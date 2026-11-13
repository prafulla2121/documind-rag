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
  pdf: 'PDF',
  docx: 'DOC',
  html: 'WEB',
  htm: 'WEB',
  txt: 'TXT',
  md: 'MD',
  csv: 'CSV',
};

export default function UploadPanel({ onUploadComplete, demo = null }) {
  const [activeTab, setActiveTab] = useState('files');
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCollection, setActiveCollection] = useState('all');
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
    // Check the size here too, so a visitor does not wait for a large upload the server will refuse.
    const maxMb = demo?.max_upload_mb;
    const tooBig = maxMb ? Array.from(files).find(f => f.size > maxMb * 1024 * 1024) : null;
    if (tooBig) {
      setUploadStatus({ type: 'error', message: `${tooBig.name} is larger than ${maxMb} MB, the demo limit.` });
      return;
    }
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
    return FILE_TYPE_ICONS[ext] || 'FILE';
  };

  return (
    <div className="upload-panel">
      <div className="upload-section">
        <h3>Documents</h3>
        <p>The documents the assistant searches when it answers.</p>
        {demo && (
          <div className="demo-notice">
            On the demo you can upload files up to {demo.max_upload_mb} MB (PDF, DOCX, TXT, MD, HTML, CSV).
            Website, sitemap and YouTube import are turned off here; they work in the full local setup.
            Uploads are visible to other visitors until the server restarts.
          </div>
        )}

        {!demo && <div className="upload-tabs" role="tablist" aria-label="Ingestion sources">
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
        </div>}

        {activeTab === 'files' ? (
          <>
        <div className={`ingest-methods ${demo ? 'single' : ''}`}>
          {/* URL Ingest (server-side fetching is off on the public demo) */}
          {!demo && <div className="url-ingest-box">
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
          </div>}

          {/* Dropzone */}
          <div
            className={`dropzone ${dragOver ? 'drag-over' : ''}`}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInputRef.current?.click(); } }}
            onClick={() => fileInputRef.current?.click()}
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
          >
            <h4>{uploading ? 'Uploading…' : 'Upload files'}</h4>
            <span className="dropzone-hint">Drop files here or click to choose. PDF, DOCX, TXT, MD, HTML, CSV.</span>
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
          <div className={`status-banner ${uploadStatus.type}`} role="status">
            {uploadStatus.message}
          </div>
        )}

        {Object.keys(taskStatuses).length > 0 && (
          <div className="task-list">
            {Object.entries(taskStatuses).map(([taskId, task]) => (
              <div key={taskId} className="task-item">
                <div className="task-label">
                  Task {taskId.slice(0, 8)} - {task.status}{task.error && `: ${task.error}`}
                </div>
                <div className="task-bar">
                  <div style={{ width: `${task.progress || 0}%` }} />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Document List */}
        <div className="documents-section">
          {!demo && <div className="collection-chips">
            {['all', 'default', 'research', 'legal', 'finance'].map(c => (
              <button
                key={c}
                onClick={() => setActiveCollection(c)}
                className={activeCollection === c ? 'active' : ''}
              >
                {c.charAt(0).toUpperCase() + c.slice(1)}
              </button>
            ))}
          </div>}

          <div className="documents-toolbar">
            <h4>Indexed documents ({documents.length})</h4>
            <input
              type="text"
              placeholder="Search documents..."
              aria-label="Search documents"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div className="doc-list">
            {documents.filter(doc => {
              const matchesSearch = doc.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
                (doc.title && doc.title.toLowerCase().includes(searchQuery.toLowerCase()));
              const matchesCollection = activeCollection === 'all' || doc.collection_id === activeCollection;
              return matchesSearch && matchesCollection;
            }).map((doc) => (
              <div key={doc.id} className="doc-item">
                <div className="doc-icon">{getFileIcon(doc.filename)}</div>
                <div className="doc-info">
                  <div className="doc-name" title={doc.filename}>{doc.filename}</div>
                  <div className="doc-meta">
                    {doc.num_chunks} chunks · {doc.source_type?.toUpperCase()}
                  </div>
                </div>
                <div className={`doc-status ${doc.status}`}>{doc.status}</div>
                {!demo && <div className="doc-actions">
                  {doc.source_type === 'web' && (
                    <button type="button" onClick={() => handleReindexDocument(doc)} title="Re-index source">
                      Re-index
                    </button>
                  )}
                  <button type="button" onClick={() => handleDeleteDocument(doc.id)} title="Delete source">
                    Delete
                  </button>
                </div>}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
