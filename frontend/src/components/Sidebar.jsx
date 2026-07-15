import { useState } from 'react'

function Sidebar({ currentView, onNavigate, collapsed, onToggleCollapse }) {
  const userName = 'Usuário';
  const userInitials = 'US';

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-brand">
        <h1>O<span>rder</span>AI</h1>
        {!collapsed && <span>Análise de Crédito</span>}
      </div>

      <nav className="sidebar-nav">
        <button
          className={`nav-item ${currentView === 'list' ? 'active' : ''}`}
          onClick={() => onNavigate('list')}
          title="Pedidos"
        >
          <div className="icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
          </div>
          <span>Pedidos</span>
        </button>

        <button
          className={`nav-item ${currentView === 'new' ? 'active' : ''}`}
          onClick={() => onNavigate('new')}
          title="Nova Análise"
        >
          <div className="icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 5v14M5 12h14" />
            </svg>
          </div>
          <span>Nova Análise</span>
        </button>

        <button
          className={`nav-item ${currentView === 'chat' ? 'active' : ''}`}
          onClick={() => onNavigate('chat')}
          title="Chat"
        >
          <div className="icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <span>Chat</span>
        </button>
      </nav>

      <div className="sidebar-user">
        <div className="user-avatar">
          {userInitials}
        </div>
        {!collapsed && (
          <div className="user-info">
            <span className="user-name">{userName}</span>
            <span className="user-role">Acesso Verificado</span>
          </div>
        )}
      </div>

      <div className="sidebar-footer">
        <button className="nav-item collapse-btn" onClick={onToggleCollapse} title={collapsed ? "Expandir menu" : "Recolher menu"}>
          <div className="icon">
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{ transition: 'transform 0.3s ease', transform: collapsed ? 'rotate(180deg)' : 'rotate(0deg)' }}
            >
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </div>
          <span>{collapsed ? 'Expandir' : 'Recolher'}</span>
        </button>
        {/* No authentication logout button removed */}
      </div>
    </aside>
  )
}

export default Sidebar
