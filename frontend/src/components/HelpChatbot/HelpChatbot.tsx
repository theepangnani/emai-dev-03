import { useState, useEffect, useRef, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { useHelpChat } from './useHelpChat';
import { ChatMessage } from './ChatMessage';
import { SuggestionChips } from './SuggestionChips';
import './HelpChatbot.css';

const STORAGE_KEY = 'classbridge-help-open';

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
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const location = useLocation();

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

  const showWelcome = messages.length === 0;
  const showChips = showWelcome || (!isLoading && error);

  return (
    <>
      {/* FAB button */}
      {!isOpen && (
        <button
          className="help-chatbot-fab"
          onClick={() => setIsOpen(true)}
          aria-label="Open help chat"
        >
          <img src="/chat-icon.png" alt="" className="help-chatbot-fab-logo" />
        </button>
      )}

      {/* Chat panel */}
      {isOpen && (
        <div className="help-chatbot-panel">
          <div className="help-chatbot-header">
            <div className="help-chatbot-header-title">
              <img src="/chat-icon.png" alt="" className="help-chatbot-header-logo" />
              <h3>ClassBridge Help</h3>
            </div>
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
              onClick={() => setIsOpen(false)}
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
    </>
  );
}
