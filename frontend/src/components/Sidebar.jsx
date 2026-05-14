import { useAuth } from '../context/AuthContext';
import { useChat } from '../context/ChatContext';
import { useEffect } from 'react';

export default function Sidebar({ activeView, onNavigate, stats }) {
  const { user, logout } = useAuth();
  const { sessions, currentSessionId, setCurrentSessionId, createNewChat, fetchSessions, isLoadingSessions } = useChat();

  useEffect(() => {
    fetchSessions();
  }, [activeView, currentSessionId]);

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
            sessions.map(session => (
              <div 
                key={session.id} 
                className={`history-item ${currentSessionId === session.id && activeView === 'chat' ? 'active' : ''}`}
                onClick={() => {
                  setCurrentSessionId(session.id);
                  onNavigate('chat');
                }}
              >
                <span className="history-title">{session.title}</span>
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
        <div className="user-profile" onClick={logout} title="Logout">
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
