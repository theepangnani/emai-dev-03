import { useState, useEffect, useRef, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { useFABContext } from '../context/FABContext';
import { useHelpChat } from './HelpChatbot/useHelpChat';
import { ChatMessage } from './HelpChatbot/ChatMessage';
import { SuggestionChips } from './HelpChatbot/SuggestionChips';
import './HelpChatbot/HelpChatbot.css';
import './SpeedDialFAB.css';

const CHAT_COMMANDS = new Set(['clear', 'reset']);

export function SpeedDialFAB() {
  const { notesFAB, studyGuideContext, getPendingQuestion, clearPendingQuestion, subscribePendingQuestion } = useFABContext();
  const [dialOpen, setDialOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [pendingQuestionTick, forceUpdate] = useState(0);

  // Subscribe to pending question changes — only SpeedDialFAB re-renders
  useEffect(() => {
    return subscribePendingQuestion(() => forceUpdate(n => n + 1));
  }, [subscribePendingQuestion]);

  // Read pending question on each render (tick changes trigger re-render)
  const pendingQuestion = getPendingQuestion();
  // Suppress unused-var lint — tick is used only to trigger re-renders
  void pendingQuestionTick;

  const containerRef = useRef<HTMLDivElement>(null);

  // Help chat state — passes study guide context for §6.114
  const {
    messages, sendMessage, isLoading, error, clearMessages,
    saveAsGuide, saveAsMaterial, isStudyMode,
  } = useHelpChat(studyGuideContext);
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const location = useLocation();

  // Auto-scroll chat messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Focus chat input when panel opens
  useEffect(() => {
    if (chatOpen) {
      setTimeout(() => inputRef.current?.focus(), 200);
    }
  }, [chatOpen]);

  // Handle pending question from FABContext (text selection → chatbot injection)
  useEffect(() => {
    if (!pendingQuestion) return;
    if (!chatOpen) {
      setChatOpen(true);
      setDialOpen(false);
      return; // Wait for next render when chatOpen is true
    }
    if (!isLoading) {
      sendMessage(pendingQuestion);
      clearPendingQuestion();
    }
  }, [pendingQuestion, chatOpen, isLoading, sendMessage, clearPendingQuestion]);

  // Listen for programmatic open (Ctrl+K / Cmd+K dispatches this event)
  useEffect(() => {
    const handleOpenChat = () => {
      setChatOpen(true);
      setDialOpen(false);
    };
    window.addEventListener('open-help-chat', handleOpenChat);
    return () => window.removeEventListener('open-help-chat', handleOpenChat);
  }, []);

  // Close speed dial when clicking outside
  useEffect(() => {
    if (!dialOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setDialOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [dialOpen]);

  const handleSend = useCallback(() => {
    const text = inputValue.trim();
    if (!text || isLoading) return;

    if (CHAT_COMMANDS.has(text.toLowerCase())) {
      clearMessages();
      setInputValue('');
      return;
    }

    setInputValue('');
    sendMessage(text);
  }, [inputValue, isLoading, sendMessage, clearMessages]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  const handleChipClick = useCallback((text: string) => {
    sendMessage(text);
  }, [sendMessage]);

  const openChat = () => {
    setChatOpen(true);
    setDialOpen(false);
  };

  const toggleNotes = () => {
    notesFAB?.onToggle();
    setDialOpen(false);
  };

  const showWelcome = messages.length === 0;
  const lastAssistantMessage = [...messages].reverse().find(m => m.role === 'assistant');
  const showChips = showWelcome || (!isLoading && error) || (!isLoading && lastAssistantMessage && ['help', 'search'].includes(lastAssistantMessage.intent || ''));

  // If no notes action registered, render the chat FAB directly (no speed dial)
  const hasMultipleActions = !!notesFAB;

  // §6.114 — header and welcome text adapt to study mode
  const guideTitle = studyGuideContext?.title || 'Study Guide';
  const welcomeText = isStudyMode
    ? 'What would you like to know?'
    : 'Hi! I\'m ClassBridge Helper. Ask me anything about the platform.';

  return (
    <div className="speed-dial" ref={containerRef}>
      {/* Chat panel (always available) */}
      {chatOpen && (
        <div className="help-chatbot-panel">
          <div className="help-chatbot-header">
            <div className="help-chatbot-header-top">
              <span className="help-chatbot-header-label">
                {isStudyMode ? 'Study Q&A' : 'ClassBridge Help'}
              </span>
              <div className="help-chatbot-header-actions">
                {messages.length > 0 && (
                  <button
                    className="help-chatbot-clear"
                    onClick={clearMessages}
                    aria-label="Clear chat history"
                    title="Clear chat"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" /></svg>
                  </button>
                )}
                <button
                  className="help-chatbot-close"
                  onClick={() => setChatOpen(false)}
                  aria-label="Close help chat"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M18 6L6 18M6 6l12 12" /></svg>
                </button>
              </div>
            </div>
            {isStudyMode && (
              <div className="help-chatbot-header-subtitle">{guideTitle}</div>
            )}
          </div>
          {isStudyMode && (
            <div className="help-chatbot-credit-pill">0.25 credits per question</div>
          )}
          <div className="help-chatbot-messages">
            {showWelcome && (
              <div className={`help-chatbot-welcome ${isStudyMode ? 'help-chatbot-welcome--study' : ''}`}>
                {welcomeText}
              </div>
            )}
            {showChips && (
              <SuggestionChips
                onChipClick={handleChipClick}
                currentPage={location.pathname}
                isStudyMode={isStudyMode}
              />
            )}
            {messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                role={msg.role}
                content={msg.content}
                videos={msg.videos}
                sources={msg.sources}
                search_results={msg.search_results}
                mode={msg.mode}
                credits_used={msg.credits_used}
                onSaveAsGuide={isStudyMode ? saveAsGuide : undefined}
                onSaveAsMaterial={isStudyMode && studyGuideContext?.courseId ? saveAsMaterial : undefined}
                hasCourseId={!!studyGuideContext?.courseId}
              />
            ))}
            {isLoading && (
              <div className="help-chatbot-typing">
                <span className="help-chatbot-typing-dot" />
                <span className="help-chatbot-typing-dot" />
                <span className="help-chatbot-typing-dot" />
              </div>
            )}
            {error && (
              <div className="help-chatbot-error-card">
                <svg className="help-chatbot-error-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <span className="help-chatbot-error-text">
                  {error.includes('/help') ? (
                    <>
                      {error.split('/help')[0]}
                      <a href="/help" style={{ color: 'inherit', textDecoration: 'underline' }}>/help</a>
                      {error.split('/help')[1]}
                    </>
                  ) : error}
                </span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
          <div className="help-chatbot-input">
            <input
              ref={inputRef}
              type="text"
              placeholder={isStudyMode ? 'Ask about this study guide...' : 'Type your question...'}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
            />
            <button
              className="help-chatbot-send"
              onClick={handleSend}
              disabled={isLoading || !inputValue.trim()}
              aria-label="Send message"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Speed dial sub-actions (only when dial is open) */}
      {hasMultipleActions && dialOpen && !chatOpen && (
        <div className="speed-dial-actions">
          <button
            className="speed-dial-action speed-dial-action--chat"
            onClick={openChat}
            aria-label="Open help chat"
          >
            <span className="speed-dial-chat-icon">
              <img src="/chat-icon.png" alt="" className="speed-dial-action-logo" />
            </span>
            <span className="speed-dial-action-label">{isStudyMode ? 'Ask' : 'Chat'}</span>
          </button>
          <button
            className={`speed-dial-action speed-dial-action--notes ${notesFAB.isOpen ? 'speed-dial-action--active' : ''}`}
            onClick={toggleNotes}
            aria-label={notesFAB.isOpen ? 'Close notes' : 'Open notes'}
          >
            <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 3h10l3 3v10a1 1 0 01-1 1H4a1 1 0 01-1-1V3z" />
              <path d="M6.5 8h7M6.5 11h4" />
            </svg>
            <span className="speed-dial-action-label">Notes</span>
            {notesFAB.hasNote && !notesFAB.isOpen && <span className="speed-dial-action-badge" />}
          </button>
        </div>
      )}

      {/* Main FAB button */}
      {!chatOpen && (
        hasMultipleActions ? (
          <button
            className={`speed-dial-trigger ${dialOpen ? 'speed-dial-trigger--open' : ''}`}
            onClick={() => setDialOpen(o => !o)}
            aria-label={dialOpen ? 'Close menu' : 'Open menu'}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <path d="M12 5v14M5 12h14" />
            </svg>
          </button>
        ) : (
          <button
            className="speed-dial-trigger speed-dial-trigger--single"
            onClick={openChat}
            aria-label="Open help chat"
          >
            <img src="/chat-icon.png" alt="" className="speed-dial-single-logo" />
          </button>
        )
      )}

      {/* Backdrop overlay when dial is open */}
      {dialOpen && <div className="speed-dial-backdrop" onClick={() => setDialOpen(false)} />}
    </div>
  );
}
