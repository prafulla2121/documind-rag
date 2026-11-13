import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { API_BASE } from '../lib/api';

export default function ChatModelSelector({ readOnly = false }) {
  const [config, setConfig] = useState(null);
  const [isOpen, setIsOpen] = useState(false);
  const { user } = useAuth();

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        // Signed-out visitors (the public demo) get the server's default model.
        const token = localStorage.getItem('token');
        const res = await fetch(`${API_BASE}/models/config`, {
          headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        const data = await res.json();
        if (data && data.provider) {
          setConfig(data);
        }
      } catch (err) {
        console.error("Failed to load model config", err);
      }
    };

    fetchConfig();
    
    // Listen for config changes from ProfileView
    const handleConfigChange = () => fetchConfig();
    window.addEventListener('modelConfigChanged', handleConfigChange);
    return () => window.removeEventListener('modelConfigChanged', handleConfigChange);
  }, []);

  if (!config) {
    return <div className="model-badge">Loading model...</div>;
  }
  if (readOnly) {
    return <div className="model-badge" title="Model used by the demo server">{config.model_name}</div>;
  }

  const modelLabel = config.model_name || "Llama 3";
  const providerLabel = config.provider === 'gemini' ? 'Gemini' : 
                        config.provider === 'ollama' ? 'Ollama' :
                        config.provider === 'anthropic' ? 'Claude' :
                        config.provider === 'openai' ? 'GPT' : 'Model';

  return (
    <div className="chat-model-selector-container">
      <div 
        className="model-badge clickable" 
        onClick={() => setIsOpen(!isOpen)}
        title="Change AI model in settings"
      >
        {modelLabel}
      </div>
      
      {isOpen && (
        <div className="model-selector-popover">
          <div className="popover-header">Current Model</div>
          <div className="popover-item active">
            <div className="item-title">{modelLabel}</div>
            <div className="item-subtitle">{providerLabel} provider</div>
          </div>
          <div className="popover-divider"></div>
          <div className="popover-footer" onClick={() => {
              // Trigger navigation to profile
              window.dispatchEvent(new CustomEvent('navigate', { detail: 'profile' }));
              setIsOpen(false);
          }}>
            Change model in settings
          </div>
        </div>
      )}
    </div>
  );
}
