import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import UploadPanel from './components/UploadPanel';
import ProfileView from './components/ProfileView';
import Auth from './components/Auth';
import { getStats } from './lib/api';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ChatProvider, useChat } from './context/ChatContext';
import { GoogleOAuthProvider } from '@react-oauth/google';

function MainApp({ googleEnabled = false }) {
  const [activeView, setActiveView] = useState('chat');
  const [stats, setStats] = useState(null);
  const { user, loading } = useAuth();
  const { currentSessionId, setCurrentSessionId } = useChat();

  const fetchStats = async () => {
    try {
      const data = await getStats();
      setStats(data);
    } catch {
      setStats(null);
    }
  };

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return <div className="loading-screen">Loading application...</div>;
  }

  if (!user) {
    return <Auth googleEnabled={googleEnabled} />;
  }

  return (
    <div className="app">
      <Sidebar
        activeView={activeView}
        onNavigate={setActiveView}
        stats={stats}
      />
      {activeView === 'chat' && <ChatWindow />}
      {activeView === 'upload' && <UploadPanel onUploadComplete={fetchStats} />}
      {activeView === 'profile' && <ProfileView />}
    </div>
  );
}

export default function App() {
  const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
  const app = (
    <AuthProvider>
      <ChatProvider>
        <MainApp googleEnabled={Boolean(googleClientId)} />
      </ChatProvider>
    </AuthProvider>
  );

  if (!googleClientId) {
    return app;
  }
  
  return (
    <GoogleOAuthProvider clientId={googleClientId}>
      {app}
    </GoogleOAuthProvider>
  );
}
