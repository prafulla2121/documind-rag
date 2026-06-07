import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";

export default function ModelSelector({ onConfigChange }) {
  const { user } = useAuth();
  const [catalog, setCatalog] = useState({});
  const [provider, setProvider] = useState("ollama");
  const [model, setModel] = useState("llama3");
  const [apiKey, setApiKey] = useState("");
  const [apiBaseUrl, setApiBaseUrl] = useState("http://localhost:11434");
  const [validating, setValidating] = useState(false);
  const [valid, setValid] = useState(null);

  // Load catalog on mount
  useEffect(() => {
    fetch("/api/models/catalog")
      .then((r) => r.json())
      .then((d) => {
        if (d && d.providers) {
          setCatalog(d.providers);
        }
      })
      .catch((err) => console.error("Failed to load model catalog", err));
      
    // Load existing config if user logged in
    const token = localStorage.getItem("token");
    if (token) {
        fetch("/api/models/config", {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        })
        .then(r => r.json())
        .then(d => {
            if (d && d.provider) {
                setProvider(d.provider);
                setModel(d.model_name);
                setApiKey(d.api_key || "");
                setApiBaseUrl(d.api_base_url || "");
            }
        })
        .catch(err => console.error("Failed to load user config", err));
    }
  }, []);

  const validateAndSave = async () => {
    setValidating(true);
    const configData = { provider, model_name: model, api_key: apiKey, api_base_url: apiBaseUrl, temperature: 0.1 };
    const token = localStorage.getItem("token");
    
    try {
      // First validate
      const res = await fetch("/api/models/validate", {
        method: "POST",
        headers: { 
            "Content-Type": "application/json",
            "Authorization": token ? `Bearer ${token}` : "" 
        },
        body: JSON.stringify(configData)
      });
      
      const data = await res.json();
      
      if (res.ok && data.valid) {
        setValid(true);
        
        // If valid, save it
        await fetch("/api/models/save", {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                "Authorization": token ? `Bearer ${token}` : "" 
            },
            body: JSON.stringify(configData)
        });
        
        if (onConfigChange) {
            onConfigChange(configData);
        }
        
        // Notify other components (like ChatWindow)
        window.dispatchEvent(new CustomEvent('modelConfigChanged'));
      } else {
        setValid(false);
      }
    } catch {
      setValid(false);
    }
    setValidating(false);
  };

  const currentProvider = catalog[provider];

  return (
    <div className="model-selector" style={{ background: '#fff', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '24px', marginBottom: '24px' }}>
      <h3 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '20px', color: 'var(--text-main)' }}>🤖 AI Model Settings</h3>

      <div style={{ marginBottom: '16px' }}>
        <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '6px' }}>Provider</label>
        <select
          value={provider}
          onChange={e => { 
            setProvider(e.target.value); 
            const defaultModel = catalog[e.target.value]?.models[0] || "";
            setModel(defaultModel); 
            setValid(null); 
          }}
          style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border-color)', fontSize: '14px' }}
        >
          {Object.entries(catalog).map(([key, val]) => (
            <option key={key} value={key}>{val.label}</option>
          ))}
        </select>
      </div>

      {currentProvider && (
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '6px' }}>Model</label>
          {currentProvider.models.length > 0 ? (
            <select 
              value={model} 
              onChange={e => setModel(e.target.value)} 
              style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border-color)', fontSize: '14px' }}
            >
              {currentProvider.models.map(m => {
                const isFree = currentProvider.free_models?.includes(m);
                return (
                  <option key={m} value={m}>
                    {m}{isFree ? ' ⚡ FREE' : ''}
                  </option>
                );
              })}
            </select>
          ) : (
            <input
              value={model}
              onChange={e => setModel(e.target.value)}
              placeholder="Enter model name..."
              style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border-color)', fontSize: '14px' }}
            />
          )}
        </div>
      )}

      {currentProvider?.key_required && (
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '6px' }}>
            API Key{" "}
            {currentProvider.key_url && (
              <a href={currentProvider.key_url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-color)', fontSize: '12px', marginLeft: '8px' }}>
                Get key &rarr;
              </a>
            )}
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={e => { setApiKey(e.target.value); setValid(null); }}
            placeholder="Paste your API key..."
            style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border-color)', fontFamily: 'monospace', fontSize: '14px' }}
          />
          {currentProvider?.free_models?.includes(model) && (
            <p style={{ 
                color: '#166534', 
                fontSize: '12px', 
                marginTop: '10px', 
                background: '#f0fdf4', 
                padding: '10px 12px', 
                borderRadius: '10px',
                border: '1px solid #bbf7d0',
                lineHeight: '1.4'
            }}>
              ⚡ <strong>{model}</strong> is a <strong>FREE</strong> model. 
              {provider === 'gemini' && " Get your key from Google AI Studio (no billing required)."}
              {provider === 'groq' && " Groq offers this model for free within their rate limits."}
              {provider === 'ollama' && " Running locally on your machine—no internet or keys needed."}
            </p>
          )}
        </div>
      )}

      {(provider === "custom" || provider === "ollama") && (
        <div style={{ marginBottom: '20px' }}>
          <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '6px' }}>API Base URL</label>
          <input
            value={apiBaseUrl}
            onChange={e => setApiBaseUrl(e.target.value)}
            placeholder="http://localhost:11434"
            style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border-color)', fontFamily: 'monospace', fontSize: '14px' }}
          />
        </div>
      )}

      <button
        onClick={validateAndSave}
        disabled={validating || (!apiKey && currentProvider?.key_required)}
        style={{ 
          width: '100%', 
          padding: '12px', 
          backgroundColor: (validating || (!apiKey && currentProvider?.key_required)) ? '#cccccc' : 'var(--accent-color)', 
          color: '#fff', 
          border: 'none', 
          borderRadius: '6px', 
          fontWeight: '600', 
          cursor: (validating || (!apiKey && currentProvider?.key_required)) ? 'not-allowed' : 'pointer' 
        }}
      >
        {validating ? "Testing..." : "✓ Test & Save Configuration"}
      </button>

      {valid === true && <p style={{ color: '#2e7d32', fontSize: '14px', marginTop: '12px', fontWeight: '500' }}>✅ Configuration saved successfully!</p>}
      {valid === false && <p style={{ color: '#d32f2f', fontSize: '14px', marginTop: '12px', fontWeight: '500' }}>❌ Connection failed. Check your API key or model name.</p>}
    </div>
  );
}
