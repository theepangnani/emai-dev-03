import { useState, useEffect, useRef, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { useHelpChat } from './useHelpChat';
import { ChatMessage } from './ChatMessage';
import { SuggestionChips } from './SuggestionChips';
import { useChatPanelInteraction } from '../../hooks/useChatPanelInteraction';
import { ArcMascot } from '../arc';
import './HelpChatbot.css';

const STORAGE_KEY = 'classbridge-help-open';

const CHAT_COMMANDS = new Set(['clear', 'reset']);

const MIN_QUERY_LENGTH = 3;

export function HelpChatbot() {
  const [isOpen, setIsOpen] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true';
    } catch {
      return false;
    }
  });

  const { messages, sendMessage, isLoading, error, clearMessages } = useHelpChat();
  const [inputValue, setInputValue] = useState('');
  const [helperMessage, setHelperMessage] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const location = useLocation();
  const { panelRef, panelStyle, maximized, toggleMaximize, onDragStart, onResizeStart } = useChatPanelInteraction('classbridge-help-panel-state');

  // Persist open/closed state
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(isOpen));
    } catch {
      // localStorage unavailable
    }
  }, [isOpen]);

  // Auto-scroll to bottom on new messages or loading state change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 200);
    }
  }, [isOpen]);

  const handleSend = useCallback(() => {
    const text = inputValue.trim();
    if (!text || isLoading) return;

    if (text.length < MIN_QUERY_LENGTH) {
      setHelperMessage('Please type at least 3 characters so I can help you better.');
      return;
    }

    setHelperMessage('');

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

  const showWelcome = messages.length === 0;
  const lastAssistantMessage = [...messages].reverse().find(m => m.role === 'assistant');
  const showChips = showWelcome || (!isLoading && error) || (!isLoading && lastAssistantMessage?.intent === 'help');

  return (
    <>
      {/* FAB button — Arc, the ClassBridge Learning Companion */}
      {!isOpen && (
        <button
          className="help-chatbot-fab help-chatbot-fab--arc"
          onClick={() => setIsOpen(true)}
          aria-label="Open help chat"
        >
          <ArcMascot size={56} mood="waving" glow decorative />
        </button>
      )}

      {/* Chat panel */}
      {isOpen && (
        <div
          className={`help-chatbot-panel${maximized ? ' help-chatbot-panel--maximized' : ''}`}
          ref={panelRef}
          style={panelStyle}
        >
          <div
            className="help-chatbot-header help-chatbot-header--draggable"
            onPointerDown={onDragStart}
            onDoubleClick={toggleMaximize}
          >
            <div className="help-chatbot-header-title">
              <ArcMascot size={32} mood={isLoading ? 'thinking' : 'happy'} decorative />
              <h3>Arc · ClassBridge Help</h3>
            </div>
            <div className="help-chatbot-header-actions">
              {messages.length > 0 && (
                <button
                  className="help-chatbot-clear"
                  onClick={clearMessages}
                  aria-label="Clear chat history"
                  title="Clear chat"
                >
                  Clear
                </button>
              )}
              <button
                className="help-chatbot-close"
                onClick={toggleMaximize}
                aria-label={maximized ? 'Restore chat window' : 'Maximize chat window'}
                title={maximized ? 'Restore' : 'Maximize'}
              >
                {maximized ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><rect x="5" y="5" width="14" height="14" rx="1" /><path d="M9 3h6M3 9v6" /></svg>
                ) : (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" /></svg>
                )}
              </button>
              <button
                className="help-chatbot-close"
                onClick={() => setIsOpen(false)}
                aria-label="Close help chat"
              >
                &times;
              </button>
            </div>
          </div>

          <div className="help-chatbot-messages">
            {showWelcome && (
              <div className="help-chatbot-welcome">
                Hi! I'm ClassBridge Helper. Ask me anything about the platform.
              </div>
            )}

            {showChips && (
              <SuggestionChips
                onChipClick={handleChipClick}
                currentPage={location.pathname}
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

          {helperMessage && (
              <div className="help-chatbot-helper-message">
                {helperMessage}
              </div>
            )}

          <div className="help-chatbot-input">
            <input
              ref={inputRef}
              type="text"
              placeholder="Type your question..."
              value={inputValue}
              onChange={(e) => { setInputValue(e.target.value); setHelperMessage(''); }}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
            />
            <button
              className="help-chatbot-send"
              onClick={handleSend}
              disabled={isLoading || inputValue.trim().length < MIN_QUERY_LENGTH}
            >
              Send
            </button>
          </div>
          {!maximized && (
            <div
              className="help-chatbot-resize-handle"
              onPointerDown={onResizeStart}
              aria-hidden="true"
            />
          )}
        </div>
      )}
    </>
  );
}
