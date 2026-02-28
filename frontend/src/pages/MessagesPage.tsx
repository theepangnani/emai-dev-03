import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { messagesApi } from '../api/client';
import type {
  ConversationSummary,
  ConversationDetail,
  RecipientOption,
  MessageSearchResult,
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
  const [searchResults, setSearchResults] = useState<MessageSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchActive, setSearchActive] = useState(false);
  const searchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // New conversation form state
  const [selectedRecipient, setSelectedRecipient] = useState<number | null>(null);
  const [newSubject, setNewSubject] = useState('');
  const [initialMessage, setInitialMessage] = useState('');
  const [creatingConversation, setCreatingConversation] = useState(false);
  const newConvModalRef = useFocusTrap<HTMLDivElement>(showNewModal, () => setShowNewModal(false));

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
      setSelectedRecipient(Number(recipientId));
      setShowNewModal(true);
      setSearchParams({}, { replace: true }); // Clear param
    }
  }, [searchParams, recipients]);

  // Handle ?conversation= deep link param (#885)
  useEffect(() => {
    const conversationId = searchParams.get('conversation');
    if (conversationId && conversations.length > 0 && !selectedConversation) {
      const id = Number(conversationId);
      if (conversations.some(c => c.id === id)) {
        selectConversation(id);
      }
    }
  }, [searchParams, conversations]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [selectedConversation?.messages]);

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

  const selectConversation = async (id: number) => {
    setLoadingConversation(true);
    // Sync conversation ID to URL for deep linking (#885)
    const params = new URLSearchParams(searchParams);
    params.set('conversation', String(id));
    setSearchParams(params, { replace: true });
    try {
      const detail = await messagesApi.getConversation(id, { offset: 0, limit: messageLimit });
      setSelectedConversation(detail);
      setMessageOffset(detail.messages.length);
      setHasMoreMessages(detail.messages.length < detail.messages_total);
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
    setNewSubject('');
    setInitialMessage('');
  };

  const performSearch = useCallback(async (query: string) => {
    if (query.length < 2) {
      setSearchResults([]);
      setSearchActive(false);
      setIsSearching(false);
      return;
    }
    setIsSearching(true);
    setSearchActive(true);
    try {
      const results = await messagesApi.search(query);
      setSearchResults(results);
    } catch (err) {
      logger.error('Failed to search messages', { error: err });
      setSearchResults([]);
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
      setSearchResults([]);
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
    setSearchResults([]);
    setSearchActive(false);
    setIsSearching(false);
    if (searchDebounceRef.current) {
      clearTimeout(searchDebounceRef.current);
    }
  };

  const handleSearchResultClick = (result: MessageSearchResult) => {
    clearSearch();
    selectConversation(result.conversation_id);
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
              ) : searchResults.length === 0 ? (
                <div className="search-empty">No messages matching &lsquo;{searchQuery}&rsquo;</div>
              ) : (
                searchResults.map((result) => (
                  <div
                    key={`${result.conversation_id}-${result.message_id}`}
                    className="search-result-item"
                    onClick={() => handleSearchResultClick(result)}
                  >
                    {result.conversation_subject && (
                      <div className="search-result-subject">
                        {highlightMatch(result.conversation_subject, searchQuery)}
                      </div>
                    )}
                    <div className="search-result-content">
                      {highlightMatch(result.message_content.length > 120 ? result.message_content.slice(0, 120) + '...' : result.message_content, searchQuery)}
                    </div>
                    <div className="search-result-meta">
                      <span className="search-result-sender">{result.sender_name}</span>
                      <span className="search-result-time">{formatTime(result.sent_at)}</span>
                    </div>
                  </div>
                ))
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
                <button className="mobile-back-btn" onClick={() => setSelectedConversation(null)}>&larr; Back</button>
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
              <div className="messages-list">
                {hasMoreMessages && (
                  <div className="load-older">
                    <button className="load-more-btn" onClick={loadOlderMessages}>
                      Load older messages
                    </button>
                  </div>
                )}
                {selectedConversation.messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`message ${msg.sender_id === user?.id ? 'sent' : 'received'}`}
                  >
                    <div className="message-content">{msg.content}</div>
                    <div className="message-meta">
                      <span className="message-time">
                        {new Date(msg.created_at).toLocaleString()}
                      </span>
                      {msg.sender_id === user?.id && msg.is_read && (
                        <span className="read-indicator">Read</span>
                      )}
                    </div>
                  </div>
                ))}
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
              {recipients.length === 0 ? (
                <div className="no-recipients">
                  <p>No recipients available</p>
                  <small>
                    You can message teachers, parents, or admins linked to your account.
                  </small>
                </div>
              ) : (
                <>
                  <div className="form-group">
                    <label>To:</label>
                    <select
                      value={selectedRecipient || ''}
                      onChange={(e) => setSelectedRecipient(Number(e.target.value) || null)}
                    >
                      <option value="">Select a recipient...</option>
                      {recipients.map((r) => (
                        <option key={r.user_id} value={r.user_id}>
                          {r.full_name} ({r.role})
                          {r.student_names.length > 0 && ` - ${r.student_names.join(', ')}`}
                        </option>
                      ))}
                    </select>
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
                </>
              )}
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
