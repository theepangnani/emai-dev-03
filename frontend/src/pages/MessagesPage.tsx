import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { messagesApi } from '../api/client';
import type {
  ConversationSummary,
  ConversationDetail,
  RecipientOption,
} from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { useFocusTrap } from '../hooks/useFocusTrap';
import { logger } from '../utils/logger';
import EmptyState from '../components/EmptyState';
import './MessagesPage.css';

export function MessagesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<ConversationDetail | null>(null);
  const [showNewModal, setShowNewModal] = useState(false);
  const [recipients, setRecipients] = useState<RecipientOption[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const conversationLimit = 20;
  const messageLimit = 30;
  const [conversationOffset, setConversationOffset] = useState(0);
  const [hasMoreConversations, setHasMoreConversations] = useState(true);
  const [messageOffset, setMessageOffset] = useState(0);
  const [hasMoreMessages, setHasMoreMessages] = useState(false);

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [filteredConversations, setFilteredConversations] = useState<ConversationSummary[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchActive, setSearchActive] = useState(false);
  const searchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Scroll-to-message state (set when clicking a search result)
  const [scrollToMessageId, setScrollToMessageId] = useState<number | null>(null);

  // In-thread search state
  const [threadSearchOpen, setThreadSearchOpen] = useState(false);
  const [threadSearchQuery, setThreadSearchQuery] = useState('');
  const [threadSearchMatches, setThreadSearchMatches] = useState<number[]>([]);
  const [threadSearchIndex, setThreadSearchIndex] = useState(0);
  const threadSearchInputRef = useRef<HTMLInputElement>(null);
  const threadSearchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // New conversation form state
  const [selectedRecipient, setSelectedRecipient] = useState<number | null>(null);
  const [newSubject, setNewSubject] = useState('');
  const [initialMessage, setInitialMessage] = useState('');
  const [creatingConversation, setCreatingConversation] = useState(false);
  const newConvModalRef = useFocusTrap<HTMLDivElement>(showNewModal, () => setShowNewModal(false));

  // Recipient search state (#956)
  const [recipientSearchQuery, setRecipientSearchQuery] = useState('');
  const [recipientSearchResults, setRecipientSearchResults] = useState<RecipientOption[]>([]);
  const [isRecipientSearching, setIsRecipientSearching] = useState(false);
  const [showRecipientDropdown, setShowRecipientDropdown] = useState(false);
  const recipientSearchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    loadConversations(true);
    loadRecipients();

    // Poll for new messages every 30 seconds
    const interval = setInterval(() => loadConversations(true), 30000);
    return () => clearInterval(interval);
  }, []);

  // Handle recipient_id query param (from teacher "Message" button)
  useEffect(() => {
    const recipientId = searchParams.get('recipient_id');
    if (recipientId && recipients.length > 0) {
      const rid = Number(recipientId);
      const match = recipients.find(r => r.user_id === rid);
      setSelectedRecipient(rid);
      if (match) setRecipientSearchQuery(match.full_name);
      setShowNewModal(true);
      setSearchParams({}, { replace: true }); // Clear param
    }
  }, [searchParams, recipients]);

  // Auto-scroll to bottom when messages change (unless scrolling to a specific message)
  useEffect(() => {
    if (scrollToMessageId && selectedConversation) {
      // Try to scroll to the target message
      const el = document.getElementById(`msg-${scrollToMessageId}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('message-highlight');
        setTimeout(() => el.classList.remove('message-highlight'), 2000);
        setScrollToMessageId(null);
      }
    } else if (!scrollToMessageId) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [selectedConversation?.messages, scrollToMessageId]);

  // Ctrl+F handler for in-thread search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'f' && selectedConversation) {
        e.preventDefault();
        setThreadSearchOpen(true);
        setTimeout(() => threadSearchInputRef.current?.focus(), 50);
      }
      if (e.key === 'Escape' && threadSearchOpen) {
        closeThreadSearch();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedConversation, threadSearchOpen]);

  // Poll active conversation more frequently
  useEffect(() => {
    if (!selectedConversation) return;

    const interval = setInterval(() => {
      refreshSelectedConversation();
    }, 15000);

    return () => clearInterval(interval);
  }, [selectedConversation?.id, messageOffset]);

  const loadConversations = async (reset = false) => {
    try {
      const offset = reset ? 0 : conversationOffset;
      const data = await messagesApi.listConversations({ skip: offset, limit: conversationLimit });
      setConversations((prev) => reset ? data : [...prev, ...data]);
      setConversationOffset(offset + data.length);
      setHasMoreConversations(data.length === conversationLimit);
      setLoading(false);
    } catch (err) {
      logger.error('Failed to load conversations', { error: err });
      setError('Failed to load conversations');
      setLoading(false);
    }
  };

  const loadRecipients = async () => {
    try {
      const data = await messagesApi.getRecipients();
      setRecipients(data);
    } catch (err) {
      logger.error('Failed to load recipients', { error: err });
    }
  };

  const refreshSelectedConversation = async () => {
    if (!selectedConversation) return;
    try {
      const detail = await messagesApi.getConversation(selectedConversation.id, { offset: 0, limit: messageLimit });
      setSelectedConversation((prev) => {
        if (!prev) return detail;
        const merged = mergeMessages(detail.messages, prev.messages);
        return { ...detail, messages: merged };
      });
    } catch (err) {
      logger.error('Failed to refresh conversation', { error: err });
    }
  };

  const selectConversation = async (id: number, targetMessageId?: number) => {
    setLoadingConversation(true);
    closeThreadSearch();
    try {
      // Load all messages to ensure the target message is visible
      const loadLimit = targetMessageId ? 200 : messageLimit;
      const detail = await messagesApi.getConversation(id, { offset: 0, limit: loadLimit });
      setSelectedConversation(detail);
      setMessageOffset(detail.messages.length);
      setHasMoreMessages(detail.messages.length < detail.messages_total);
      if (targetMessageId) {
        setScrollToMessageId(targetMessageId);
      }
      await messagesApi.markAsRead(id);
      loadConversations(true); // Refresh unread counts
    } catch (err) {
      logger.error('Failed to load conversation', { error: err });
      setError('Failed to load conversation');
    } finally {
      setLoadingConversation(false);
    }
  };

  const loadOlderMessages = async () => {
    if (!selectedConversation || !hasMoreMessages) return;
    try {
      const detail = await messagesApi.getConversation(selectedConversation.id, { offset: messageOffset, limit: messageLimit });
      setSelectedConversation((prev) => {
        if (!prev) return detail;
        const merged = mergeMessages(detail.messages, prev.messages);
        return { ...prev, messages: merged, messages_total: detail.messages_total };
      });
      const nextOffset = messageOffset + detail.messages.length;
      setMessageOffset(nextOffset);
      setHasMoreMessages(nextOffset < detail.messages_total);
    } catch (err) {
      logger.error('Failed to load older messages', { error: err });
    }
  };

  const mergeMessages = (older: ConversationDetail['messages'], current: ConversationDetail['messages']) => {
    const map = new Map<number, ConversationDetail['messages'][number]>();
    [...older, ...current].forEach((msg) => map.set(msg.id, msg));
    return Array.from(map.values()).sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
  };

  const handleSendMessage = async () => {
    if (!selectedConversation || !newMessage.trim() || sending) return;

    setSending(true);
    try {
      await messagesApi.sendMessage(selectedConversation.id, newMessage.trim());
      setNewMessage('');
      await refreshSelectedConversation();
      loadConversations(true);
    } catch (err) {
      logger.error('Failed to send message', { error: err });
      setError('Failed to send message');
    } finally {
      setSending(false);
    }
  };

  const handleCreateConversation = async () => {
    if (!selectedRecipient || !initialMessage.trim() || creatingConversation) return;

    setCreatingConversation(true);
    try {
      const conv = await messagesApi.createConversation({
        recipient_id: selectedRecipient,
        subject: newSubject.trim() || undefined,
        initial_message: initialMessage.trim(),
      });
      setShowNewModal(false);
      resetNewConversationForm();
      await loadConversations(true);
      setSelectedConversation(conv);
      setMessageOffset(conv.messages.length);
      setHasMoreMessages(conv.messages.length < conv.messages_total);
      logger.info('Created new conversation', { conversationId: conv.id });
    } catch (err) {
      logger.error('Failed to create conversation', { error: err });
      setError('Failed to create conversation');
    } finally {
      setCreatingConversation(false);
    }
  };

  const resetNewConversationForm = () => {
    setSelectedRecipient(null);
    setRecipientSearchQuery('');
    setRecipientSearchResults([]);
    setShowRecipientDropdown(false);
    setNewSubject('');
    setInitialMessage('');
  };

  const handleRecipientSearchChange = (value: string) => {
    setRecipientSearchQuery(value);
    setSelectedRecipient(null);

    if (recipientSearchDebounceRef.current) {
      clearTimeout(recipientSearchDebounceRef.current);
    }

    if (value.length < 2) {
      setRecipientSearchResults(recipients);
      setShowRecipientDropdown(value.length > 0 || recipients.length > 0);
      return;
    }

    setIsRecipientSearching(true);
    setShowRecipientDropdown(true);
    recipientSearchDebounceRef.current = setTimeout(async () => {
      try {
        const results = await messagesApi.getRecipients({ q: value });
        setRecipientSearchResults(results);
      } catch (err) {
        logger.error('Failed to search recipients', { error: err });
        setRecipientSearchResults([]);
      } finally {
        setIsRecipientSearching(false);
      }
    }, 300);
  };

  const handleRecipientSelect = (recipient: RecipientOption) => {
    setSelectedRecipient(recipient.user_id);
    setRecipientSearchQuery(recipient.full_name);
    setShowRecipientDropdown(false);
  };

  const performSearch = useCallback(async (query: string) => {
    if (query.length < 2) {
      setFilteredConversations([]);
      setSearchActive(false);
      setIsSearching(false);
      return;
    }
    setIsSearching(true);
    setSearchActive(true);
    try {
      const results = await messagesApi.listConversations({ q: query });
      setFilteredConversations(results);
    } catch (err) {
      logger.error('Failed to search messages', { error: err });
      setFilteredConversations([]);
    } finally {
      setIsSearching(false);
    }
  }, []);

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    if (searchDebounceRef.current) {
      clearTimeout(searchDebounceRef.current);
    }
    if (value.length < 2) {
      setFilteredConversations([]);
      setSearchActive(false);
      setIsSearching(false);
      return;
    }
    setIsSearching(true);
    searchDebounceRef.current = setTimeout(() => {
      performSearch(value);
    }, 300);
  };

  const clearSearch = () => {
    setSearchQuery('');
    setFilteredConversations([]);
    setSearchActive(false);
    setIsSearching(false);
    if (searchDebounceRef.current) {
      clearTimeout(searchDebounceRef.current);
    }
  };

  const highlightMatch = (text: string, query: string) => {
    if (!query || query.length < 2) return <>{text}</>;
    const parts: React.ReactNode[] = [];
    const lowerText = text.toLowerCase();
    const lowerQuery = query.toLowerCase();
    let lastIndex = 0;
    let idx = lowerText.indexOf(lowerQuery, lastIndex);
    let keyCounter = 0;
    while (idx !== -1) {
      if (idx > lastIndex) {
        parts.push(<span key={keyCounter++}>{text.slice(lastIndex, idx)}</span>);
      }
      parts.push(<mark key={keyCounter++}>{text.slice(idx, idx + query.length)}</mark>);
      lastIndex = idx + query.length;
      idx = lowerText.indexOf(lowerQuery, lastIndex);
    }
    if (lastIndex < text.length) {
      parts.push(<span key={keyCounter++}>{text.slice(lastIndex)}</span>);
    }
    return <>{parts}</>;
  };

  // In-thread search functions
  const handleThreadSearchChange = (value: string) => {
    setThreadSearchQuery(value);
    if (threadSearchDebounceRef.current) {
      clearTimeout(threadSearchDebounceRef.current);
    }
    if (value.length < 2 || !selectedConversation) {
      setThreadSearchMatches([]);
      setThreadSearchIndex(0);
      return;
    }
    threadSearchDebounceRef.current = setTimeout(() => {
      const lowerQuery = value.toLowerCase();
      const matches = selectedConversation.messages
        .filter((msg) => msg.content.toLowerCase().includes(lowerQuery))
        .map((msg) => msg.id);
      setThreadSearchMatches(matches);
      setThreadSearchIndex(0);
      // Scroll to first match
      if (matches.length > 0) {
        scrollToThreadMatch(matches[0]);
      }
    }, 200);
  };

  const scrollToThreadMatch = (messageId: number) => {
    const el = document.getElementById(`msg-${messageId}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  const navigateThreadSearch = (direction: 'prev' | 'next') => {
    if (threadSearchMatches.length === 0) return;
    let newIndex: number;
    if (direction === 'next') {
      newIndex = (threadSearchIndex + 1) % threadSearchMatches.length;
    } else {
      newIndex = (threadSearchIndex - 1 + threadSearchMatches.length) % threadSearchMatches.length;
    }
    setThreadSearchIndex(newIndex);
    scrollToThreadMatch(threadSearchMatches[newIndex]);
  };

  const closeThreadSearch = () => {
    setThreadSearchOpen(false);
    setThreadSearchQuery('');
    setThreadSearchMatches([]);
    setThreadSearchIndex(0);
    if (threadSearchDebounceRef.current) {
      clearTimeout(threadSearchDebounceRef.current);
    }
  };

  const getOtherParticipantName = (conv: ConversationDetail) => {
    if (conv.participant_1_id === user?.id) {
      return conv.participant_2_name;
    }
    return conv.participant_1_name;
  };

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (diffDays === 1) {
      return 'Yesterday';
    } else if (diffDays < 7) {
      return date.toLocaleDateString([], { weekday: 'short' });
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Your conversations" showBackButton>
        <div className="loading-container">
          <div className="loading-grid">
            <div className="loading-card">
              <div className="skeleton loading-line" />
              <div className="skeleton loading-line short" />
              <div className="skeleton loading-line" />
            </div>
            <div className="loading-card">
              <div className="skeleton loading-line" />
              <div className="skeleton loading-line short" />
              <div className="skeleton loading-line" />
            </div>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout welcomeSubtitle="Your conversations" showBackButton>
      {error && (
        <div className="error-banner">
          {error}
          <button onClick={() => setError('')}>&times;</button>
        </div>
      )}

      <div className={`messages-container${selectedConversation ? ' has-selection' : ''}`}>
        {/* Conversation List */}
        <aside className="conversation-list">
          <div className="list-header">
            <h2>Conversations</h2>
            <button className="new-message-btn" onClick={() => setShowNewModal(true)}>
              + New Message
            </button>
          </div>
          <div className="search-bar">
            <svg className="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              className="search-input"
              placeholder="Search messages..."
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
            />
            {searchQuery && (
              <button className="search-clear" onClick={clearSearch} aria-label="Clear search">
                &times;
              </button>
            )}
          </div>
          {searchActive ? (
            <div className="search-results">
              {isSearching ? (
                <div className="search-loading">Searching...</div>
              ) : filteredConversations.length === 0 ? (
                <div className="search-empty">No conversations matching &lsquo;{searchQuery}&rsquo;</div>
              ) : (
                <div className="conversations">
                  {filteredConversations.map((conv) => (
                    <div
                      key={conv.id}
                      className={`conversation-item ${selectedConversation?.id === conv.id ? 'active' : ''} ${conv.unread_count > 0 ? 'unread' : ''}`}
                      onClick={() => selectConversation(conv.id)}
                    >
                      <div className="conv-header">
                        <span className="conv-name">
                          {conv.other_participant_name}
                          {conv.other_participant_role === 'admin' && (
                            <span className="conv-role-badge admin">Admin</span>
                          )}
                        </span>
                        {conv.unread_count > 0 && (
                          <span className="unread-badge">{conv.unread_count}</span>
                        )}
                      </div>
                      {conv.student_name && (
                        <span className="conv-student">Re: {conv.student_name}</span>
                      )}
                      {conv.last_message_preview && (
                        <p className="conv-preview">{conv.last_message_preview}</p>
                      )}
                      {conv.last_message_at && (
                        <span className="conv-time">{formatTime(conv.last_message_at)}</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : conversations.length === 0 ? (
            <EmptyState
              icon={<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>}
              title="No messages yet"
              description="Start a conversation with your child's teacher."
              action={{ label: 'New Message', onClick: () => setShowNewModal(true) }}
              variant="compact"
            />
          ) : (
            <div className="conversations">
              {conversations.map((conv) => (
                <div
                  key={conv.id}
                  className={`conversation-item ${selectedConversation?.id === conv.id ? 'active' : ''} ${conv.unread_count > 0 ? 'unread' : ''}`}
                  onClick={() => selectConversation(conv.id)}
                >
                  <div className="conv-header">
                    <span className="conv-name">
                      {conv.other_participant_name}
                      {conv.other_participant_role === 'admin' && (
                        <span className="conv-role-badge admin">Admin</span>
                      )}
                    </span>
                    {conv.unread_count > 0 && (
                      <span className="unread-badge">{conv.unread_count}</span>
                    )}
                  </div>
                  {conv.student_name && (
                    <span className="conv-student">Re: {conv.student_name}</span>
                  )}
                  {conv.last_message_preview && (
                    <p className="conv-preview">{conv.last_message_preview}</p>
                  )}
                  {conv.last_message_at && (
                    <span className="conv-time">{formatTime(conv.last_message_at)}</span>
                  )}
                </div>
              ))}
            </div>
          )}
          {!searchActive && hasMoreConversations && (
            <div className="conversation-footer">
              <button onClick={() => loadConversations()} className="load-more-btn">
                Load more
              </button>
            </div>
          )}
        </aside>

        {/* Message Thread */}
        <main className="message-thread">
          {loadingConversation ? (
            <div className="no-selection">
              <div className="no-selection-content">
                <div className="skeleton" style={{ width: 40, height: 40, borderRadius: '50%', margin: '0 auto 12px' }} />
                <div className="skeleton" style={{ width: '60%', height: 14, margin: '0 auto 8px' }} />
                <div className="skeleton" style={{ width: '40%', height: 12, margin: '0 auto' }} />
              </div>
            </div>
          ) : selectedConversation ? (
            <>
              <div className="thread-header">
                <div className="thread-header-top">
                  <button className="mobile-back-btn" onClick={() => setSelectedConversation(null)}>&larr; Back</button>
                  <div className="thread-header-info">
                    <h2>{getOtherParticipantName(selectedConversation)}</h2>
                    {selectedConversation.student_name && (
                      <span className="thread-student">
                        Regarding: {selectedConversation.student_name}
                      </span>
                    )}
                    {selectedConversation.subject && (
                      <span className="thread-subject">{selectedConversation.subject}</span>
                    )}
                  </div>
                  <button
                    className="thread-search-toggle"
                    onClick={() => {
                      if (threadSearchOpen) {
                        closeThreadSearch();
                      } else {
                        setThreadSearchOpen(true);
                        setTimeout(() => threadSearchInputRef.current?.focus(), 50);
                      }
                    }}
                    aria-label="Search in conversation"
                    title="Search in conversation (Ctrl+F)"
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="11" cy="11" r="8" />
                      <line x1="21" y1="21" x2="16.65" y2="16.65" />
                    </svg>
                  </button>
                </div>
                {threadSearchOpen && (
                  <div className="thread-search-bar">
                    <input
                      ref={threadSearchInputRef}
                      type="text"
                      className="thread-search-input"
                      placeholder="Search in conversation..."
                      value={threadSearchQuery}
                      onChange={(e) => handleThreadSearchChange(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          navigateThreadSearch(e.shiftKey ? 'prev' : 'next');
                        }
                      }}
                    />
                    {threadSearchMatches.length > 0 && (
                      <span className="thread-search-count">
                        {threadSearchIndex + 1}/{threadSearchMatches.length}
                      </span>
                    )}
                    {threadSearchQuery.length >= 2 && threadSearchMatches.length === 0 && (
                      <span className="thread-search-count">No results</span>
                    )}
                    <button
                      className="thread-search-nav"
                      onClick={() => navigateThreadSearch('prev')}
                      disabled={threadSearchMatches.length === 0}
                      aria-label="Previous match"
                    >
                      &uarr;
                    </button>
                    <button
                      className="thread-search-nav"
                      onClick={() => navigateThreadSearch('next')}
                      disabled={threadSearchMatches.length === 0}
                      aria-label="Next match"
                    >
                      &darr;
                    </button>
                    <button className="thread-search-close" onClick={closeThreadSearch} aria-label="Close search">
                      &times;
                    </button>
                  </div>
                )}
              </div>
              <div className="messages-list">
                {hasMoreMessages && (
                  <div className="load-older">
                    <button className="load-more-btn" onClick={loadOlderMessages}>
                      Load older messages
                    </button>
                  </div>
                )}
                {selectedConversation.messages.map((msg) => {
                  const isThreadMatch = threadSearchMatches.includes(msg.id);
                  const isCurrentThreadMatch = threadSearchMatches[threadSearchIndex] === msg.id;
                  return (
                    <div
                      key={msg.id}
                      id={`msg-${msg.id}`}
                      className={`message ${msg.sender_id === user?.id ? 'sent' : 'received'}${isThreadMatch ? ' thread-match' : ''}${isCurrentThreadMatch ? ' thread-match-active' : ''}`}
                    >
                      <div className="message-content">
                        {threadSearchQuery.length >= 2 && isThreadMatch
                          ? highlightMatch(msg.content, threadSearchQuery)
                          : msg.content}
                      </div>
                      <div className="message-meta">
                        <span className="message-time">
                          {new Date(msg.created_at).toLocaleString()}
                        </span>
                        {msg.sender_id === user?.id && msg.is_read && (
                          <span className="read-indicator">Read</span>
                        )}
                      </div>
                    </div>
                  );
                })}
                <div ref={messagesEndRef} />
              </div>
              <div className="message-input">
                <textarea
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  placeholder="Type your message..."
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  disabled={sending}
                />
                <button
                  onClick={handleSendMessage}
                  disabled={!newMessage.trim() || sending}
                  className="send-button"
                >
                  {sending ? 'Sending...' : 'Send'}
                </button>
              </div>
            </>
          ) : (
            <div className="no-selection">
              <div className="no-selection-content">
                <span className="no-selection-icon">💬</span>
                <p>Select a conversation to view messages</p>
                <small>or start a new conversation</small>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* New Conversation Modal */}
      {showNewModal && (
        <div className="modal-overlay" onClick={() => setShowNewModal(false)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="New Message" ref={newConvModalRef} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>New Message</h2>
              <button className="modal-close" onClick={() => setShowNewModal(false)}>
                &times;
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>To:</label>
                <div className="recipient-search-wrapper">
                  <input
                    type="text"
                    className="recipient-search-input"
                    placeholder="Search for a user..."
                    value={recipientSearchQuery}
                    onChange={(e) => handleRecipientSearchChange(e.target.value)}
                    onFocus={() => {
                      if (recipientSearchQuery.length < 2 && recipients.length > 0) {
                        setRecipientSearchResults(recipients);
                        setShowRecipientDropdown(true);
                      } else if (recipientSearchQuery.length >= 2) {
                        setShowRecipientDropdown(true);
                      }
                    }}
                    onBlur={() => {
                      setTimeout(() => setShowRecipientDropdown(false), 200);
                    }}
                  />
                  {showRecipientDropdown && (
                    <div className="recipient-dropdown">
                      {isRecipientSearching ? (
                        <div className="recipient-dropdown-loading">Searching...</div>
                      ) : recipientSearchResults.length === 0 ? (
                        <div className="recipient-dropdown-empty">
                          {recipientSearchQuery.length >= 2 ? 'No users found' : 'Type to search...'}
                        </div>
                      ) : (
                        recipientSearchResults.map((r) => (
                          <div
                            key={r.user_id}
                            className="recipient-dropdown-item"
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => handleRecipientSelect(r)}
                          >
                            <span className="recipient-name">{r.full_name}</span>
                            <span className="recipient-role"> ({r.role})</span>
                            {r.student_names.length > 0 && (
                              <span className="recipient-students"> &mdash; {r.student_names.join(', ')}</span>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              </div>
              <div className="form-group">
                <label>Subject (optional):</label>
                <input
                  type="text"
                  value={newSubject}
                  onChange={(e) => setNewSubject(e.target.value)}
                  placeholder="e.g., Homework question"
                />
              </div>
              <div className="form-group">
                <label>Message:</label>
                <textarea
                  value={initialMessage}
                  onChange={(e) => setInitialMessage(e.target.value)}
                  placeholder="Write your message..."
                  rows={5}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="cancel-button" onClick={() => setShowNewModal(false)}>
                Cancel
              </button>
              <button
                className="send-button"
                onClick={handleCreateConversation}
                disabled={!selectedRecipient || !initialMessage.trim() || creatingConversation}
              >
                {creatingConversation ? 'Sending...' : 'Send Message'}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
