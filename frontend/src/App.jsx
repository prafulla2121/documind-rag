import { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import UploadPanel from './components/UploadPanel';
import ProfileView from './components/ProfileView';
import Auth from './components/Auth';
import { REPO_URL, getDemoInfo, getStats } from './lib/api';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ChatProvider } from './context/ChatContext';
import { GoogleOAuthProvider } from '@react-oauth/google';

const WAKE_GIVE_UP_MS = 180000;

// Free hosting sleeps when idle; keep asking until the backend answers instead of showing a broken page.
function useBackendInfo() {
  const [info, setInfo] = useState(null);
  const [failed, setFailed] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const started = Date.now();
    const tick = setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000);
    (async () => {
      while (!cancelled && Date.now() - started < WAKE_GIVE_UP_MS) {
        try {
          const data = await getDemoInfo();
          if (!cancelled) setInfo(data);
          return;
        } catch {
          await new Promise(r => setTimeout(r, 3000));
        }
      }
      if (!cancelled) setFailed(true);
    })().finally(() => clearInterval(tick));
    return () => { cancelled = true; clearInterval(tick); };
  }, [attempt]);

  const retry = useCallback(() => { setFailed(false); setElapsed(0); setAttempt(a => a + 1); }, []);
  return { info, failed, elapsed, retry };
}

function WakeScreen({ failed, elapsed, onRetry }) {
  return (
    <div className="wake-screen">
      <div className="wake-card" role="status" aria-live="polite">
        <h1>DocuMind</h1>
        <p className="wake-lead">Ask questions about documents and get answers with cited sources.</p>
        {failed ? (
          <>
            <p className="wake-error">The demo server did not answer. It may be restarting.</p>
            <button className="btn-primary" onClick={onRetry}>Try again</button>
          </>
        ) : (
          <>
            <div className="wake-progress"><span className="spinner-dark" aria-hidden="true" /> Waking up the server… {elapsed}s</div>
            <p className="wake-note">The free server sleeps when nobody uses it. The first visit can take about a minute.</p>
          </>
        )}
        <a className="wake-link" href={REPO_URL} target="_blank" rel="noreferrer">View the code on GitHub</a>
      </div>
    </div>
  );
}

function MainApp({ googleEnabled = false }) {
  const [activeView, setActiveView] = useState('chat');
  const [stats, setStats] = useState(null);
  const { user, loading } = useAuth();
  const backend = useBackendInfo();
  const demo = backend.info?.demo_mode ? backend.info : null;

  const fetchStats = async () => {
    try {
      const data = await getStats();
      setStats(data);
    } catch {
      setStats(null);
    }
  };

  useEffect(() => {
    if (!backend.info) return undefined;
    fetchStats();
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, [backend.info]);

  // Other components ask to switch views with a 'navigate' event (e.g. the model picker → settings).
  useEffect(() => {
    const onNavigate = (e) => setActiveView(e.detail);
    window.addEventListener('navigate', onNavigate);
    return () => window.removeEventListener('navigate', onNavigate);
  }, []);

  if (!backend.info) {
    return <WakeScreen failed={backend.failed} elapsed={backend.elapsed} onRetry={backend.retry} />;
  }

  if (loading) {
    return <div className="loading-screen">Loading application...</div>;
  }

  // The public demo needs no account: every visitor is a guest on the shared sample data.
  if (!user && !demo) {
    return <Auth googleEnabled={googleEnabled} />;
  }

  return (
    <div className="app">
      <Sidebar
        activeView={activeView}
        onNavigate={setActiveView}
        stats={stats}
        demo={demo}
      />
      {activeView === 'chat' && <ChatWindow demo={demo} />}
      {activeView === 'upload' && <UploadPanel onUploadComplete={fetchStats} demo={demo} />}
      {activeView === 'profile' && !demo && <ProfileView />}
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
