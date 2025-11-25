import { useState, useRef, useEffect } from 'react'
import './App.css'

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const messagesEndRef = useRef(null)

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = () => {
    if (!input.trim() || isStreaming) return

    // Add user message
    const userMessage = { role: 'user', content: input }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsStreaming(true)

    // Add empty assistant message that will be streamed into
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])

    // Connect to SSE stream using fetch (EventSource only supports GET)
    fetch('http://localhost:5000/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: input })
    }).then(response => {
      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      const readStream = () => {
        reader.read().then(({ done, value }) => {
          if (done) {
            setIsStreaming(false)
            return
          }

          const chunk = decoder.decode(value)
          // Parse SSE format: "data: token\n\n"
          const lines = chunk.split('\n')

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const token = line.slice(6) // Remove "data: " prefix

              if (token === '[DONE]') {
                setIsStreaming(false)
                return
              }

              // Append token to last message
              setMessages(prev => {
                const updated = [...prev]
                const lastIdx = updated.length - 1
                updated[lastIdx] = {
                  ...updated[lastIdx],
                  content: updated[lastIdx].content + token
                }
                return updated
              })
            }
          }

          readStream()
        })
      }

      readStream()
    }).catch(err => {
      console.error('Stream error:', err)
      setIsStreaming(false)
    })
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat-container">
      <h1>Chat UI</h1>

      <div className="message-list">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            <span className="role">{msg.role === 'user' ? 'You' : 'AI'}</span>
            <p>{msg.content}{msg.role === 'assistant' && isStreaming && idx === messages.length - 1 && '▌'}</p>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="input-area">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Type a message..."
          disabled={isStreaming}
        />
        <button onClick={handleSend} disabled={isStreaming || !input.trim()}>
          {isStreaming ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  )
}

export default App
