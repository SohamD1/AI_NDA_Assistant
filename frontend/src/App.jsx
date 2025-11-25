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
    return token
  }, [])

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

  // Format message content with markdown-like rendering
  const formatContent = (content) => {
    // Simple markdown formatting
    return content
      .split('\n')
      .map((line, i) => {
        // Headers
        if (line.startsWith('# ')) {
          return <h3 key={i}>{line.slice(2)}</h3>
        }
        if (line.startsWith('## ')) {
          return <h4 key={i}>{line.slice(3)}</h4>
        }
        if (line.startsWith('### ')) {
          return <h5 key={i}>{line.slice(4)}</h5>
        }
        // Bold
        if (line.includes('**')) {
          const parts = line.split(/\*\*(.*?)\*\*/g)
          return (
            <p key={i}>
              {parts.map((part, j) =>
                j % 2 === 1 ? <strong key={j}>{part}</strong> : part
              )}
            </p>
          )
        }
        // Lists
        if (line.startsWith('- ') || line.startsWith('* ')) {
          return <li key={i}>{line.slice(2)}</li>
        }
        if (line.match(/^\d+\. /)) {
          return <li key={i}>{line.replace(/^\d+\. /, '')}</li>
        }
        // Code blocks
        if (line.startsWith('```')) {
          return null
        }
        // Regular text
        return line ? <p key={i}>{line}</p> : <br key={i} />
      })
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
                  {msg.role === 'assistant' ? formatContent(msg.content) : msg.content}
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
              <pre className="document-preview">
                {currentDocument}
                <div ref={documentEndRef} />
              </pre>
            )}
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
                Copy Document
              </button>
              <button
                onClick={() => {
                  const blob = new Blob([currentDocument], { type: 'text/plain' })
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = 'legal-document.txt'
                  a.click()
                  URL.revokeObjectURL(url)
                }}
                className="action-btn"
              >
                Download
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
