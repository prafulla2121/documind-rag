import { useState, useEffect, useRef } from 'react';
import {
  deleteDocument,
  getDocuments,
  getIngestTaskStatus,
  ingestConnector,
  ingestSitemap,
  ingestUrl,
  reindexDocument,
  uploadFile,
} from '../lib/api';
import YouTubeInput from './YouTubeInput';

const FILE_TYPE_ICONS = {
  pdf: '📕',
  docx: '📘',
  html: '🌐',
  htm: '🌐',
  txt: '📝',
  md: '📝',
  csv: '📊',
};

export default function UploadPanel({ onUploadComplete }) {
  const [activeTab, setActiveTab] = useState('files');
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [urlInput, setUrlInput] = useState('');
  const [crawlSite, setCrawlSite] = useState(false);
  const [maxPages, setMaxPages] = useState(10);
  const [sitemapInput, setSitemapInput] = useState('');
  const [taskStatuses, setTaskStatuses] = useState({});
  const fileInputRef = useRef(null);

  const fetchDocuments = async () => {
    try {
      const data = await getDocuments();
      setDocuments(data.documents || []);
    } catch {
      // Backend might not be available
    }
  };

  useEffect(() => {
    fetchDocuments();
    const interval = setInterval(fetchDocuments, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const pendingTaskIds = Object.entries(taskStatuses)
      .filter(([, status]) => status.status === 'queued' || status.status === 'running')
      .map(([taskId]) => taskId);
    if (pendingTaskIds.length === 0) return undefined;
    const interval = setInterval(async () => {
      for (const taskId of pendingTaskIds) {
        try {
          const latest = await getIngestTaskStatus(taskId);
          setTaskStatuses(prev => ({ ...prev, [taskId]: latest }));
        } catch {
          // Ignore transient polling errors
        }
      }
    }, 1500);
    return () => clearInterval(interval);
  }, [taskStatuses]);

  const handleUpload = async (files) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadStatus(null);

    try {
      for (const file of files) {
        const result = await uploadFile(file);
        if (result.task_id) {
          setTaskStatuses(prev => ({ ...prev, [result.task_id]: { status: 'queued', progress: 0 } }));
        }
      }
      setUploadStatus({
        type: 'success',
        message: `${files.length} file(s) queued!`,
      });
      fetchDocuments();
      if (onUploadComplete) onUploadComplete();
    } catch (err) {
      setUploadStatus({
        type: 'error',
        message: `Upload failed: ${err.message}`,
      });
    } finally {
      setUploading(false);
    }
  };

  const handleUrlSubmit = async (e) => {
    e.preventDefault();
    if (!urlInput.trim()) return;
    
    setUploading(true);
    setUploadStatus(null);

    try {
      const result = await ingestUrl(urlInput.trim(), { crawl: crawlSite, maxPages });
      if (result.task_id) {
        setTaskStatuses(prev => ({ ...prev, [result.task_id]: { status: 'queued', progress: 0 } }));
      }
      setUploadStatus({
        type: 'success',
        message: result.task_id ? 'URL queued!' : result.message,
      });
      setUrlInput('');
      fetchDocuments();
      if (onUploadComplete) onUploadComplete();
    } catch (err) {
      setUploadStatus({
        type: 'error',
        message: `URL Ingest failed: ${err.message}`,
      });
    } finally {
      setUploading(false);
    }
  };

  const handleSitemapSubmit = async (e) => {
    e.preventDefault();
    if (!sitemapInput.trim()) return;

    setUploading(true);
    setUploadStatus(null);
    try {
      const result = await ingestSitemap(sitemapInput.trim(), Math.max(maxPages, 10));
      if (result.task_id) {
        setTaskStatuses(prev => ({ ...prev, [result.task_id]: { status: 'queued', progress: 0 } }));
      }
      setUploadStatus({ type: 'success', message: result.message || 'Sitemap queued!' });
      setSitemapInput('');
      fetchDocuments();
      if (onUploadComplete) onUploadComplete();
    } catch (err) {
      setUploadStatus({ type: 'error', message: `Sitemap failed: ${err.message}` });
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDocument = async (docId) => {
    try {
      await deleteDocument(docId);
      setUploadStatus({ type: 'success', message: 'Source deleted.' });
      fetchDocuments();
    } catch (err) {
      setUploadStatus({ type: 'error', message: `Delete failed: ${err.message}` });
    }
  };

  const handleReindexDocument = async (doc) => {
    try {
      const result = await reindexDocument(doc.id);
      if (result.task_id) {
        setTaskStatuses(prev => ({ ...prev, [result.task_id]: { status: 'queued', progress: 0 } }));
      }
      setUploadStatus({ type: 'success', message: 'Re-index queued.' });
      fetchDocuments();
    } catch (err) {
      setUploadStatus({ type: 'error', message: `Re-index failed: ${err.message}` });
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    handleUpload(e.dataTransfer.files);
  };

  const handleYouTubeSuccess = (videoMeta) => {
    setUploadStatus({
      type: 'success',
      message: videoMeta.already_existed
        ? 'This YouTube video is already in your library.'
        : `YouTube transcript loaded: ${videoMeta.chunk_count} chunks created.`,
    });
    fetchDocuments();
    if (onUploadComplete) onUploadComplete();
  };

  const getFileIcon = (filename) => {
    const ext = filename.split('.').pop()?.toLowerCase() || '';
    return FILE_TYPE_ICONS[ext] || '📄';
  };

  return (
    <div className="upload-panel">
      <div className="upload-section">
        <h3>Knowledge Base</h3>
        <p>Configure the documents and data sources used to power your assistant's answers.</p>

        <div className="upload-tabs" role="tablist" aria-label="Ingestion sources">
          <button
            type="button"
            className={activeTab === 'files' ? 'active' : ''}
            onClick={() => setActiveTab('files')}
          >
            Files
          </button>
          <button
            type="button"
            className={activeTab === 'youtube' ? 'active' : ''}
            onClick={() => setActiveTab('youtube')}
          >
            YouTube
          </button>
          <button
            type="button"
            className={activeTab === 'connectors' ? 'active' : ''}
            onClick={() => setActiveTab('connectors')}
          >
            Connectors
          </button>
        </div>

        {activeTab === 'files' ? (
          <>
        <div className="ingest-methods">
          {/* URL Ingest */}
          <div className="url-ingest-box">
            <h4>Add Website</h4>
            <form onSubmit={handleUrlSubmit} className="url-form">
              <input 
                type="text" 
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="example.com or https://example.com"
                required
                disabled={uploading}
              />
              <button type="submit" disabled={uploading || !urlInput.trim()}>
                Add
              </button>
            </form>
            <div className="crawl-controls">
              <label>
                <input
                  type="checkbox"
                  checked={crawlSite}
                  onChange={(e) => setCrawlSite(e.target.checked)}
                  disabled={uploading}
                />
                Crawl same-site links
              </label>
              <input
                type="number"
                min="1"
                max="50"
                value={maxPages}
                onChange={(e) => setMaxPages(Number(e.target.value))}
                disabled={uploading || !crawlSite}
                aria-label="Maximum pages to crawl"
              />
            </div>
            <form onSubmit={handleSitemapSubmit} className="url-form sitemap-form">
              <input
                type="text"
                value={sitemapInput}
                onChange={(e) => setSitemapInput(e.target.value)}
                placeholder="https://example.com/sitemap.xml"
                disabled={uploading}
              />
              <button type="submit" disabled={uploading || !sitemapInput.trim()}>
                Sitemap
              </button>
            </form>
          </div>

          {/* Dropzone */}
          <div
            className={`dropzone ${dragOver ? 'drag-over' : ''}`}
            onClick={() => fileInputRef.current?.click()}
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
          >
            <div className="dropzone-icon">📁</div>
            <h4>Upload Files</h4>
            <span style={{fontSize: '12px', color: '#999'}}>PDF, DOCX, TXT, etc.</span>
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.html,.htm,.txt,.md,.csv"
          style={{ display: 'none' }}
          onChange={(e) => handleUpload(e.target.files)}
        />
          </>
        ) : activeTab === 'youtube' ? (
          <YouTubeInput onSuccess={handleYouTubeSuccess} />
        ) : (
          <div className="connector-grid">
            {[
              ['confluence', 'Confluence'],
              ['notion', 'Notion'],
              ['google_drive', 'Google Drive'],
              ['sharepoint', 'SharePoint'],
            ].map(([id, label]) => (
              <button
                key={id}
                type="button"
                className="connector-card"
                onClick={async () => {
                  try {
                    await ingestConnector(id);
                  } catch (err) {
                    setUploadStatus({ type: 'error', message: err.message });
                  }
                }}
              >
                <span>{label}</span>
                <small>Setup required</small>
              </button>
            ))}
          </div>
        )}

        {/* Upload Status */}
        {uploadStatus && (
          <div style={{
            padding: '12px', 
            borderRadius: '8px', 
            marginBottom: '24px',
            fontSize: '14px',
            backgroundColor: uploadStatus.type === 'success' ? '#d1fae5' : '#fee2e2',
            color: uploadStatus.type === 'success' ? '#065f46' : '#991b1b'
          }}>
            {uploadStatus.message}
          </div>
        )}

        {Object.keys(taskStatuses).length > 0 && (
          <div style={{ marginBottom: '20px', display: 'grid', gap: '8px' }}>
            {Object.entries(taskStatuses).map(([taskId, task]) => (
              <div key={taskId} style={{ border: '1px solid #eee', borderRadius: '8px', padding: '8px 10px' }}>
                <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>
                  Task {taskId.slice(0, 8)} - {task.status}
                </div>
                <div style={{ height: '6px', background: '#f1f1f1', borderRadius: '999px', overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${task.progress || 0}%`, background: '#d97757' }} />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Document List */}
        <div className="documents-section">
          <h4>Ingested Sources ({documents.length})</h4>
          <div className="doc-list">
            {documents.map((doc) => (
              <div key={doc.id} className="doc-item">
                <div className="doc-icon">{getFileIcon(doc.filename)}</div>
                <div className="doc-info">
                  <div className="doc-name" title={doc.filename}>{doc.filename}</div>
                  <div className="doc-meta">
                    {doc.num_chunks} chunks • {doc.source_type?.toUpperCase()}
                  </div>
                </div>
                <div className={`doc-status ${doc.status}`}>{doc.status}</div>
                <div className="doc-actions">
                  {doc.source_type === 'web' && (
                    <button type="button" onClick={() => handleReindexDocument(doc)} title="Re-index source">
                      Re-index
                    </button>
                  )}
                  <button type="button" onClick={() => handleDeleteDocument(doc.id)} title="Delete source">
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
