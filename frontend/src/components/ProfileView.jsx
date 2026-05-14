import { useAuth } from '../context/AuthContext';
import { getStats } from '../lib/api';
import { useState, useEffect } from 'react';

export default function ProfileView() {
  const { user, logout } = useAuth();
  const [stats, setStats] = useState(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await getStats();
        setStats(data);
      } catch (err) {
        console.error("Failed to load stats", err);
      }
    };
    fetchStats();
  }, []);

  return (
    <div className="profile-view">
      <div className="profile-container">
        <div className="profile-header">
          <h2>Settings & Profile</h2>
          <p>Manage your account settings and view system usage.</p>
        </div>

        <div className="profile-card">
          <h3>Account Information</h3>
          <div className="profile-user-info">
            <div className="profile-avatar-large">
              {user?.username?.charAt(0).toUpperCase()}
            </div>
            <div className="profile-details">
              <h4>{user?.username}</h4>
              <p>Standard Workspace Plan</p>
            </div>
          </div>
        </div>

        <div className="profile-card">
          <h3>Usage Statistics</h3>
          <div className="profile-stats-grid">
            <div className="stat-box">
              <div className="stat-label">Total Queries Executed</div>
              <div className="stat-value">{stats ? stats.total_queries : '-'}</div>
            </div>
            <div className="stat-box">
              <div className="stat-label">Documents Indexed</div>
              <div className="stat-value">{stats ? stats.documents : '-'}</div>
            </div>
            <div className="stat-box">
              <div className="stat-label">Storage Region</div>
              <div className="stat-value" style={{ fontSize: '18px', paddingTop: '10px' }}>US-East (Local)</div>
            </div>
          </div>
        </div>

        <div className="profile-danger-zone">
          <h3>Session Management</h3>
          <p style={{ color: '#666', fontSize: '14px', marginBottom: '16px' }}>
            Logging out will clear your active session on this device.
          </p>
          <button onClick={logout} className="btn-signout">
            Sign Out Securely
          </button>
        </div>
      </div>
    </div>
  );
}
