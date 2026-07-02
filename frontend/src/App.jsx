import { useEffect, useState } from 'react'
import Sidebar from './components/Sidebar'
import DocumentList from './components/DocumentList'
import DocumentAnalysis from './components/DocumentAnalysis'
import AnalysisResults from './components/AnalysisResults'
import keycloak from './auth/keycloak'
import './App.css'

const API_BASE = import.meta.env.VITE_BACKEND_URL || '/contract-ai-backend'

function App() {
  const [view, setView] = useState('list')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [documents, setDocuments] = useState([])
  const [toastMessage, setToastMessage] = useState('')
  const [selectedTaskId, setSelectedTaskId] = useState(null)

  const formatDate = (value) => {
    try {
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return new Date().toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
      return date.toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return new Date().toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    }
  }

  const fetchAnalyses = async () => {
    try {
      const response = await fetch(`${API_BASE}/analyses`, {
        headers: {
          'Authorization': `Bearer ${keycloak.token}`
        }
      })
      if (!response.ok) {
        if (response.status === 401) keycloak.logout()
        throw new Error('Falha ao carregar análises')
      }
      const data = await response.json()
      const docs = (data.analyses || []).map((item) => {
        let progress = 0

        if (item.chunks_quantity) {
          const analyzed = item.analyzed_chunks_quantity || 0
          progress = Math.round((analyzed / item.chunks_quantity) * 100)
        }

        return {
          id: item.id,
          name: item.filename || 'Documento sem nome',
          date: formatDate(item.created_at),
          status: item.status === 'completed' || item.status === 'concluded' ? 'concluido' : item.status === 'failed' ? 'erro' : 'em_analise',
          stage: item.status === 'queued' ? 'Na fila' : item.status === 'processing' ? 'Processando' : item.status === 'failed' ? 'Erro na análise' : 'Análise concluída',
          progress,
          result: item.result,
        }
      })
      setDocuments(docs)
    } catch (error) {
      console.error(error)
    }
  }

  useEffect(() => {
    fetchAnalyses()
    const intervalId = setInterval(fetchAnalyses, 10000)
    return () => clearInterval(intervalId)
  }, [])

  const notify = (message) => {
    setToastMessage(message)
    setTimeout(() => setToastMessage(''), 4000)
  }

  const handleDocumentAnalyzed = (doc) => {
    setDocuments((prev) => [doc, ...prev])
    setView('list')
    fetchAnalyses()
  }

  const handleViewDetails = (id) => {
    setSelectedTaskId(id)
    setView('results')
  }

  const handleGoToNew = () => {
    setSelectedTaskId(null)
    setView('new')
  }

  const handleGoBackToList = () => {
    setView('list')
  }

  const handleDeleteDocument = async (id) => {
    try {
      const response = await fetch(`${API_BASE}/analyze/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${keycloak.token}`
        }
      })
      if (response.status === 401) return keycloak.logout()
      if (!response.ok) throw new Error('Falha ao excluir análise')

      setDocuments((prev) => prev.filter(doc => doc.id !== id))
      notify('Análise excluída com sucesso.')
    } catch (error) {
      console.error(error)
      notify('Erro ao excluir análise.')
    }
  }

  return (
    <div className="app-layout">
      <Sidebar
        currentView={view === 'results' ? 'list' : view}
        onNavigate={(v) => {
          if (v === 'new') handleGoToNew()
          else setView(v)
        }}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />
      <main className="main-content">
        {view === 'list' && (
          <DocumentList
            documents={documents}
            onNewDocument={handleGoToNew}
            onViewDocument={handleViewDetails}
            onDeleteDocument={handleDeleteDocument}
          />
        )}

        {view === 'new' && (
          <DocumentAnalysis
            onDocumentAnalyzed={handleDocumentAnalyzed}
            onSuccess={notify}
          />
        )}

        {view === 'results' && (
          <AnalysisResults
            taskId={selectedTaskId}
            onBack={handleGoBackToList}
          />
        )}

        {toastMessage && <div className="toast-notification">{toastMessage}</div>}
      </main>
    </div>
  )
}

export default App
