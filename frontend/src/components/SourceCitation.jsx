export default function SourceCitation({ source }) {
  return (
    <div className="source-item">
      <span className="source-badge">S{source.index}</span>
      <span className="source-title">{source.title || 'Document'}</span>
      {source.section && (
        <span className="source-section">— {source.section}</span>
      )}
    </div>
  );
}
