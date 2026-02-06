import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { teacherCommsApi } from '../api/client';
import type { TeacherCommunication, EmailMonitoringStatus } from '../api/client';
import { NotificationBell } from '../components/NotificationBell';
import { useDebounce } from '../utils/useDebounce';
import './TeacherCommsPage.css';

export function TeacherCommsPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [communications, setCommunications] = useState<TeacherCommunication[]>([]);
  const [selected, setSelected] = useState<TeacherCommunication | null>(null);
  const [status, setStatus] = useState<EmailMonitoringStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
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
    } catch {
      // Silently fail
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
    } catch {
      // Silently fail
    } finally {
      setSyncing(false);
    }
  };

  const selectCommunication = async (comm: TeacherCommunication) => {
    setSelected(comm);
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
    <div className="teacher-comms-page">
      <header className="comms-header">
        <div className="header-left">
          <button className="back-button" onClick={() => navigate('/dashboard')}>
            &larr; Dashboard
          </button>
          <h1 className="page-title">Teacher Communications</h1>
        </div>
        <div className="header-right">
          <span className="user-name">{user?.full_name}</span>
          <NotificationBell />
          <button className="logout-button" onClick={logout}>
            Logout
          </button>
        </div>
      </header>

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

      {status && !status.gmail_enabled && (
        <div className="connect-banner">
          <p>Connect your Google account to monitor teacher emails and announcements.</p>
          <button onClick={() => navigate('/dashboard')}>
            Go to Dashboard to Connect
          </button>
        </div>
      )}

      <div className="comms-container">
        <aside className="comms-list">
          {loading ? (
            <div className="empty-state"><p>Loading...</p></div>
          ) : communications.length === 0 ? (
            <div className="empty-state">
              <p>No communications yet</p>
              <small>Sync your account to fetch teacher emails and announcements</small>
            </div>
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
                <h2>{selected.subject || '(No Subject)'}</h2>
                <div className="detail-meta">
                  <span className="detail-sender">
                    From: {selected.sender_name}
                    {selected.sender_email && ` <${selected.sender_email}>`}
                  </span>
                  {selected.course_name && (
                    <span className="detail-course">Course: {selected.course_name}</span>
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
  );
}
