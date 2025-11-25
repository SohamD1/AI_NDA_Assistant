import { useState, useRef, useEffect, useCallback } from 'react'
import './App.css'

// Generate a unique session ID
const generateSessionId = () => {
  return 'session_' + Math.random().toString(36).substring(2, 15)
}

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [sessionId] = useState(() => generateSessionId())
  const [currentDocument, setCurrentDocument] = useState(null)
  const [previousDocument, setPreviousDocument] = useState(null)
  const [toolStatus, setToolStatus] = useState(null)
  const [showDiff, setShowDiff] = useState(false)
  const messagesEndRef = useRef(null)
  const documentEndRef = useRef(null)

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Auto-scroll document preview when it updates
  useEffect(() => {
    if (currentDocument) {
      documentEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [currentDocument])

  // Parse tool events and document content from messages
  const parseToolEvents = useCallback((token) => {
    if (token.startsWith('[TOOL_START:')) {
      const toolName = token.slice(12, -1)
      setToolStatus({ type: 'start', name: toolName })
      return null
    }
    if (token.startsWith('[TOOL_EXECUTING:')) {
      const toolName = token.slice(16, -1)
      setToolStatus({ type: 'executing', name: toolName })
      return null
    }
    if (token.startsWith('[TOOL_RESULT:')) {
      const toolName = token.slice(13, -1)
      setToolStatus({ type: 'result', name: toolName })
      setTimeout(() => setToolStatus(null), 1500)
      return null
    }
    // Handle LaTeX document from generate_document or apply_edits tool
    if (token.startsWith('[LATEX_DOCUMENT:')) {
      const base64Content = token.slice(16, -1)
      try {
        // Decode base64 to get the LaTeX content
        const latexContent = atob(base64Content)
        console.log('Received LaTeX document, length:', latexContent.length)
        setPreviousDocument(currentDocument)
        setCurrentDocument(latexContent)
      } catch (e) {
        console.error('Failed to decode LaTeX content:', e)
      }
      return null
    }
    return token
  }, [currentDocument])

  // Extract document from assistant message
  const extractDocument = useCallback((content) => {
    // Look for document patterns
    const docPatterns = [
      /```[\s\S]*?```/g,
      /={60}[\s\S]*?={60}/g,
      /# [A-Z][\s\S]*?(?=\n\n---|\n\n\*Document|$)/g
    ]

    for (const pattern of docPatterns) {
      const matches = content.match(pattern)
      if (matches && matches.length > 0) {
        const doc = matches[matches.length - 1]
        if (doc.length > 100) { // Only consider substantial documents
          return doc
        }
      }
    }
    return null
  }, [])

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return

    const userMessage = { role: 'user', content: input }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsStreaming(true)
    setToolStatus(null)

    // Add empty assistant message
    setMessages(prev => [...prev, { role: 'assistant', content: '', toolCalls: [] }])

    try {
      const response = await fetch('http://localhost:5000/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: input,
          session_id: sessionId
        })
      })

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let fullContent = ''

      const readStream = async () => {
        while (true) {
          const { done, value } = await reader.read()
          if (done) {
            setIsStreaming(false)
            setToolStatus(null)

            // Check for document in final content
            const doc = extractDocument(fullContent)
            if (doc) {
              setPreviousDocument(currentDocument)
              setCurrentDocument(doc)
            }
            return
          }

          const chunk = decoder.decode(value)
          const lines = chunk.split('\n')

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              let token = line.slice(6)

              if (token === '[DONE]') {
                setIsStreaming(false)
                setToolStatus(null)
                return
              }

              // Parse tool events
              const parsed = parseToolEvents(token)
              if (parsed === null) continue

              // Append to message
              fullContent += parsed
              setMessages(prev => {
                const updated = [...prev]
                const lastIdx = updated.length - 1
                updated[lastIdx] = {
                  ...updated[lastIdx],
                  content: updated[lastIdx].content + parsed
                }
                return updated
              })
            }
          }
        }
      }

      await readStream()
    } catch (err) {
      console.error('Stream error:', err)
      setIsStreaming(false)
      setToolStatus(null)
      setMessages(prev => {
        const updated = [...prev]
        const lastIdx = updated.length - 1
        updated[lastIdx] = {
          ...updated[lastIdx],
          content: updated[lastIdx].content + '\n\n[Error: Connection failed. Please try again.]'
        }
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
    try {
      await fetch(`http://localhost:5000/history?session_id=${sessionId}`, {
        method: 'DELETE'
      })
      setMessages([])
      setCurrentDocument(null)
      setPreviousDocument(null)
    } catch (err) {
      console.error('Failed to clear history:', err)
    }
  }

  // Render diff between old and new document
  const renderDiff = () => {
    if (!previousDocument || !currentDocument || !showDiff) return null

    const oldLines = previousDocument.split('\n')
    const newLines = currentDocument.split('\n')

    return (
      <div className="diff-view">
        <h4>Changes Made</h4>
        <div className="diff-content">
          {newLines.map((line, idx) => {
            const oldLine = oldLines[idx]
            const isNew = !oldLine
            const isChanged = oldLine && oldLine !== line

            let className = ''
            if (isNew) className = 'diff-added'
            else if (isChanged) className = 'diff-modified'

            return (
              <div key={idx} className={`diff-line ${className}`}>
                <span className="line-number">{idx + 1}</span>
                <span className="line-content">{line || ' '}</span>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  // Generate PDF from the rendered document
  const downloadAsPDF = async () => {
    if (!currentDocument) return

    // Create a hidden iframe to render the document
    const printWindow = window.open('', '_blank')
    if (!printWindow) {
      alert('Please allow popups to download PDF')
      return
    }

    // Parse LaTeX to HTML for printing
    const parseLatexForPrint = (tex) => {
      let html = tex
      // Remove preamble
      html = html.replace(/\\documentclass[^]*?\\begin\{document\}/s, '')
      html = html.replace(/\\end\{document\}/g, '')
      html = html.replace(/\\usepackage[^\n]*/g, '')

      // Remove table/tabular environments and their column specs like {p{3in}p{3in}}
      html = html.replace(/\\begin\{tabular\}\{[^}]*\}/g, '')
      html = html.replace(/\\end\{tabular\}/g, '')
      html = html.replace(/\\begin\{table\}[^]*?\\end\{table\}/gs, '')
      html = html.replace(/\{p\{[^}]+\}[^}]*\}/g, '') // Remove {p{3in}p{3in}} style specs
      html = html.replace(/\{[lcr|]+\}/g, '') // Remove {lll} or {|c|c|} column specs

      // Remove other environments we don't need
      html = html.replace(/\\begin\{minipage\}[^]*?\\end\{minipage\}/gs, '')
      html = html.replace(/\\begin\{flushright\}([^]*?)\\end\{flushright\}/g, '<div style="text-align:right">$1</div>')
      html = html.replace(/\\begin\{flushleft\}([^]*?)\\end\{flushleft\}/g, '<div style="text-align:left">$1</div>')

      // Title handling
      html = html.replace(/\\title\{([^}]+)\}/g, '<h1>$1</h1>')
      html = html.replace(/\\maketitle/g, '')
      html = html.replace(/\\begin\{center\}([^]*?)\\end\{center\}/g, '<div style="text-align:center">$1</div>')
      html = html.replace(/\{\\Large\\bfseries\s*([^}]+)\}/g, '<h1>$1</h1>')
      html = html.replace(/\{\\large\\bfseries\s*([^}]+)\}/g, '<h2>$1</h2>')
      html = html.replace(/\\textbf\{\\Large\s*([^}]+)\}/g, '<h1>$1</h1>')

      // Sections
      html = html.replace(/\\section\*?\{([^}]+)\}/g, '<h2>$1</h2>')
      html = html.replace(/\\subsection\*?\{([^}]+)\}/g, '<h3>$1</h3>')

      // Text formatting
      html = html.replace(/\\textbf\{([^}]+)\}/g, '<strong>$1</strong>')
      html = html.replace(/\\textit\{([^}]+)\}/g, '<em>$1</em>')
      html = html.replace(/\\underline\{([^}]+)\}/g, '<u>$1</u>')
      html = html.replace(/\\emph\{([^}]+)\}/g, '<em>$1</em>')

      // Lists
      html = html.replace(/\\begin\{itemize\}/g, '<ul>')
      html = html.replace(/\\end\{itemize\}/g, '</ul>')
      html = html.replace(/\\begin\{enumerate\}/g, '<ol>')
      html = html.replace(/\\end\{enumerate\}/g, '</ol>')
      html = html.replace(/\\item\s*/g, '<li>')

      // Spacing
      html = html.replace(/\\vspace\{[^}]+\}/g, '<div style="height:20px"></div>')
      html = html.replace(/\\hspace\{[^}]+\}/g, '&nbsp;&nbsp;')
      html = html.replace(/\\hfill/g, '')
      html = html.replace(/\\noindent\s*/g, '')
      html = html.replace(/\\par\s*/g, '</p><p>')
      html = html.replace(/\\bigskip/g, '<br><br>')
      html = html.replace(/\\medskip/g, '<br>')
      html = html.replace(/\\smallskip/g, '')
      html = html.replace(/\\newline/g, '<br>')
      html = html.replace(/\\\\\s*/g, '<br>')

      // Rules/lines
      html = html.replace(/\\rule\{([^}]+)\}\{[^}]+\}/g, '<hr style="width:$1;border:none;border-top:1px solid #111">')
      html = html.replace(/\\hrulefill/g, '<hr>')

      // Special characters
      html = html.replace(/\\&/g, '&amp;')
      html = html.replace(/\\%/g, '%')
      html = html.replace(/\\\$/g, '$')
      html = html.replace(/\\_/g, '_')
      html = html.replace(/\\#/g, '#')
      html = html.replace(/\\ldots/g, '...')
      html = html.replace(/---/g, '—')
      html = html.replace(/--/g, '–')
      html = html.replace(/``/g, '"')
      html = html.replace(/''/g, '"')

      // Clean up remaining LaTeX commands and braces
      html = html.replace(/\\[a-zA-Z]+\[[^\]]*\]\{[^}]*\}/g, '') // commands with optional args
      html = html.replace(/\\[a-zA-Z]+\{[^}]*\}/g, '') // commands with args
      html = html.replace(/\\[a-zA-Z]+/g, '') // commands without args
      html = html.replace(/\{([^{}]*)\}/g, '$1') // remove remaining braces but keep content

      // Paragraphs
      html = html.replace(/\n\s*\n/g, '</p><p>')

      // Clean up empty tags and extra whitespace
      html = html.replace(/<p>\s*<\/p>/g, '')
      html = html.replace(/\s+/g, ' ')

      return '<p>' + html + '</p>'
    }

    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>NDA Document</title>
        <style>
          body {
            font-family: 'Times New Roman', Georgia, serif;
            padding: 40px 60px;
            background: white;
            color: #111;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            font-size: 12pt;
          }
          h1 { text-align: center; font-size: 18pt; font-weight: bold; margin-bottom: 24px; text-transform: uppercase; border-bottom: 2px solid #111; padding-bottom: 10px; }
          h2 { font-size: 14pt; font-weight: bold; margin-top: 24px; margin-bottom: 12px; }
          h3 { font-size: 12pt; font-weight: bold; margin-top: 16px; margin-bottom: 8px; }
          p { margin: 12px 0; text-align: justify; }
          ul, ol { margin: 12px 0; padding-left: 24px; }
          li { margin: 6px 0; }
          @media print {
            body { padding: 20px; }
          }
        </style>
      </head>
      <body>
        ${parseLatexForPrint(currentDocument)}
      </body>
      </html>
    `)
    printWindow.document.close()

    // Wait for content to load then print
    setTimeout(() => {
      printWindow.print()
    }, 250)
  }

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <h1>LexiDoc - Legal Document Assistant</h1>
        <div className="header-actions">
          <span className="session-badge">Session: {sessionId.slice(0, 12)}...</span>
          <button onClick={clearHistory} className="clear-btn" disabled={isStreaming}>
            Clear History
          </button>
        </div>
      </header>

      <div className="main-content">
        {/* Chat Panel */}
        <div className="chat-panel">
          <div className="panel-header">
            <h2>Chat</h2>
            {toolStatus && (
              <div className={`tool-status ${toolStatus.type}`}>
                {toolStatus.type === 'start' && `Preparing ${toolStatus.name}...`}
                {toolStatus.type === 'executing' && `Executing ${toolStatus.name}...`}
                {toolStatus.type === 'result' && `${toolStatus.name} complete`}
              </div>
            )}
          </div>

          <div className="message-list">
            {messages.length === 0 && (
              <div className="welcome-message">
                <h3>Welcome to LexiDoc</h3>
                <p>I can help you create legal documents through conversation. Try:</p>
                <ul>
                  <li>"Help me create an NDA between my company and a contractor"</li>
                  <li>"I need an employment agreement template"</li>
                  <li>"Draft a simple service agreement"</li>
                </ul>
                <p>I'll ask clarifying questions and generate the document for you.</p>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div key={idx} className={`message ${msg.role}`}>
                <div className="message-header">
                  <span className="role">{msg.role === 'user' ? 'You' : 'LexiDoc'}</span>
                </div>
                <div className="message-content">
                  {msg.content}
                  {msg.role === 'assistant' && isStreaming && idx === messages.length - 1 && (
                    <span className="cursor">▌</span>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="input-area">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Describe the legal document you need..."
              disabled={isStreaming}
              rows={3}
            />
            <button
              onClick={handleSend}
              disabled={isStreaming || !input.trim()}
              className="send-btn"
            >
              {isStreaming ? (
                <>
                  <span className="spinner"></span>
                  Processing...
                </>
              ) : (
                'Send'
              )}
            </button>
          </div>
        </div>

        {/* Document Preview Panel */}
        <div className="document-panel">
          <div className="panel-header">
            <h2>Document Preview</h2>
            {previousDocument && currentDocument && (
              <button
                onClick={() => setShowDiff(!showDiff)}
                className={`diff-toggle ${showDiff ? 'active' : ''}`}
              >
                {showDiff ? 'Hide Changes' : 'Show Changes'}
              </button>
            )}
          </div>

          <div className="document-content">
            {!currentDocument ? (
              <div className="no-document">
                <p>No document generated yet.</p>
                <p>Start a conversation to create a legal document.</p>
              </div>
            ) : showDiff ? (
              renderDiff()
            ) : (
              <iframe
                title="Document Preview"
                className="latex-preview-frame"
                srcDoc={`
                  <!DOCTYPE html>
                  <html>
                  <head>
                    <style>
                      body {
                        font-family: 'Times New Roman', Georgia, serif;
                        padding: 40px 50px;
                        background: white;
                        color: #111;
                        line-height: 1.6;
                        max-width: 800px;
                        margin: 0 auto;
                        font-size: 12pt;
                      }
                      h1 {
                        text-align: center;
                        font-size: 18pt;
                        font-weight: bold;
                        margin-bottom: 24px;
                        text-transform: uppercase;
                        border-bottom: 2px solid #111;
                        padding-bottom: 10px;
                      }
                      h2 {
                        font-size: 14pt;
                        font-weight: bold;
                        margin-top: 24px;
                        margin-bottom: 12px;
                        text-transform: uppercase;
                      }
                      h3 {
                        font-size: 12pt;
                        font-weight: bold;
                        margin-top: 16px;
                        margin-bottom: 8px;
                      }
                      p {
                        margin: 12px 0;
                        text-align: justify;
                      }
                      ul, ol {
                        margin: 12px 0;
                        padding-left: 24px;
                      }
                      li {
                        margin: 6px 0;
                      }
                      .signature-block {
                        margin-top: 40px;
                        display: flex;
                        justify-content: space-between;
                      }
                      .signature-line {
                        width: 45%;
                      }
                      .signature-line hr {
                        border: none;
                        border-top: 1px solid #111;
                        margin: 30px 0 5px 0;
                      }
                      .center {
                        text-align: center;
                      }
                      .bold {
                        font-weight: bold;
                      }
                      pre {
                        white-space: pre-wrap;
                        font-family: 'Times New Roman', Georgia, serif;
                        font-size: 12pt;
                      }
                    </style>
                  </head>
                  <body>
                    <div id="content"></div>
                    <script>
                      const latex = ${JSON.stringify(currentDocument)};

                      function parseLatex(tex) {
                        let html = tex;

                        // Remove document class and preamble
                        html = html.replace(/\\\\documentclass[^]*?\\\\begin\\{document\\}/s, '');
                        html = html.replace(/\\\\end\\{document\\}/g, '');
                        html = html.replace(/\\\\usepackage[^\\n]*/g, '');

                        // Title - handle various formats
                        html = html.replace(/\\\\title\\{([^}]+)\\}/g, '<h1>$1</h1>');
                        html = html.replace(/\\\\maketitle/g, '');
                        html = html.replace(/\\\\begin\\{center\\}([^]*?)\\\\end\\{center\\}/g, '<div class="center">$1</div>');
                        html = html.replace(/\\{\\\\Large\\\\bfseries\\s*([^}]+)\\}/g, '<h1>$1</h1>');
                        html = html.replace(/\\{\\\\large\\\\bfseries\\s*([^}]+)\\}/g, '<h2>$1</h2>');
                        html = html.replace(/\\\\textbf\\{\\\\Large\\s*([^}]+)\\}/g, '<h1>$1</h1>');

                        // Sections
                        html = html.replace(/\\\\section\\*?\\{([^}]+)\\}/g, '<h2>$1</h2>');
                        html = html.replace(/\\\\subsection\\*?\\{([^}]+)\\}/g, '<h3>$1</h3>');

                        // Text formatting
                        html = html.replace(/\\\\textbf\\{([^}]+)\\}/g, '<strong>$1</strong>');
                        html = html.replace(/\\\\textit\\{([^}]+)\\}/g, '<em>$1</em>');
                        html = html.replace(/\\\\underline\\{([^}]+)\\}/g, '<u>$1</u>');
                        html = html.replace(/\\\\emph\\{([^}]+)\\}/g, '<em>$1</em>');

                        // Lists
                        html = html.replace(/\\\\begin\\{itemize\\}/g, '<ul>');
                        html = html.replace(/\\\\end\\{itemize\\}/g, '</ul>');
                        html = html.replace(/\\\\begin\\{enumerate\\}/g, '<ol>');
                        html = html.replace(/\\\\end\\{enumerate\\}/g, '</ol>');
                        html = html.replace(/\\\\item\\s*/g, '<li>');

                        // Spacing and formatting
                        html = html.replace(/\\\\vspace\\{[^}]+\\}/g, '<div style="height:20px"></div>');
                        html = html.replace(/\\\\hspace\\{[^}]+\\}/g, '&nbsp;&nbsp;');
                        html = html.replace(/\\\\hfill/g, '<span style="float:right">');
                        html = html.replace(/\\\\noindent\\s*/g, '');
                        html = html.replace(/\\\\par\\s*/g, '</p><p>');
                        html = html.replace(/\\\\bigskip/g, '<br><br>');
                        html = html.replace(/\\\\medskip/g, '<br>');
                        html = html.replace(/\\\\smallskip/g, '');
                        html = html.replace(/\\\\newline/g, '<br>');
                        html = html.replace(/\\\\\\\\\\s*/g, '<br>');

                        // Rules/lines for signatures
                        html = html.replace(/\\\\rule\\{([^}]+)\\}\\{[^}]+\\}/g, '<hr style="width:$1;display:inline-block;border:none;border-top:1px solid #111">');
                        html = html.replace(/\\\\hrulefill/g, '<hr>');

                        // Special characters
                        html = html.replace(/\\\\&/g, '&amp;');
                        html = html.replace(/\\\\%/g, '%');
                        html = html.replace(/\\\\\\$/g, '$');
                        html = html.replace(/\\\\_/g, '_');
                        html = html.replace(/\\\\#/g, '#');
                        html = html.replace(/\\\\ldots/g, '...');
                        html = html.replace(/---/g, '—');
                        html = html.replace(/--/g, '–');
                        html = html.replace(/\`\`/g, '"');
                        html = html.replace(/''/g, '"');

                        // Clean up remaining LaTeX commands
                        html = html.replace(/\\\\[a-zA-Z]+\\{[^}]*\\}/g, '');
                        html = html.replace(/\\\\[a-zA-Z]+/g, '');

                        // Convert double newlines to paragraphs
                        html = html.replace(/\\n\\s*\\n/g, '</p><p>');

                        return '<p>' + html + '</p>';
                      }

                      try {
                        document.getElementById('content').innerHTML = parseLatex(latex);
                      } catch(e) {
                        document.getElementById('content').innerHTML = '<pre>' + latex + '</pre>';
                      }
                    </script>
                  </body>
                  </html>
                `}
              />
            )}
            <div ref={documentEndRef} />
          </div>

          {currentDocument && (
            <div className="document-actions">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(currentDocument)
                  alert('Document copied to clipboard!')
                }}
                className="action-btn"
              >
                Copy LaTeX
              </button>
              <button
                onClick={downloadAsPDF}
                className="action-btn primary"
              >
                Download PDF
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <footer className="app-footer">
        <p>LexiDoc - AI-Powered Legal Document Assistant | Not legal advice - consult a qualified attorney</p>
      </footer>
    </div>
  )
}

export default App
