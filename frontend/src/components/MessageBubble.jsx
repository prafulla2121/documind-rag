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

  const avgScore = useMemo(() => {
    if (!message.sources?.length) return 0;
    return message.sources.reduce((acc, source) => acc + (source.score || 0), 0) / message.sources.length;
  }, [message.sources]);
  const confidenceLabel = avgScore > 0.3 ? 'Grounded' : message.sources?.length ? 'Low confidence' : 'No strong sources';

  // Claude-style star icon (simplified as SVG)
  const AiIcon = () => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2L13.5 8.5L20 10L13.5 11.5L12 18L10.5 11.5L4 10L10.5 8.5L12 2Z" fill="#d97757"/>
      <path d="M18 4L18.5 6L20.5 6.5L18.5 7L18 9L17.5 7L15.5 6.5L17.5 6L18 4Z" fill="#d97757"/>
    </svg>
  );

  return (
    <div className="message-container">
      <div className={`message ${message.role}`}>
        <div className="message-avatar">
          {isUser ? (
            <div className="avatar" style={{width: '24px', height: '24px', fontSize: '10px'}}>U</div>
          ) : (
            <AiIcon />
          )}
        </div>
        <div className="message-content">
            {isStreaming ? (
              <div className="typing-indicator">
                <span style={{ color: '#999', fontStyle: 'italic', fontSize: '14px' }}>
                  RagSystem is thinking...
                </span>
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
                  {displayContent || "RagSystem is thinking..."}
                </ReactMarkdown>
              </div>
            )}
            {!isUser && (
              <div className={`answer-confidence ${confidenceLabel === 'Grounded' ? 'grounded' : confidenceLabel === 'Low confidence' ? 'low' : 'none'}`}>
                {confidenceLabel}
              </div>
            )}

            {/* Sources styled as Claude-style Artifact Cards */}
            {!isUser && message.sources && message.sources.length > 0 && (
              <div className="sources-area">
                <div className="sources-heading">Sources</div>
                {message.sources.map((source, idx) => (
                  <div key={idx} className="source-card" onClick={() => setSelectedSource(source)} role="button" tabIndex={0}>
                    <div className="source-card-icon">{source.source_type === 'youtube' ? 'YT' : 'DOC'}</div>
                    <div className="source-card-info">
                      <SourceCitation source={source} />
                      <div className="source-card-type">
                        {source.source_type === 'youtube' ? (source.channel_name || 'YouTube transcript') : 'Knowledge Base Source'}
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
                  <div className="source-detail-section">Section: {selectedSource.section}</div>
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
