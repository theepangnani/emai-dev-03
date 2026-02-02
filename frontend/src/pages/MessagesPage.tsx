import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { messagesApi } from '../api/client';
import type {
  ConversationSummary,
  ConversationDetail,
  RecipientOption,
} from '../api/client';
import { NotificationBell } from '../components/NotificationBell';
import { logger } from '../utils/logger';
import './MessagesPage.css';

export function MessagesPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<ConversationDetail | null>(null);
  const [showNewModal, setShowNewModal] = useState(false);
  const [recipients, setRecipients] = useState<RecipientOption[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // New conversation form state
  const [selectedRecipient, setSelectedRecipient] = useState<number | null>(null);
  const [newSubject, setNewSubject] = useState('');
  const [initialMessage, setInitialMessage] = useState('');
  const [creatingConversation, setCreatingConversation] = useState(false);

  useEffect(() => {
    loadConversations();
    loadRecipients();

    // Poll for new messages every 30 seconds
    const interval = setInterval(loadConversations, 30000);
    return () => clearInterval(interval);
  }, []);

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
  }, [selectedConversation?.id]);

  const loadConversations = async () => {
    try {
      const data = await messagesApi.listConversations();
      setConversations(data);
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
      const detail = await messagesApi.getConversation(selectedConversation.id);
      setSelectedConversation(detail);
    } catch (err) {
      logger.error('Failed to refresh conversation', { error: err });
    }
  };

  const selectConversation = async (id: number) => {
    try {
      const detail = await messagesApi.getConversation(id);
      setSelectedConversation(detail);
      await messagesApi.markAsRead(id);
      loadConversations(); // Refresh unread counts
    } catch (err) {
      logger.error('Failed to load conversation', { error: err });
      setError('Failed to load conversation');
    }
  };

  const handleSendMessage = async () => {
    if (!selectedConversation || !newMessage.trim() || sending) return;

    setSending(true);
    try {
      await messagesApi.sendMessage(selectedConversation.id, newMessage.trim());
      setNewMessage('');
      await refreshSelectedConversation();
      loadConversations();
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
      await loadConversations();
      setSelectedConversation(conv);
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
      <div className="messages-page">
        <div className="loading-container">
          <p>Loading messages...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="messages-page">
      <header className="messages-header">
        <div className="header-left">
          <button className="back-button" onClick={() => navigate('/dashboard')}>
            &larr; Dashboard
          </button>
          <h1 className="page-title">Messages</h1>
        </div>
        <div className="header-right">
          <span className="user-name">{user?.full_name}</span>
          <NotificationBell />
          <button className="new-message-btn" onClick={() => setShowNewModal(true)}>
            + New Message
          </button>
          <button className="logout-button" onClick={logout}>
            Logout
          </button>
        </div>
      </header>

      {error && (
        <div className="error-banner">
          {error}
          <button onClick={() => setError('')}>&times;</button>
        </div>
      )}

      <div className="messages-container">
        {/* Conversation List */}
        <aside className="conversation-list">
          <div className="list-header">
            <h2>Conversations</h2>
          </div>
          {conversations.length === 0 ? (
            <div className="empty-state">
              <p>No conversations yet</p>
              <small>Start a new message to begin</small>
            </div>
          ) : (
            <div className="conversations">
              {conversations.map((conv) => (
                <div
                  key={conv.id}
                  className={`conversation-item ${selectedConversation?.id === conv.id ? 'active' : ''} ${conv.unread_count > 0 ? 'unread' : ''}`}
                  onClick={() => selectConversation(conv.id)}
                >
                  <div className="conv-header">
                    <span className="conv-name">{conv.other_participant_name}</span>
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
        </aside>

        {/* Message Thread */}
        <main className="message-thread">
          {selectedConversation ? (
            <>
              <div className="thread-header">
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
          <div className="modal" onClick={(e) => e.stopPropagation()}>
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
                    {user?.role === 'parent'
                      ? 'You can message teachers of your children\'s courses.'
                      : 'You can message parents of students in your courses.'}
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
    </div>
  );
}
