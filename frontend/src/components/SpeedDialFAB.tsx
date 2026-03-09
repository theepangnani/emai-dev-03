import { useState, useEffect, useRef, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { useFABContext } from '../context/FABContext';
import { useHelpChat } from './HelpChatbot/useHelpChat';
import { ChatMessage } from './HelpChatbot/ChatMessage';
import { SuggestionChips } from './HelpChatbot/SuggestionChips';
import './HelpChatbot/HelpChatbot.css';
import './SpeedDialFAB.css';


export function SpeedDialFAB() {
  const { notesFAB } = useFABContext();
  const [dialOpen, setDialOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Help chat state
  const { messages, sendMessage, isLoading, error } = useHelpChat();
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
    setInputValue('');
    sendMessage(text);
  }, [inputValue, isLoading, sendMessage]);

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
  const showChips = showWelcome || (!isLoading && error);

  // If no notes action registered, render the chat FAB directly (no speed dial)
  const hasMultipleActions = !!notesFAB;

  return (
    <div className="speed-dial" ref={containerRef}>
      {/* Chat panel (always available) */}
      {chatOpen && (
        <div className="help-chatbot-panel">
          <div className="help-chatbot-header">
            <div className="help-chatbot-header-title">
              <img src="/logo-icon.png" alt="" className="help-chatbot-header-logo" />
              <h3>ClassBridge Help</h3>
            </div>
            <button
              className="help-chatbot-close"
              onClick={() => setChatOpen(false)}
              aria-label="Close help chat"
            >
              &times;
            </button>
          </div>
          <div className="help-chatbot-messages">
            {showWelcome && (
              <div className="help-chatbot-welcome">
                Hi! I'm ClassBridge Helper. Ask me anything about the platform.
              </div>
            )}
            {showChips && (
              <SuggestionChips onChipClick={handleChipClick} currentPage={location.pathname} />
            )}
            {messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                role={msg.role}
                content={msg.content}
                videos={msg.videos}
                sources={msg.sources}
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
              <div className="help-chatbot-error">
                {error.includes('/help') ? (
                  <>
                    {error.split('/help')[0]}
                    <a href="/help" style={{ color: 'inherit', textDecoration: 'underline' }}>/help</a>
                    {error.split('/help')[1]}
                  </>
                ) : error}
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
          <div className="help-chatbot-input">
            <input
              ref={inputRef}
              type="text"
              placeholder="Type your question..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
            />
            <button
              className="help-chatbot-send"
              onClick={handleSend}
              disabled={isLoading || !inputValue.trim()}
            >
              Send
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
              <img src="/logo-icon.png" alt="" className="speed-dial-action-logo" />
            </span>
            <span className="speed-dial-action-label">Chat</span>
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
            <img src="/logo-icon.png" alt="" className="speed-dial-single-logo" />
          </button>
        )
      )}

      {/* Backdrop overlay when dial is open */}
      {dialOpen && <div className="speed-dial-backdrop" onClick={() => setDialOpen(false)} />}
    </div>
  );
}
