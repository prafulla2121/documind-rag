import { useAuth } from '../context/AuthContext';
import { useChat } from '../context/ChatContext';
import { useEffect, useState } from 'react';
import { API_BASE } from '../lib/api';

const systemTheme = () => (window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');

export default function Sidebar({ activeView, onNavigate, stats, demo = null }) {
  const { user, logout } = useAuth();
  const { sessions, currentSessionId, setCurrentSessionId, createNewChat, fetchSessions, isLoadingSessions } = useChat();
  // No saved choice = follow the OS setting (CSS prefers-color-scheme).
  const [theme, setTheme] = useState(localStorage.getItem('theme'));
  const [sidebarSearch, setSidebarSearch] = useState('');

  useEffect(() => {
    fetchSessions();
  }, [activeView, currentSessionId]);

  useEffect(() => {
    if (theme) document.documentElement.setAttribute('data-theme', theme);
    else document.documentElement.removeAttribute('data-theme');
  }, [theme]);

  const effectiveTheme = theme || systemTheme();
  const toggleTheme = () => {
    const newTheme = effectiveTheme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
  };

  const handleTogglePin = async (e, sessionId) => {
    e.stopPropagation();
    try {
      await fetch(`${API_BASE}/query/sessions/${sessionId}/pin`, {
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
          <h1>DocuMind</h1>
          {demo && <span className="demo-tag">Demo</span>}
        </div>
      </div>

      <button className="new-chat-btn" onClick={handleNewChat} aria-label="New chat">
        <span aria-hidden="true">+</span><span className="new-chat-label">New chat</span>
      </button>

      <nav className="sidebar-nav">
        {!demo && (
          <div className="sidebar-search">
            <input
              type="text"
              placeholder="Search chats..."
              aria-label="Search chats"
              value={sidebarSearch}
              onChange={(e) => setSidebarSearch(e.target.value)}
            />
          </div>
        )}
        <button
          className={`nav-item ${activeView === 'chat' ? 'active' : ''}`}
          onClick={() => onNavigate('chat')}
        >
          Chat
        </button>
        <button
          className={`nav-item ${activeView === 'upload' ? 'active' : ''}`}
          onClick={() => onNavigate('upload')}
        >
          Documents
        </button>

        {!demo && (
          <>
            <div className="nav-group-label">Recents</div>
            <div className="chat-history-list">
              {isLoadingSessions ? (
                <div className="history-empty">Loading history...</div>
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
                  >
                    <span className="history-title">
                      {session.title}
                    </span>
                    <button
                      className={`pin-btn ${session.is_pinned ? 'pinned' : ''}`}
                      onClick={(e) => handleTogglePin(e, session.id)}
                      title={session.is_pinned ? 'Unpin' : 'Pin'}
                    >
                      {session.is_pinned ? 'Pinned' : 'Pin'}
                    </button>
                  </div>
                ))
              ) : (
                <div className="history-empty">No recent chats</div>
              )}
            </div>
          </>
        )}
      </nav>

      <div className="sidebar-footer">
        <button className="nav-item" onClick={toggleTheme}>
          {effectiveTheme === 'light' ? 'Dark mode' : 'Light mode'}
        </button>
        {demo ? (
          <div className="user-profile static">
            <div className="avatar">G</div>
            <div className="username-container">
              <span className="username">Guest</span>
              <span className="plan-type">Public demo, no sign-in</span>
            </div>
          </div>
        ) : (
          <div className="user-profile" onClick={() => onNavigate('profile')} title="View Profile">
            <div className="avatar">{user?.username?.charAt(0).toUpperCase()}</div>
            <div className="username-container">
              <span className="username">{user?.username}</span>
              <span className="plan-type">Free plan</span>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
