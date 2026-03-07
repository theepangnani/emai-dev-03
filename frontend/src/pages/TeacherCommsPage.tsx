import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { teacherCommsApi } from '../api/client';
import type { TeacherCommunication, EmailMonitoringStatus } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { ListSkeleton } from '../components/Skeleton';
import EmptyState from '../components/EmptyState';
import { useDebounce } from '../utils/useDebounce';
import { PageNav } from '../components/PageNav';
import './TeacherCommsPage.css';

export function TeacherCommsPage() {
  const navigate = useNavigate();
  const [communications, setCommunications] = useState<TeacherCommunication[]>([]);
  const [selected, setSelected] = useState<TeacherCommunication | null>(null);
  const [status, setStatus] = useState<EmailMonitoringStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState('');
  const [replyText, setReplyText] = useState('');
  const [replySending, setReplySending] = useState(false);
  const [replySuccess, setReplySuccess] = useState('');
  const [showReply, setShowReply] = useState(false);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 20;
  const debouncedSearch = useDebounce(search, 400);

  useEffect(() => {
    loadStatus();
  }, []);

  useEffect(() => {
    loadCommunications();
  }, [page, typeFilter, debouncedSearch]);

  const loadStatus = async () => {
    try {
      const data = await teacherCommsApi.getStatus();
      setStatus(data);
    } catch {
      // Silently fail
    }
  };

  const loadCommunications = async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (typeFilter) params.type = typeFilter;
      if (debouncedSearch) params.search = debouncedSearch;
      const data = await teacherCommsApi.list(params as Parameters<typeof teacherCommsApi.list>[0]);
      setCommunications(data.items);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load communications');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setPage(1);
  };

  const handleSync = async () => {
    if (syncing) return;
    setSyncing(true);
    try {
      const result = await teacherCommsApi.triggerSync();
      if (result.synced > 0) {
        loadCommunications();
        loadStatus();
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to sync communications');
    } finally {
      setSyncing(false);
    }
  };

  const handleReply = async () => {
    if (!selected || !replyText.trim() || replySending) return;
    setReplySending(true);
    setReplySuccess('');
    try {
      const result = await teacherCommsApi.reply(selected.id, replyText.trim());
      setReplySuccess(`Reply sent to ${result.to}`);
      setReplyText('');
      setShowReply(false);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to send reply');
    } finally {
      setReplySending(false);
    }
  };

  const handleEnableEmailMonitoring = async () => {
    try {
      const { authorization_url } = await teacherCommsApi.getEmailMonitoringAuthUrl();
      window.location.href = authorization_url;
    } catch {
      setError('Failed to start email monitoring setup. Please try again.');
    }
  };

  const selectCommunication = async (comm: TeacherCommunication) => {
    setSelected(comm);
    setShowReply(false);
    setReplyText('');
    setReplySuccess('');
    if (!comm.is_read) {
      try {
        await teacherCommsApi.markAsRead(comm.id);
        setCommunications((prev) =>
          prev.map((c) => (c.id === comm.id ? { ...c, is_read: true } : c))
        );
      } catch {
        // Silently fail
      }
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'email': return '\u{1F4E7}';
      case 'announcement': return '\u{1F4E2}';
      case 'comment': return '\u{1F4AC}';
      default: return '\u{1F4E8}';
    }
  };

  const formatTime = (dateString: string | null) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffHours < 1) return 'Just now';
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <DashboardLayout welcomeSubtitle="Teacher communications" showBackButton>
      <div className="teacher-comms-page">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Teacher Communications' },
        ]} />

        <div className="comms-toolbar">
        <div className="search-bar">
          <input
            type="text"
            placeholder="Search communications..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
          <button onClick={handleSearch}>Search</button>
        </div>
        <select
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
          className="type-filter"
        >
          <option value="">All Types</option>
          <option value="email">Emails</option>
          <option value="announcement">Announcements</option>
        </select>
        <button
          className="sync-button"
          onClick={handleSync}
          disabled={syncing || !status?.gmail_enabled}
        >
          {syncing ? 'Syncing...' : 'Sync Now'}
        </button>
      </div>

      {error && (
        <div className="error-banner" style={{ background: '#fef2f2', color: '#991b1b', padding: '8px 16px', borderRadius: '8px', margin: '0 16px 8px' }}>
          {error}
          <button onClick={() => setError('')} style={{ marginLeft: 8, background: 'none', border: 'none', cursor: 'pointer', color: '#991b1b' }}>&times;</button>
        </div>
      )}

      {status && !status.classroom_enabled && (
        <div className="connect-banner">
          <p>Connect your Google account to monitor teacher emails and announcements.</p>
          <button onClick={() => navigate('/dashboard')}>
            Go to Dashboard to Connect
          </button>
        </div>
      )}

      {status && status.classroom_enabled && !status.gmail_scope_granted && (
        <div className="connect-banner">
          <p>Enable email monitoring to sync teacher emails from Gmail. Classroom announcements are already available.</p>
          <button onClick={handleEnableEmailMonitoring}>
            Enable Email Monitoring
          </button>
        </div>
      )}

      <div className={`comms-container${selected ? ' has-selection' : ''}`}>
        <aside className="comms-list">
          {loading ? (
            <ListSkeleton rows={4} />
          ) : communications.length === 0 ? (
            <EmptyState
              title="No communications yet"
              description="Sync your account to fetch teacher emails and announcements"
              variant="compact"
            />
          ) : (
            <>
              {communications.map((comm) => (
                <div
                  key={comm.id}
                  className={`comm-item ${selected?.id === comm.id ? 'active' : ''} ${!comm.is_read ? 'unread' : ''}`}
                  onClick={() => selectCommunication(comm)}
                >
                  <div className="comm-item-header">
                    <span className="comm-type-icon">{getTypeIcon(comm.type)}</span>
                    <span className="comm-sender">{comm.sender_name || 'Unknown'}</span>
                    <span className="comm-time">{formatTime(comm.received_at)}</span>
                  </div>
                  <p className="comm-subject">{comm.subject || '(No Subject)'}</p>
                  {comm.ai_summary && (
                    <p className="comm-ai-preview">AI: {comm.ai_summary}</p>
                  )}
                  {!comm.is_read && <span className="unread-dot" />}
                </div>
              ))}
              {totalPages > 1 && (
                <div className="pagination">
                  <button disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</button>
                  <span>{page} / {totalPages}</span>
                  <button disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</button>
                </div>
              )}
            </>
          )}
        </aside>

        <main className="comms-detail">
          {selected ? (
            <div className="detail-content">
              <div className="detail-header">
                <button className="mobile-back-btn" onClick={() => setSelected(null)}>&larr; Back to list</button>
                <h2>{selected.subject || '(No Subject)'}</h2>
                <div className="detail-meta">
                  <span className="detail-sender">
                    From: {selected.sender_name}
                    {selected.sender_email && ` <${selected.sender_email}>`}
                  </span>
                  {selected.course_name && (
                    <span className="detail-course">Class: {selected.course_name}</span>
                  )}
                  {selected.received_at && (
                    <span className="detail-date">
                      {new Date(selected.received_at).toLocaleString()}
                    </span>
                  )}
                  <span className="detail-type">{getTypeIcon(selected.type)} {selected.type}</span>
                </div>
              </div>

              {selected.ai_summary && (
                <div className="ai-summary-card">
                  <h3>AI Summary</h3>
                  <p>{selected.ai_summary}</p>
                </div>
              )}

              <div className="detail-body">
                <h3>Full Message</h3>
                <div className="message-body">{selected.body || '(No content)'}</div>
              </div>

              {/* Reply Section */}
              {selected.sender_email && (
                <div className="reply-section">
                  {replySuccess && (
                    <div className="reply-success">{replySuccess}</div>
                  )}
                  {!showReply ? (
                    <button className="reply-btn" onClick={() => setShowReply(true)}>
                      Reply to {selected.sender_name || selected.sender_email}
                    </button>
                  ) : (
                    <div className="reply-compose">
                      <h3>Reply</h3>
                      <textarea
                        className="reply-textarea"
                        placeholder={`Reply to ${selected.sender_name || selected.sender_email}...`}
                        value={replyText}
                        onChange={(e) => setReplyText(e.target.value)}
                        rows={4}
                      />
                      <div className="reply-actions">
                        <button className="cancel-btn" onClick={() => { setShowReply(false); setReplyText(''); }}>
                          Cancel
                        </button>
                        <button
                          className="send-reply-btn"
                          onClick={handleReply}
                          disabled={replySending || !replyText.trim()}
                        >
                          {replySending ? 'Sending...' : 'Send Reply'}
                        </button>
                      </div>
                      <p className="reply-note">Sent via ClassBridge email on your behalf</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="no-selection">
              <div className="no-selection-content">
                <span className="no-selection-icon">{'\u{1F4E7}'}</span>
                <p>Select a communication to view details</p>
                <small>or sync to fetch new emails and announcements</small>
              </div>
            </div>
          )}
        </main>
      </div>
      </div>
    </DashboardLayout>
  );
}
