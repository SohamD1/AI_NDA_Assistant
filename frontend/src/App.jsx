import { useState, useRef, useEffect } from 'react'
import './App.css'

const generateSessionId = () => 'session_' + Math.random().toString(36).substring(2, 15)

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [sessionId] = useState(() => generateSessionId())
  const [currentDocument, setCurrentDocument] = useState(null)
  const [toolStatus, setToolStatus] = useState(null)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Format chat messages with markdown-like syntax
  const formatMessage = (text) => {
    if (!text) return ''

    let html = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')

    // Bold **text**
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')

    // Bullet points
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
    html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')

    // Line breaks
    html = html.replace(/\n/g, '<br>')

    return html
  }

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return

    const userMessage = { role: 'user', content: input }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsStreaming(true)
    setToolStatus(null)

    // Add empty assistant message
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])

    try {
      const response = await fetch('http://localhost:5000/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input, session_id: sessionId })
      })

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6)

          if (data === '[DONE]') {
            setIsStreaming(false)
            setToolStatus(null)
            return
          }

          // Handle tool events
          if (data.startsWith('[TOOL_EXECUTING:')) {
            setToolStatus(data.slice(16, -1))
            continue
          }
          if (data.startsWith('[TOOL_RESULT:')) {
            setToolStatus(null)
            continue
          }
          if (data.startsWith('[TOOL_START:')) {
            continue
          }

          // Handle LaTeX document
          if (data.startsWith('[LATEX_DOCUMENT:')) {
            try {
              const base64 = data.slice(16, -1)
              setCurrentDocument(atob(base64))
            } catch (e) {
              console.error('Failed to decode LaTeX:', e)
            }
            continue
          }

          // Handle text content (base64 encoded)
          if (data.startsWith('[TEXT:')) {
            try {
              const base64 = data.slice(6, -1)
              const text = atob(base64)
              setMessages(prev => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                if (last && last.role === 'assistant') {
                  last.content += text
                }
                return updated
              })
            } catch (e) {
              console.error('Failed to decode text:', e)
            }
            continue
          }

          // Regular text fallback (shouldn't happen with new backend)
          setMessages(prev => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last && last.role === 'assistant') {
              last.content += data
            }
            return updated
          })
        }
      }

      setIsStreaming(false)
      setToolStatus(null)
    } catch (err) {
      console.error('Stream error:', err)
      setIsStreaming(false)
      setMessages(prev => {
        const updated = [...prev]
        const last = updated[updated.length - 1]
        if (last) last.content += '\n\n[Error: Connection failed]'
        return updated
      })
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const clearHistory = async () => {
    await fetch(`http://localhost:5000/history?session_id=${sessionId}`, { method: 'DELETE' })
    setMessages([])
    setCurrentDocument(null)
  }

  const downloadPDF = () => {
    if (!currentDocument) return
    const win = window.open('', '_blank')
    if (!win) return alert('Please allow popups')

    // Simple LaTeX to HTML
    let html = currentDocument
      .replace(/\\documentclass[\s\S]*?\\begin\{document\}/g, '')
      .replace(/\\end\{document\}/g, '')
      .replace(/\\section\*?\{([^}]+)\}/g, '<h2>$1</h2>')
      .replace(/\\textbf\{([^}]+)\}/g, '<strong>$1</strong>')
      .replace(/\\begin\{itemize\}/g, '<ul>')
      .replace(/\\end\{itemize\}/g, '</ul>')
      .replace(/\\item\s*/g, '<li>')
      .replace(/\\\\/g, '<br>')
      .replace(/\\[a-zA-Z]+\{[^}]*\}/g, '')
      .replace(/\\[a-zA-Z]+/g, '')
      .replace(/\n\n/g, '</p><p>')

    win.document.write(`
      <!DOCTYPE html><html><head><title>NDA</title>
      <style>
        body { font-family: 'Times New Roman', serif; padding: 40px 60px; max-width: 800px; margin: 0 auto; }
        h2 { margin-top: 24px; }
        p { text-align: justify; line-height: 1.6; }
      </style>
      </head><body><p>${html}</p></body></html>
    `)
    win.document.close()
    setTimeout(() => win.print(), 200)
  }

  // LaTeX preview parser for iframe
  const parseLatex = (tex) => {
    let html = tex

    // Remove preamble
    html = html.replace(/\\documentclass[\s\S]*?\\begin\{document\}/g, '')
    html = html.replace(/\\end\{document\}/g, '')
    html = html.replace(/\\usepackage[^\n]*/g, '')

    // Remove tabular/table environments completely and replace with styled div
    html = html.replace(/\\begin\{tabular\}\{[^}]*\}([\s\S]*?)\\end\{tabular\}/g, (_, content) => {
      // Parse table rows - split by \\ or \hline
      const rows = content.split(/\\\\|\\hline/).filter(r => r.trim())
      let tableHtml = '<div class="signature-section">'
      for (const row of rows) {
        // Split columns by &
        const cols = row.split('&').map(c => c.trim())
        if (cols.length >= 2) {
          tableHtml += `<div class="sig-row"><div class="sig-col">${cols[0]}</div><div class="sig-col">${cols[1]}</div></div>`
        } else if (cols[0]) {
          tableHtml += `<div class="sig-row"><div class="sig-col">${cols[0]}</div></div>`
        }
      }
      tableHtml += '</div>'
      return tableHtml
    })

    // Remove any remaining table formatting artifacts
    html = html.replace(/\{[lcr|]+\}/g, '')
    html = html.replace(/\{p\{[^}]+\}[^}]*\}/g, '')
    html = html.replace(/\{[\d.]+pt\}/g, '')
    html = html.replace(/\\hline/g, '')
    html = html.replace(/\\cline\{[^}]*\}/g, '')

    // Sections
    html = html.replace(/\\section\*?\{([^}]+)\}/g, '<h2>$1</h2>')
    html = html.replace(/\\subsection\*?\{([^}]+)\}/g, '<h3>$1</h3>')

    // Text formatting
    html = html.replace(/\\textbf\{([^}]+)\}/g, '<strong>$1</strong>')
    html = html.replace(/\\textit\{([^}]+)\}/g, '<em>$1</em>')
    html = html.replace(/\\underline\{([^}]+)\}/g, '<u>$1</u>')

    // Lists
    html = html.replace(/\\begin\{itemize\}/g, '<ul>')
    html = html.replace(/\\end\{itemize\}/g, '</ul>')
    html = html.replace(/\\begin\{enumerate\}/g, '<ol>')
    html = html.replace(/\\end\{enumerate\}/g, '</ol>')
    html = html.replace(/\\item\s*/g, '<li>')

    // Other environments
    html = html.replace(/\\begin\{center\}([\s\S]*?)\\end\{center\}/g, '<div style="text-align:center">$1</div>')

    // Spacing
    html = html.replace(/\\\\/g, '<br>')
    html = html.replace(/\\vspace\{[^}]+\}/g, '<br>')
    html = html.replace(/\\hspace\{[^}]+\}/g, '&nbsp;&nbsp;')
    html = html.replace(/\\noindent/g, '')
    html = html.replace(/\\par/g, '</p><p>')
    html = html.replace(/\\rule\{[^}]+\}\{[^}]+\}/g, '<hr class="sig-line">')

    // Special chars
    html = html.replace(/\\&/g, '&amp;')
    html = html.replace(/---/g, '&mdash;')
    html = html.replace(/--/g, '&ndash;')

    // Clean remaining LaTeX
    html = html.replace(/\\[a-zA-Z]+\{[^}]*\}/g, '')
    html = html.replace(/\\[a-zA-Z]+/g, '')
    html = html.replace(/\{([^{}]*)\}/g, '$1')
    html = html.replace(/\n\n+/g, '</p><p>')

    return html
  }

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>LexiDoc - NDA Assistant</h1>
        <button onClick={clearHistory} className="clear-btn" disabled={isStreaming}>Clear</button>
      </header>

      <div className="main-content">
        {/* Chat Panel */}
        <div className="chat-panel">
          <div className="panel-header">
            <h2>Chat</h2>
            {toolStatus && <span className="tool-status">Running: {toolStatus}</span>}
          </div>

          <div className="message-list">
            {messages.length === 0 && (
              <div className="welcome-message">
                <h3>Welcome to LexiDoc</h3>
                <p>I can help you create NDAs. Just tell me what you need!</p>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div key={idx} className={`message ${msg.role}`}>
                <div className="message-header">
                  <span className="role">{msg.role === 'user' ? 'You' : 'LexiDoc'}</span>
                </div>
                <div
                  className="message-content"
                  dangerouslySetInnerHTML={{ __html: formatMessage(msg.content) }}
                />
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="input-area">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Describe your NDA requirements..."
              disabled={isStreaming}
              rows={3}
            />
            <button onClick={handleSend} disabled={isStreaming || !input.trim()} className="send-btn">
              {isStreaming ? 'Processing...' : 'Send'}
            </button>
          </div>
        </div>

        {/* Document Panel */}
        <div className="document-panel">
          <div className="panel-header">
            <h2>Document Preview</h2>
          </div>

          <div className="document-content">
            {!currentDocument ? (
              <div className="no-document">
                <p>No document yet.</p>
                <p>Chat to create your NDA.</p>
              </div>
            ) : (
              <iframe
                title="Preview"
                className="latex-preview-frame"
                srcDoc={`
                  <!DOCTYPE html><html><head>
                  <style>
                    body { font-family: 'Times New Roman', serif; padding: 40px; color: #111; line-height: 1.6; }
                    h2 { font-size: 14pt; margin-top: 20px; }
                    p { margin: 10px 0; text-align: justify; }
                    ul, ol { padding-left: 24px; }
                    .signature-section { margin-top: 40px; }
                    .sig-row { display: flex; justify-content: space-between; margin: 20px 0; }
                    .sig-col { width: 45%; }
                    .sig-line { border: none; border-top: 1px solid #111; margin: 30px 0 5px 0; }
                  </style>
                  </head><body><p>${parseLatex(currentDocument)}</p></body></html>
                `}
              />
            )}
          </div>

          {currentDocument && (
            <div className="document-actions">
              <button onClick={() => navigator.clipboard.writeText(currentDocument)} className="action-btn">
                Copy LaTeX
              </button>
              <button onClick={downloadPDF} className="action-btn primary">
                Download PDF
              </button>
            </div>
          )}
        </div>
      </div>

      <footer className="app-footer">
        <p>LexiDoc - Not legal advice</p>
      </footer>
    </div>
  )
}

export default App
