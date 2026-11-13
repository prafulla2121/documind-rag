import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useMemo, useState } from 'react';
import SourceCitation from './SourceCitation';

export default function MessageBubble({ message, isLoading }) {
  const isUser = message.role === 'user';
  const isStreaming = !isUser && isLoading && message.content === '';
  const [selectedSource, setSelectedSource] = useState(null);
  
  const content = message.content || '';
  const displayContent = useMemo(() => {
    if (isUser) return content;
    return content
      .replace(/\s*\[https?:\/\/(?:www\.)?(?:youtu\.be|youtube\.com)\/[^\]]+\]/gi, '')
      .replace(/\s*\(https?:\/\/(?:www\.)?(?:youtu\.be|youtube\.com)\/[^\)]+\)/gi, '')
      .replace(/\s*https?:\/\/(?:www\.)?(?:youtu\.be|youtube\.com)\/\S+/gi, '')
      .replace(/Source Summary:\s*(?:\n\s*[-*]\s*DOCUMENT\s*\d+\s*)+/gi, '')
      .trim();
  }, [content, isUser]);

  // Scores are raw RRF or cross-encoder values (different scales), so state the source count, not a confidence.
  const sourceCount = message.sources?.length || 0;
  const confidenceLabel = sourceCount
    ? `Based on ${sourceCount} source section${sourceCount > 1 ? 's' : ''}`
    : 'No matching sources';

  return (
    <div className="message-container">
      <div className={`message ${message.role}`}>
        <div className="message-avatar">
          <div className={`avatar avatar-sm ${isUser ? '' : 'avatar-ai'}`} aria-hidden="true">{isUser ? 'You' : 'DM'}</div>
        </div>
        <div className="message-content">
            {isStreaming ? (
              <div className="typing-indicator">
                <span className="thinking-text">Searching the documents…</span>
              </div>
            ) : (
              <div className="markdown-content">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    code({node, inline, className, children, ...props}) {
                      const match = /language-(\w+)/.exec(className || '')
                      return !inline && match ? (
                        <SyntaxHighlighter
                          children={String(children).replace(/\n$/, '')}
                          style={atomDark}
                          language={match[1]}
                          PreTag="div"
                          {...props}
                        />
                      ) : (
                        <code className={className} {...props}>
                          {children}
                        </code>
                      )
                    }
                  }}
                >
                  {displayContent || "Searching the documents…"}
                </ReactMarkdown>
              </div>
            )}
            {!isUser && (
              <div className={`answer-confidence ${sourceCount ? 'grounded' : 'none'}`}>
                {confidenceLabel}
              </div>
            )}

            {!isUser && message.sources && message.sources.length > 0 && (
              <div className="sources-area">
                <div className="sources-heading">Sources</div>
                {message.sources.map((source, idx) => (
                  <div
                    key={idx}
                    className={`source-card ${selectedSource === source ? 'selected' : ''}`}
                    onClick={() => setSelectedSource(source)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelectedSource(source); } }}
                    role="button"
                    tabIndex={0}
                    aria-label={`Show source ${source.index}`}
                  >
                    <div className="source-card-info">
                      <SourceCitation source={source} />
                      {source.excerpt && source.source_type !== 'youtube' && (
                        <div className="source-card-excerpt">{source.excerpt.replace(/^#+\s.*\n+/, '')}</div>
                      )}
                      <div className="source-card-type">
                        {source.source_type === 'youtube'
                          ? (source.channel_name || 'YouTube transcript')
                          : [source.filename, source.retrieval_methods?.length ? `found by ${source.retrieval_methods.join(' + ')}` : '']
                              .filter(Boolean).join(' · ')}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {selectedSource && (
              <div className="source-detail-drawer">
                <div className="source-detail-header">
                  <strong>{selectedSource.title || selectedSource.filename || 'Source Document'}</strong>
                  <button className="source-close-btn" onClick={() => setSelectedSource(null)}>Close</button>
                </div>
                <div className="source-detail-meta">
                  <span>Type: {selectedSource.source_type || 'unknown'}</span>
                  <span>Score: {(selectedSource.score || 0).toFixed(3)}</span>
                </div>
                {selectedSource.source_type === 'youtube' && (
                  <div className="youtube-detail-preview">
                    {selectedSource.thumbnail_url && <img src={selectedSource.thumbnail_url} alt="" />}
                    <div>
                      <div>{selectedSource.channel_name || 'YouTube transcript'}</div>
                      {selectedSource.url && (
                        <a href={selectedSource.url} target="_blank" rel="noreferrer">
                          Open at {selectedSource.timestamp || '0:00'}
                        </a>
                      )}
                    </div>
                  </div>
                )}
                {selectedSource.section && (
                  <div className="source-detail-section">Section: {selectedSource.section.replace(/^#+\s*/, '')}</div>
                )}
                {selectedSource.retrieval_methods?.length > 0 && (
                  <div className="source-detail-section">Retrieved via: {selectedSource.retrieval_methods.join(', ')}</div>
                )}
                {selectedSource.excerpt && (
                  <div className="source-detail-excerpt">{selectedSource.excerpt}</div>
                )}
              </div>
            )}
        </div>
      </div>
    </div>
  );
}
