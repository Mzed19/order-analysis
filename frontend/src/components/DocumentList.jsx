import { useState } from 'react'

function DocumentList({ documents, onNewDocument, onViewDocument, onDeleteDocument }) {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [selectedDocId, setSelectedDocId] = useState(null)

  const getStatusBadge = (status) => {
    switch (status) {
      case 'concluido':
        return <span className="badge badge-success">Concluído</span>
      case 'em_analise':
        return <span className="badge badge-info">Em análise</span>
      case 'erro':
        return <span className="badge badge-error">Erro</span>
      default:
        return <span className="badge">{status}</span>
    }
  }

  const openDeleteModal = (id) => {
    setSelectedDocId(id)
    setIsModalOpen(true)
  }

  const closeDeleteModal = () => {
    setIsModalOpen(false)
    setSelectedDocId(null)
  }

  const confirmDelete = () => {
    if (selectedDocId) {
      onDeleteDocument(selectedDocId)
      closeDeleteModal()
    }
  }

  return (
    <div className="document-list-page animate-fade-in">
      <div className="page-header">
        <div className="header-title">
          <h1>Auditoria de Contratos</h1>
          <p className="subtitle">Acompanhe o processamento de seus documentos</p>
          <div className="retention-warning">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            As análises ficam disponíveis por 24 horas e são removidas automaticamente.
          </div>
        </div>
        <button className="btn-action" onClick={onNewDocument}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          Nova Análise
        </button>
      </div>

      <div className="table-container ">
        {documents.length > 0 ? (
          <table className="documents-table">
            <thead>
              <tr>
                <th>Documento</th>
                <th>Upload</th>
                <th>Status</th>
                <th>Etapa</th>
                <th>Progresso</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id}>
                  <td>
                    <div className="doc-name-cell">
                      <div className="doc-icon">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                          <polyline points="14 2 14 8 20 8" />
                        </svg>
                      </div>
                      {doc.name.length > 75 
                        ? <span title={doc.name}>{doc.name.substring(0, 75)}...</span> 
                        : doc.name}
                    </div>
                  </td>
                  <td>{doc.date}</td>
                  <td>{getStatusBadge(doc.status)}</td>
                  <td>{doc.stage}</td>
                  <td>
                    <div className="progress-cell">
                      <div className="progress-bar">
                        <div
                          className="progress-fill"
                          style={{ width: `${doc.progress}%` }}
                        />
                      </div>
                      <span className="progress-text">{doc.progress}%</span>
                    </div>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        className="btn-details"
                        onClick={() => onViewDocument(doc.id)}
                        disabled={doc.status === 'em_analise'}
                        title={doc.status === 'em_analise' ? 'Aguarde a conclusão da análise' : 'Ver detalhes'}
                      >
                        Detalhes
                      </button>
                      <button
                        className="btn-details"
                        style={{ color: 'var(--error)', borderColor: 'rgba(239, 68, 68, 0.2)', padding: '8px' }}
                        onClick={() => openDeleteModal(doc.id)}
                        title="Apagar análise"
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="3 6 5 6 21 6" />
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                          <line x1="10" y1="11" x2="10" y2="17" />
                          <line x1="14" y1="11" x2="14" y2="17" />
                        </svg>
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="analysis-placeholder" style={{ padding: '80px 20px' }}>
            <div className="doc-icon" style={{ width: '64px', height: '64px', marginBottom: '20px' }}>
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
            </div>
            <h3>Nenhum documento encontrado</h3>
            <p>Comece fazendo o upload de um contrato para análise.</p>
            <button className="btn-primary" onClick={onNewDocument} style={{ marginTop: '20px' }}>
              Fazer Primeiro Upload
            </button>
          </div>
        )}
      </div>

      {isModalOpen && (
        <div className="modal-backdrop" onClick={closeDeleteModal}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-icon">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M3 6h18m-2 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                  <line x1="10" y1="11" x2="10" y2="17" />
                  <line x1="14" y1="11" x2="14" y2="17" />
                </svg>
              </div>
              <h2 className="modal-title">Apagar Análise?</h2>
            </div>
            <div className="modal-body">
              Esta ação removerá permanentemente os resultados da análise e os dados associados do servidor. Você não poderá desfazer esta operação.
            </div>
            <div className="modal-actions">
              <button className="btn-cancel" onClick={closeDeleteModal}>Cancelar</button>
              <button className="btn-delete-confirm" onClick={confirmDelete}>Apagar Permanentemente</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default DocumentList
