import { useEffect, useState } from 'react'
import { apiFetch } from '../api'

function MetricsView() {
  const [metrics, setMetrics] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await apiFetch('/metrics')
        if (!response.ok) {
          throw new Error('Erro ao carregar métricas.')
        }
        const data = await response.json()
        setMetrics(data.metrics || [])
      } catch (err) {
        console.error(err)
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchMetrics()
  }, [])

  const formatDate = (dateString) => {
    if (!dateString) return '-'
    const date = new Date(dateString)
    return date.toLocaleString('pt-BR')
  }

  return (
    <div className="metrics-container animate-fade-in">
      <div className="page-header">
        <div className="header-title">
          <h1>Métricas de Uso</h1>
          <p className="subtitle">Acompanhamento de análises realizadas na plataforma</p>
        </div>
      </div>

      <div className="table-container" style={{ marginTop: '40px' }}>
        {loading ? (
          <div className="analysis-placeholder">
            <div className="spinner"></div>
            <p>Carregando métricas...</p>
          </div>
        ) : error ? (
          <div className="analysis-placeholder">
            <p style={{ color: 'var(--error)' }}>{error}</p>
          </div>
        ) : metrics.length === 0 ? (
          <div className="analysis-placeholder">
            <p>Nenhuma métrica registrada ainda.</p>
          </div>
        ) : (
          <table className="documents-table">
            <thead>
              <tr>
                <th>Usuário</th>
                <th>Documento</th>
                <th>Data da Análise</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((metric, index) => (
                <tr key={index}>
                  <td className="doc-name-cell">
                    <div className="user-avatar" style={{ width: '28px', height: '28px', fontSize: '10px' }}>
                      {metric.user_name?.substring(0, 2).toUpperCase()}
                    </div>
                    {metric.user_name}
                  </td>
                  <td>{metric.document_name}</td>
                  <td style={{ color: 'var(--text-dim)' }}>{formatDate(metric.analyzed_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

export default MetricsView
