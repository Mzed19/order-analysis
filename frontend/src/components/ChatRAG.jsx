import { useState, useRef, useEffect } from 'react'
import { apiFetch } from '../api'

function ChatRAG() {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Olá! Sou seu assistente de análise de crédito. Você pode me fazer perguntas sobre os pedidos de compra analisados ou sobre as diretrizes gerais de crédito. Como posso ajudar?'
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim()
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await apiFetch('/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question: userMessage.content }),
      })

      if (!response.ok) {
        throw new Error('Erro ao obter resposta do servidor')
      }

      const data = await response.json()

      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: data.answer || 'Sem resposta.'
        }
      ])
    } catch (error) {
      console.error(error)
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: 'Desculpe, ocorreu um erro ao processar sua pergunta. Por favor, tente novamente.'
        }
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-container animate-fade-in">
      <div className="chat-header">
        <h2>Assistente Virtual</h2>
        <p className="subtitle">Tire suas dúvidas sobre crédito usando Inteligência Artificial</p>
      </div>

      <div className="chat-messages">
        {messages.map((msg) => (
          <div key={msg.id} className={`chat-message-wrapper ${msg.role}`}>
            <div className="chat-message-avatar">
              {msg.role === 'assistant' ? 'AI' : 'U'}
            </div>
            <div className="chat-message-bubble">
              <div className="chat-message-text">{msg.content}</div>
            </div>
          </div>
        ))}
        {loading && (
          <div className="chat-message-wrapper assistant">
            <div className="chat-message-avatar">AI</div>
            <div className="chat-message-bubble loading-bubble">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form className="chat-input-area" onSubmit={handleSend}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Faça uma pergunta"
          disabled={loading}
          autoFocus
        />
        <button type="submit" className="btn-action" disabled={loading || !input.trim()}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
          <span>Enviar</span>
        </button>
      </form>
    </div>
  )
}

export default ChatRAG
