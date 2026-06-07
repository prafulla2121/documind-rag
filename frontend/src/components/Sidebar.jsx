import { useAuth } from '../context/AuthContext';
import { useChat } from '../context/ChatContext';
import { useEffect, useState } from 'react';

export default function Sidebar({ activeView, onNavigate, stats }) {
  const { user, logout } = useAuth();
  const { sessions, currentSessionId, setCurrentSessionId, createNewChat, fetchSessions, isLoadingSessions } = useChat();
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'light');
  const [sidebarSearch, setSidebarSearch] = useState('');

  useEffect(() => {
    fetchSessions();
    document.documentElement.setAttribute('data-theme', theme);
  }, [activeView, currentSessionId, theme]);

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
  };

  const handleTogglePin = async (e, sessionId) => {
    e.stopPropagation();
    try {
      await fetch(`http://localhost:8000/api/query/sessions/${sessionId}/pin`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      fetchSessions();
    } catch (err) {
      console.error(err);
    }
  };

  const handleNewChat = () => {
    createNewChat();
    onNavigate('chat');
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo-text">
          <h1>RagSystem</h1>
        </div>
      </div>

      <button className="new-chat-btn" onClick={handleNewChat}>
        <span style={{fontSize: '18px'}}>+</span> New chat
      </button>

      <nav className="sidebar-nav">
        <div style={{ padding: '0 12px 16px' }}>
          <input
            type="text"
            placeholder="Search chats..."
            value={sidebarSearch}
            onChange={(e) => setSidebarSearch(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 12px',
              borderRadius: '8px',
              border: '1px solid var(--sidebar-border)',
              backgroundColor: 'var(--bg-color)',
              color: 'var(--text-main)',
              fontSize: '13px'
            }}
          />
        </div>
        <button 
          className={`nav-item ${activeView === 'chat' ? 'active' : ''}`}
          onClick={() => onNavigate('chat')}
        >
          <span className="nav-item-icon">💬</span> Chats
        </button>
        <button 
          className={`nav-item ${activeView === 'upload' ? 'active' : ''}`}
          onClick={() => onNavigate('upload')}
        >
          <span className="nav-item-icon">📁</span> Projects
        </button>

        <div className="nav-group-label">Recents</div>
        <div className="chat-history-list">
          {isLoadingSessions ? (
            <div style={{ padding: '8px 12px', fontSize: '12px', color: '#999' }}>
              Loading history...
            </div>
          ) : sessions.length > 0 ? (
            sessions
              .filter(s => s.title.toLowerCase().includes(sidebarSearch.toLowerCase()))
              .map(session => (
              <div 
                key={session.id} 
                className={`history-item ${currentSessionId === session.id && activeView === 'chat' ? 'active' : ''}`}
                onClick={() => {
                  setCurrentSessionId(session.id);
                  onNavigate('chat');
                }}
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              >
                <span className="history-title" style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {session.is_pinned && <span style={{ marginRight: '6px' }}>📌</span>}
                  {session.title}
                </span>
                <button
                  className="pin-btn"
                  onClick={(e) => handleTogglePin(e, session.id)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '12px', opacity: 0.5 }}
                >
                  {session.is_pinned ? '📍' : '📌'}
                </button>
              </div>
            ))
          ) : (
            <div style={{ padding: '8px 12px', fontSize: '12px', color: '#999', fontStyle: 'italic' }}>
              No recent chats
            </div>
          )}
        </div>
      </nav>

      <div className="sidebar-footer">
        <button
          className="nav-item"
          onClick={toggleTheme}
          style={{ marginBottom: '8px' }}
        >
          <span className="nav-item-icon">{theme === 'light' ? '🌙' : '☀️'}</span>
          {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
        </button>
        <div className="user-profile" onClick={() => onNavigate('profile')} title="View Profile" style={{ cursor: 'pointer' }}>
          <div className="avatar">{user?.username?.charAt(0).toUpperCase()}</div>
          <div className="username-container">
            <span className="username">{user?.username}</span>
            <span className="plan-type">Free plan</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
