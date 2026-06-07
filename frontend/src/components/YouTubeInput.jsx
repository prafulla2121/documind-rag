import { useState } from 'react';
import { ingestYouTube } from '../lib/api';

export default function YouTubeInput({ onSuccess }) {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [videoMeta, setVideoMeta] = useState(null);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;

    setLoading(true);
    setError('');
    setVideoMeta(null);

    try {
      const result = await ingestYouTube(trimmed);
      setVideoMeta(result);
      setUrl('');
      if (onSuccess) onSuccess(result);
    } catch (err) {
      setError(err.message || 'Unable to load this YouTube transcript.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="youtube-ingest">
      <form onSubmit={handleSubmit} className="youtube-form">
        <div className="youtube-input-wrap">
          <label htmlFor="youtube-url">YouTube URL</label>
          <input
            id="youtube-url"
            type="text"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="youtu.be/video-id or youtube.com/watch?v=video-id"
            disabled={loading}
            required
          />
        </div>
        <button type="submit" disabled={loading || !url.trim()}>
          {loading && <span className="spinner" aria-hidden="true" />}
          {loading ? 'Loading...' : 'Load Transcript'}
        </button>
      </form>

      {error && <div className="youtube-alert">{error}</div>}

      {videoMeta && (
        <div className="youtube-result-card">
          <img src={videoMeta.thumbnail_url} alt="" />
          <div className="youtube-result-info">
            <div className="youtube-result-title">{videoMeta.title}</div>
            <div className="youtube-result-meta">
              {videoMeta.channel_name} • {videoMeta.chunk_count} chunks
            </div>
            {videoMeta.already_existed && (
              <span className="youtube-badge">Already in your library</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
