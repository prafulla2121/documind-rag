export default function SourceCitation({ source }) {
  if (source.source_type === 'youtube') {
    const videoId = source.video_id;
    const title = source.video_title || source.title || 'YouTube video';
    const displayTitle = title.length > 40 ? `${title.slice(0, 37)}...` : title;
    const timestamp = source.timestamp || '0:00';
    const url = source.url || `https://youtu.be/${videoId}?t=${Math.floor(source.start_seconds || 0)}`;

    return (
      <div className="source-item youtube-source-item">
        <span className="youtube-play-icon">Play</span>
        <span className="source-title" title={title}>{displayTitle}</span>
        <a
          className="youtube-time-link"
          href={url}
          target="_blank"
          rel="noreferrer"
          onClick={(event) => event.stopPropagation()}
        >
          {timestamp}
        </a>
        {videoId && (
          <div className="youtube-tooltip">
            <img src={`https://img.youtube.com/vi/${videoId}/mqdefault.jpg`} alt="" />
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="source-item">
      <span className="source-badge">S{source.index}</span>
      <span className="source-title">{source.title || 'Document'}</span>
      {source.section && (
        <span className="source-section">- {source.section}</span>
      )}
    </div>
  );
}

