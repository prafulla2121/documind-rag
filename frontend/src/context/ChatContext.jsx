import { createContext, useContext, useState, useEffect, useRef, useMemo } from 'react';
import { getChatSessions, getSessionMessages, streamQuery } from '../lib/api';

const ChatContext = createContext();

export function ChatProvider({ children }) {
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [streamState, setStreamState] = useState({ status: 'idle', phase: null, error: null });
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const skipNextSessionLoadRef = useRef(false);
  const abortControllerRef = useRef(null);
  const lastUserQueryRef = useRef('');

  // Initial load of sessions
  useEffect(() => {
    fetchSessions();
  }, []);

  // Load messages when currentSessionId changes
  useEffect(() => {
    if (currentSessionId) {
      if (skipNextSessionLoadRef.current) {
        skipNextSessionLoadRef.current = false;
        return;
      }
      loadSessionMessages(currentSessionId);
    } else {
      setMessages([]);
    }
  }, [currentSessionId]);

  const fetchSessions = async () => {
    try {
      setIsLoadingSessions(true);
      // Small delay to ensure DB persistence is finalized before reading
      await new Promise(r => setTimeout(r, 500));
      const data = await getChatSessions();
      setSessions(data.sessions || []);
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
    } finally {
      setIsLoadingSessions(false);
    }
  };

  const loadSessionMessages = async (id) => {
    try {
      const data = await getSessionMessages(id);
      setMessages(data.messages || []);
    } catch (error) {
      console.error("Failed to load messages:", error);
      setMessages([]);
    }
  };

  const sendMessage = async (query, options = {}) => {
    const { regenerate = false } = options;
    if (!query.trim() || streamState.status !== 'idle') return;

    lastUserQueryRef.current = query;

    const userMsg = regenerate ? null : {
      id: Date.now().toString(),
      role: 'user',
      content: query,
    };

    const assistantId = (Date.now() + 1).toString();
    const assistantMsg = {
      id: assistantId,
      role: 'assistant',
      content: '',
      sources: [],
      streamingPhase: 'analyzing_query',
    };

    setMessages(prev => (regenerate ? [...prev, assistantMsg] : [...prev, userMsg, assistantMsg]));
    setStreamState({ status: 'sending', phase: 'analyzing_query', error: null });
    abortControllerRef.current = new AbortController();

    try {
      let fullContent = '';
      let sources = [];

      for await (const event of streamQuery(query, {}, currentSessionId, { signal: abortControllerRef.current.signal })) {
        if (event.type === 'session_id') {
          if (!currentSessionId) {
            // Prevent immediate reload from wiping optimistic streaming message.
            skipNextSessionLoadRef.current = true;
            setCurrentSessionId(event.data);
            fetchSessions(); // Refresh list to show new session
          }
        } else if (event.type === 'phase') {
          setStreamState(prev => ({ ...prev, status: 'streaming', phase: event.data }));
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? { ...m, streamingPhase: event.data }
                : m
            )
          );
        } else if (event.type === 'sources') {
          sources = event.data || [];
        } else if (event.type === 'token') {
          setStreamState(prev => ({ ...prev, status: 'streaming', phase: 'drafting_answer' }));
          fullContent += event.data;
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? { ...m, content: fullContent, sources, streamingPhase: 'drafting_answer' }
                : m
            )
          );
        } else if (event.type === 'done') {
          setStreamState({ status: 'idle', phase: null, error: null });
        }
      }
    } catch (error) {
      const wasAborted = error?.name === 'AbortError';
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantId
            ? { ...m, content: wasAborted ? 'Generation stopped.' : 'Error connecting to assistant.' }
            : m
        )
      );
      setStreamState({
        status: 'idle',
        phase: null,
        error: wasAborted ? null : 'connection_error',
      });
    } finally {
      abortControllerRef.current = null;
      setStreamState(prev => (prev.status === 'idle' ? prev : { status: 'idle', phase: null, error: prev.error }));
    }
  };

  const cancelStreaming = () => {
    abortControllerRef.current?.abort();
  };

  const regenerateLastResponse = async () => {
    const lastQuery = lastUserQueryRef.current || [...messages].reverse().find(m => m.role === 'user')?.content;
    if (!lastQuery || streamState.status !== 'idle') return;
    await sendMessage(lastQuery, { regenerate: true });
  };

  const createNewChat = () => {
    abortControllerRef.current?.abort();
    setCurrentSessionId(null);
    setMessages([]);
    setStreamState({ status: 'idle', phase: null, error: null });
  };

  const isLoading = useMemo(() => streamState.status !== 'idle', [streamState.status]);

  return (
    <ChatContext.Provider value={{
      sessions,
      currentSessionId,
      setCurrentSessionId,
      messages,
      setMessages,
      isLoading,
      streamState,
      isLoadingSessions,
      sendMessage,
      cancelStreaming,
      regenerateLastResponse,
      createNewChat,
      fetchSessions
    }}>
      {children}
    </ChatContext.Provider>
  );
}

export const useChat = () => useContext(ChatContext);
