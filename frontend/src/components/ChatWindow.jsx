import { useState, useRef, useEffect } from 'react';
import { useChat } from '../context/ChatContext';
import MessageBubble from './MessageBubble';
import ChatModelSelector from './ChatModelSelector';
import { REPO_URL } from '../lib/api';

const SUGGESTIONS = [
  "What is our vacation policy?",
  "How do I request time off?",
  "What are the company benefits?",
  "How do I reset my password?",
];

export default function ChatWindow({ demo = null }) {
  const {
    messages,
    isLoading,
    streamState,
    sendMessage,
    cancelStreaming,
    regenerateLastResponse,
    currentSessionId,
    sessions
  } = useChat();
  const [input, setInput] = useState('');
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(scrollToBottom, [messages]);

  const handleSend = async (text) => {
    const query = (text || input).trim();
    if (!query || isLoading) return;
    
    setInput('');
    await sendMessage(query);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const currentSession = sessions.find(s => s.id === currentSessionId);
  const phaseLabel = {
    analyzing_query: 'Analyzing query',
    retrieving_documents: 'Retrieving documents',
    reranking_results: 'Reranking results',
    building_context: 'Building context',
    drafting_answer: 'Drafting answer',
  };

  return (
    <div className="main-content">
      {/* Header */}
      <div className="chat-header" style={{ justifyContent: 'space-between' }}>
        <h2>{currentSession?.title || 'New conversation'}</h2>
        {messages.length > 0 && (
          <div className="header-actions">
            <button
              className="btn-ghost"
              onClick={() => {
                const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(messages, null, 2));
                const downloadAnchorNode = document.createElement('a');
                downloadAnchorNode.setAttribute("href", dataStr);
                downloadAnchorNode.setAttribute("download", `chat_export_${currentSessionId}.json`);
                document.body.appendChild(downloadAnchorNode);
                downloadAnchorNode.click();
                downloadAnchorNode.remove();
              }}
            >
              Export JSON
            </button>
            <button
              className="btn-ghost"
              onClick={() => {
                const mdContent = messages.map(m => `### ${m.role.toUpperCase()}\n\n${m.content}\n\n---`).join('\n\n');
                const dataStr = "data:text/markdown;charset=utf-8," + encodeURIComponent(mdContent);
                const downloadAnchorNode = document.createElement('a');
                downloadAnchorNode.setAttribute("href", dataStr);
                downloadAnchorNode.setAttribute("download", `chat_export_${currentSessionId}.md`);
                document.body.appendChild(downloadAnchorNode);
                downloadAnchorNode.click();
                downloadAnchorNode.remove();
              }}
            >
              Export MD
            </button>
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="messages-area">
        {isLoading && (
          <div className="stream-status-timeline">
            {Object.entries(phaseLabel).map(([phaseKey, label]) => (
              <span
                key={phaseKey}
                className={`timeline-step ${streamState.phase === phaseKey ? 'active' : ''}`}
              >
                {label}
              </span>
            ))}
          </div>
        )}
        {messages.length === 0 ? (
          <div className="empty-state">
            <h3>DocuMind</h3>
            <p>
              Ask questions about your documents. Answers come from hybrid search
              (vectors + BM25) over the indexed text and cite the sections they used.
            </p>
            <p className="empty-links">
              <a href={REPO_URL} target="_blank" rel="noreferrer">Source code on GitHub</a>
            </p>
            {demo && (
              <div className="demo-notice">
                <strong>Demo:</strong> data resets when the server restarts. First visit can take
                about a minute while the free server wakes up. Uploads are visible to other
                visitors, so do not upload private files.
              </div>
            )}
            {demo && !demo.llm_ready && (
              <div className="demo-notice warn" role="alert">
                No Gemini API key is set on the server, so answers are not generated: you will see
                the retrieved source text instead. Retrieval and citations still work.
              </div>
            )}
            {demo && <div className="suggestion-label">Try a question about the sample document, the Harbor HL-7 lantern guide:</div>}
            <div className="suggestion-chips">
              {(demo?.examples?.length ? demo.examples : SUGGESTIONS).map((s, i) => (
                <button
                  key={i}
                  className={`suggestion-chip`}
                  onClick={() => handleSend(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map(msg => (
            <MessageBubble key={msg.id} message={msg} isLoading={isLoading} />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="input-area">
        <div className="input-wrapper">
          <div className="input-container">
            <textarea
              ref={inputRef}
              className="input-field"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question about the documents…"
              aria-label="Your question"
              rows={1}
            />
          </div>
          <div className="input-footer">
            <button
              className="plus-button"
              title="Add documents"
              aria-label="Add documents"
              onClick={() => window.dispatchEvent(new CustomEvent('navigate', { detail: 'upload' }))}
            >+</button>
            <div style={{display: 'flex', alignItems: 'center', gap: '12px'}}>
               <ChatModelSelector readOnly={Boolean(demo)} />
               {isLoading ? (
                <button className="send-button-mini" onClick={cancelStreaming} title="Stop generation" aria-label="Stop generation">
                  ■
                </button>
               ) : (
                <button className="send-button-mini" onClick={regenerateLastResponse} disabled={!messages.some(m => m.role === 'assistant')} title="Regenerate last response" aria-label="Regenerate last response">
                  ↻
                </button>
               )}
               <button
                className="send-button-mini"
                onClick={() => handleSend()}
                disabled={isLoading || !input.trim()}
                title="Send"
                aria-label="Send"
              >
                ↑
              </button>
            </div>
          </div>
        </div>
        <div className="input-disclaimer">
          Answers can be wrong. Check them against the cited sources.
        </div>
      </div>
    </div>
  );
}
