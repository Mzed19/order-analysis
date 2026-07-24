import { useEffect, useState } from 'react'
import { apiFetch } from '../api'

// Simple Markdown Parser for bold, italic, and lists
const formatMarkdown = (text) => {
  if (!text) return ''

  let formatted = text
    .replace(/^### (.*$)/gm, '<h3 class="insight-title-text">$1</h3>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/^- (.*$)/gm, '<li>$1</li>')
    .replace(/\n/g, '<br />')

  // Clean up nested lists and headings
  formatted = formatted
    .replace(/(<li>.*<\/li>)/g, '<ul>$1</ul>')
    .replace(/<\/ul><br \/><ul>/g, '')
    .replace(/<br \/><h3/g, '<h3')
    .replace(/<\/h3><br \/>/g, '</h3>')

  return <div className="formatted-content" dangerouslySetInnerHTML={{ __html: formatted }} />
}

function AnalysisResults({ taskId, onBack }) {
  const [analysisResults, setAnalysisResults] = useState([])
  const [fileName, setFileName] = useState('')
  const [statusMessage, setStatusMessage] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchTaskStatus = async () => {
      try {
        const response = await apiFetch(`/analyze/${taskId}`)
        if (!response.ok) {
          setStatusMessage('Erro ao carregar detalhes da análise.')
          setLoading(false)
          return
        }
        const data = await response.json()
        const task = data.task

        if (task.filename) setFileName(task.filename)

        if (task.status === 'completed' || task.status === 'concluded') {
          const resultList = Array.isArray(task.result) ? task.result : [String(task.result)]
          setAnalysisResults(resultList)
          setStatusMessage('')
          setLoading(false)
        } else if (task.status === 'failed') {
          setStatusMessage(`Falha na análise: ${task.result}`)
          setLoading(false)
        } else {
          setStatusMessage('A análise ainda está em processamento...')
          setTimeout(fetchTaskStatus, 3000)
        }
      } catch (error) {
        console.error(error)
        setStatusMessage('Erro de conexão ao buscar resultados.')
        setLoading(false)
      }
    }

    if (taskId) fetchTaskStatus()
  }, [taskId])

  const getRiskScore = (text) => {
    // Tenta encontrar "Score de Risco: XX" ou "Risco: XX"
    const match = text.match(/(?:\*\*Score de Risco:\*\*|\*\*Risco:\*\*)\s*(\d+)/i)
    return match ? parseInt(match[1]) : null
  }

  const getScoreColor = (score) => {
    if (score >= 80) return 'var(--error)'
    if (score >= 40) return 'var(--warning)'
    return 'var(--success)'
  }

  return (
    <div className="analysis-container animate-fade-in">
      <div className="page-header" style={{ marginBottom: '40px' }}>
        <div className="header-title">
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '12px' }}>
            <button className="btn-details" onClick={onBack} style={{ padding: '8px', borderRadius: '50%' }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="15 18 9 12 15 6" />
              </svg>
            </button>
            <h1 style={{ fontSize: '36px' }}>Relatório de Insights</h1>
          </div>
          <div style={{ marginLeft: '52px' }}>
            <p className="subtitle">Análise detalhada gerada pela Inteligência Artificial</p>
            {fileName && (
              <div className="doc-badge" style={{ marginTop: '12px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
                  <polyline points="13 2 13 9 20 9"></polyline>
                </svg>
                {fileName}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="insights-grid">
        {analysisResults.length > 0 ? (
          analysisResults.map((item, index) => {
            return (
              <div className="analysis-card insight-card animate-fade-in" key={index} style={{ animationDelay: `${index * 0.1}s` }}>
                <div className="insight-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span className="insight-number">#{index + 1}</span>
                    <h3 className="insight-card-title">Análise de Crédito</h3>
                  </div>
                </div>
                <div className="insight-content">
                  {formatMarkdown(item)}
                </div>
              </div>
            )
          })
        ) : loading ? (
          <div className="analysis-placeholder" style={{ gridColumn: '1 / -1' }}>
            <div className="spinner" style={{ width: '60px', height: '60px' }}></div>
            <p style={{ marginTop: '24px', fontSize: '18px' }}>{statusMessage || 'Processando seus insights...'}</p>
          </div>
        ) : (
          <div className="analysis-placeholder" style={{ gridColumn: '1 / -1' }}>
            <p>{statusMessage || 'Nenhum resultado disponível para este documento.'}</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default AnalysisResults
