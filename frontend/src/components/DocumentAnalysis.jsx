import { useRef, useState } from 'react'
import keycloak from '../auth/keycloak'

const API_BASE = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001'

function DocumentAnalysis({ onDocumentAnalyzed, onSuccess }) {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [statusMessage, setStatusMessage] = useState('')
  const fileInputRef = useRef(null)

  const handleFileChange = (e) => {
    const selected = e.target.files[0]
    if (selected && selected.type === 'application/pdf') {
      setFile(selected)
      setStatusMessage('')
    }
  }

  const handleAnalyze = async () => {
    if (!file) return

    setLoading(true)
    setStatusMessage('Enviando documento...')

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${keycloak.token}`
        },
        body: formData,
      })

      if (!response.ok) {
        if (response.status === 401) return keycloak.logout()
        throw new Error('Erro ao enviar análise')
      }

      const data = await response.json()
      const newTask = {
        id: data.id,
        name: file.name,
        date: new Date().toLocaleString('pt-BR'),
        status: 'em_analise',
        stage: 'Iniciando processamento',
        progress: 20,
      }
      onDocumentAnalyzed(newTask)
      onSuccess?.('Documento enviado com sucesso! Acompanhe o progresso na lista.')
      setFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (error) {
      setStatusMessage(`Erro: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="analysis-container animate-fade-in">
      <div className="page-header" style={{ marginBottom: '32px' }}>
        <div className="header-title">
          <h1>Nova Análise IA</h1>
          <p className="subtitle">Faça o upload de documentos PDF para extração inteligente de dados</p>
        </div>
      </div>

      <div className="analysis-page" style={{ gridTemplateColumns: '1fr', maxWidth: '600px', margin: '0 auto' }}>
        <div className="upload-card">
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <h2 style={{ fontSize: '18px', fontWeight: '700', marginBottom: '20px' }}>Upload do Contrato</h2>
            <label className="file-upload" htmlFor="pdf-input">
              <input
                id="pdf-input"
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />
              <div className="upload-area" style={{ minHeight: '200px' }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="upload-icon-svg">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
                <span className="upload-text">
                  {file ? file.name : 'Selecionar Documento PDF'}
                </span>
                <span className="upload-hint">Clique para selecionar seu arquivo</span>
              </div>
            </label>

            {statusMessage && (
              <p style={{ marginTop: '16px', fontSize: '14px', color: statusMessage.includes('Erro') ? 'var(--error)' : 'var(--primary)' }}>
                {statusMessage}
              </p>
            )}

            <button
              className="btn-primary"
              onClick={handleAnalyze}
              disabled={!file || loading}
              style={{ width: '100%', marginTop: '24px', justifyContent: 'center' }}
            >
              {loading ? (
                <>
                  <div className="spinner" style={{ width: '16px', height: '16px', borderTopColor: '#fff' }}></div>
                  Enviando...
                </>
              ) : (
                'Enviar para Análise'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default DocumentAnalysis
