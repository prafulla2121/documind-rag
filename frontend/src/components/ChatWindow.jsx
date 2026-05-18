import { useState, useRef, useEffect } from 'react';
import { useChat } from '../context/ChatContext';
import MessageBubble from './MessageBubble';
import ChatModelSelector from './ChatModelSelector';

const SUGGESTIONS = [
  "What is our vacation policy?",
  "How do I request time off?",
  "What are the company benefits?",
  "How do I reset my password?",
];

export default function ChatWindow() {
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
      <div className="chat-header">
        <h2>{currentSession?.title || 'New Conversation'} ⌵</h2>
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
            <div className="empty-state-icon">🧠</div>
            <h3>How can I help you today?</h3>
            <p>
              I can help you find information about company policies, procedures,
              IT support, HR matters, and anything in our knowledge base.
            </p>
            <div className="suggestion-chips">
              {SUGGESTIONS.map((s, i) => (
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
              placeholder="Message RagSystem..."
              rows={1}
            />
          </div>
          <div className="input-footer">
            <button className="plus-button" title="Attach file">+</button>
            <div style={{display: 'flex', alignItems: 'center', gap: '12px'}}>
               <ChatModelSelector />
               {isLoading ? (
                <button className="send-button-mini" onClick={cancelStreaming} title="Stop generation">
                  ■
                </button>
               ) : (
                <button className="send-button-mini" onClick={regenerateLastResponse} disabled={!messages.some(m => m.role === 'assistant')} title="Regenerate last response">
                  ↻
                </button>
               )}
               <button
                className="send-button-mini"
                onClick={() => handleSend()}
                disabled={isLoading || !input.trim()}
              >
                ➤
              </button>
            </div>
          </div>
        </div>
        <div style={{textAlign: 'center', fontSize: '11px', color: '#999', marginTop: '12px'}}>
          RagSystem is AI and can make mistakes. Please double-check responses.
        </div>
      </div>
    </div>
  );
}
