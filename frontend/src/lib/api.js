/**
 * API Client — handles all backend communication.
 * Uses Vite proxy in dev (/api → http://localhost:8000/api)
 */

const API_BASE = '/api';

const getAuthHeaders = (headers = {}) => {
  const token = localStorage.getItem('token');
  if (token) {
    return { ...headers, 'Authorization': `Bearer ${token}` };
  }
  return headers;
};

export const apiCall = async (endpoint, options = {}) => {
  console.log(`[API] calling ${API_BASE}${endpoint}`);
  const headers = getAuthHeaders({
    'Content-Type': 'application/json',
    ...options.headers,
  });

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });
  if (!res.ok) throw new Error(`API call failed: ${res.statusText}`);
  return res.json();
}

/**
 * Send a query (non-streaming) and get the full response.
 */
export async function sendQuery(query, filters = {}, sessionId = null) {
  const body = { query, stream: false, filters };
  if (sessionId) body.session_id = sessionId;
  
  const res = await fetch(`${API_BASE}/query/`, {
    method: 'POST',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Query failed: ${res.statusText}`);
  return res.json();
}

/**
 * Send a query with streaming — yields SSE events.
 */
export async function* streamQuery(query, filters = {}, sessionId = null, options = {}) {
  const body = { query, stream: true, filters };
  if (sessionId) body.session_id = sessionId;

  const res = await fetch(`${API_BASE}/query/`, {
    method: 'POST',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
    signal: options.signal,
  });

  if (!res.ok) throw new Error(`Query failed: ${res.statusText}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const event = JSON.parse(line.slice(6));
          yield event;
        } catch {
          // skip malformed lines
        }
      }
    }
  }
}

/**
 * Upload a file for ingestion.
 */
export async function uploadFile(file) {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/ingest/upload`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
  return res.json();
}

/**
 * Upload multiple files.
 */
export async function uploadMultipleFiles(files) {
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }

  const res = await fetch(`${API_BASE}/ingest/upload-multiple`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
  return res.json();
}

export async function ingestUrl(url) {
  const res = await fetch(`${API_BASE}/ingest/url`, {
    method: 'POST',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error(`URL Ingest failed: ${res.statusText}`);
  return res.json();
}

export async function getIngestTaskStatus(taskId) {
  const res = await fetch(`${API_BASE}/ingest/tasks/${taskId}`, {
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error(`Failed to get task status: ${res.statusText}`);
  return res.json();
}

/**
 * Get list of ingested documents.
 */
export async function getDocuments() {
  const res = await fetch(`${API_BASE}/ingest/documents`, {
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error(`Failed to get documents: ${res.statusText}`);
  return res.json();
}

/**
 * Get system stats.
 */
export async function getStats() {
  const res = await fetch(`${API_BASE}/admin/stats`, {
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error(`Failed to get stats: ${res.statusText}`);
  return res.json();
}

/**
 * Health check.
 */
export async function healthCheck() {
  try {
    const res = await fetch('/health');
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Chat History
 */
export async function getChatSessions() {
  const res = await fetch(`${API_BASE}/query/sessions`, {
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error(`Failed to get sessions: ${res.statusText}`);
  return res.json();
}

export async function getSessionMessages(sessionId) {
  const res = await fetch(`${API_BASE}/query/sessions/${sessionId}/messages`, {
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error(`Failed to get messages: ${res.statusText}`);
  return res.json();
}

export async function deleteChatSession(sessionId) {
  const res = await fetch(`${API_BASE}/query/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: getAuthHeaders()
  });
  if (!res.ok) throw new Error(`Failed to delete session: ${res.statusText}`);
  return res.json();
}
