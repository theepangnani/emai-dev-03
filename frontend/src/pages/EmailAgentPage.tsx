/**
 * AI Email Agent Page — Phase 5.
 *
 * Tab-based inbox UI:
 *   Inbox | Sent | Drafts | Archived
 *
 * Features:
 *   - Thread list with AI summaries
 *   - Thread detail view with full message history
 *   - AI Compose modal (draft, improve, tone, language)
 *   - Reply suggestion
 *   - Action item extraction
 *   - Thread summarisation
 *   - Full-text search
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import {
  emailAgentApi,
  type EmailThreadSummary,
  type EmailThreadDetail,
  type EmailMessageItem,
  type AIDraftResponse,
} from '../api/emailAgent';
import './EmailAgentPage.css';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDateTime(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  return d.toLocaleDateString();
}

function stripHtml(html: string): string {
  return html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}

type Tab = 'inbox' | 'sent' | 'drafts' | 'archived';

// ─── Subcomponents ────────────────────────────────────────────────────────────

function ThreadSkeleton() {
  return (
    <div className="ea-thread-skeleton" aria-busy="true">
      <div className="skeleton ea-sk-subject" />
      <div className="skeleton ea-sk-snippet" />
      <div className="skeleton ea-sk-meta" />
    </div>
  );
}

interface ThreadCardProps {
  thread: EmailThreadSummary;
  selected: boolean;
  onClick: () => void;
}

function ThreadCard({ thread, selected, onClick }: ThreadCardProps) {
  const recipients = thread.recipient_names.length
    ? thread.recipient_names.join(', ')
    : thread.recipient_emails.join(', ');

  const snippet = thread.ai_summary
    ? thread.ai_summary
    : `${thread.message_count} message${thread.message_count !== 1 ? 's' : ''}`;

  return (
    <button
      className={`ea-thread-card${selected ? ' ea-thread-card--selected' : ''}`}
      onClick={onClick}
      aria-current={selected ? 'true' : undefined}
    >
      <div className="ea-thread-card-header">
        <span className="ea-thread-card-recipients" title={recipients}>
          {recipients || '(no recipients)'}
        </span>
        <span className="ea-thread-card-time">
          {formatDateTime(thread.last_message_at)}
        </span>
      </div>
      <div className="ea-thread-card-subject">{thread.subject}</div>
      <div className="ea-thread-card-snippet">{snippet}</div>
      {thread.tags.length > 0 && (
        <div className="ea-thread-card-tags">
          {thread.tags.map((tag) => (
            <span key={tag} className="ea-tag">{tag}</span>
          ))}
        </div>
      )}
    </button>
  );
}

interface MessageBubbleProps {
  msg: EmailMessageItem;
}

function MessageBubble({ msg }: MessageBubbleProps) {
  const isOutbound = msg.direction === 'outbound';
  const sender = msg.from_name || msg.from_email;
  const time = formatDateTime(msg.sent_at || msg.received_at || msg.created_at);
  const body = msg.body_html ? stripHtml(msg.body_html) : msg.body_text;

  return (
    <div className={`ea-msg-bubble${isOutbound ? ' ea-msg-bubble--outbound' : ' ea-msg-bubble--inbound'}`}>
      <div className="ea-msg-meta">
        <span className="ea-msg-sender">{isOutbound ? 'You' : sender}</span>
        <span className="ea-msg-time">{time}</span>
        {msg.ai_draft && (
          <span className="ea-msg-ai-badge" title={`AI-drafted (${msg.ai_tone || 'formal'})`}>
            AI
          </span>
        )}
      </div>
      <div className="ea-msg-body">{body}</div>
    </div>
  );
}

// ─── AI Compose Modal ─────────────────────────────────────────────────────────

interface ComposeModalProps {
  onClose: () => void;
  onSent: () => void;
}

function AIComposeModal({ onClose, onSent }: ComposeModalProps) {
  const [prompt, setPrompt] = useState('');
  const [context, setContext] = useState('');
  const [tone, setTone] = useState<'formal' | 'friendly' | 'concise' | 'empathetic'>('formal');
  const [language, setLanguage] = useState<'en' | 'fr'>('en');
  const [draft, setDraft] = useState<AIDraftResponse | null>(null);
  const [toField, setToField] = useState('');
  const [improveInstruction, setImproveInstruction] = useState('');
  const [generating, setGenerating] = useState(false);
  const [improving, setImproving] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    setGenerating(true);
    setError(null);
    try {
      const res = await emailAgentApi.draftWithAI({ prompt, context, tone, language });
      setDraft(res.data);
    } catch {
      setError('Failed to generate draft. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  const handleImprove = async (instruction: string) => {
    if (!draft) return;
    setImproving(true);
    setError(null);
    try {
      const res = await emailAgentApi.improveDraft({
        current_body: draft.body,
        instruction,
      });
      setDraft({ ...draft, body: res.data.body });
      setImproveInstruction('');
    } catch {
      setError('Failed to improve draft.');
    } finally {
      setImproving(false);
    }
  };

  const handleSend = async () => {
    if (!draft || !toField.trim()) return;
    setSending(true);
    setError(null);
    try {
      const recipients = toField.split(',').map((e) => e.trim()).filter(Boolean);
      await emailAgentApi.sendMessage({
        recipient_emails: recipients,
        subject: draft.subject,
        body_text: draft.body,
        ai_draft: true,
        ai_tone: draft.tone,
      });
      onSent();
      onClose();
    } catch {
      setError('Failed to send email.');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="ea-modal-overlay" role="dialog" aria-modal="true" aria-label="AI Email Composer">
      <div className="ea-modal">
        <div className="ea-modal-header">
          <h2 className="ea-modal-title">AI Email Composer</h2>
          <button className="ea-modal-close" onClick={onClose} aria-label="Close">&#x2715;</button>
        </div>

        {error && <div className="ea-error">{error}</div>}

        <div className="ea-modal-body">
          <label className="ea-label">What do you need to communicate?</label>
          <textarea
            className="ea-textarea"
            rows={3}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="e.g. Ask Ms. Johnson about extra help for the upcoming exam..."
          />

          <label className="ea-label">Context</label>
          <input
            className="ea-input"
            value={context}
            onChange={(e) => setContext(e.target.value)}
            placeholder="e.g. My child: Emma, Grade 10, struggling with algebra"
          />

          <div className="ea-row">
            <div className="ea-field">
              <label className="ea-label">Tone</label>
              <select
                className="ea-select"
                value={tone}
                onChange={(e) => setTone(e.target.value as typeof tone)}
              >
                <option value="formal">Formal</option>
                <option value="friendly">Friendly</option>
                <option value="concise">Concise</option>
                <option value="empathetic">Empathetic</option>
              </select>
            </div>
            <div className="ea-field">
              <label className="ea-label">Language</label>
              <select
                className="ea-select"
                value={language}
                onChange={(e) => setLanguage(e.target.value as typeof language)}
              >
                <option value="en">English</option>
                <option value="fr">French</option>
              </select>
            </div>
          </div>

          <button
            className="ea-btn ea-btn--primary"
            onClick={handleGenerate}
            disabled={generating || !prompt.trim()}
          >
            {generating ? 'Generating...' : 'Generate Draft'}
          </button>

          {draft && (
            <>
              <hr className="ea-divider" />

              <label className="ea-label">To</label>
              <input
                className="ea-input"
                value={toField}
                onChange={(e) => setToField(e.target.value)}
                placeholder="teacher@school.com, another@school.com"
              />

              <label className="ea-label">Subject</label>
              <input
                className="ea-input"
                value={draft.subject}
                onChange={(e) => setDraft({ ...draft, subject: e.target.value })}
              />

              <label className="ea-label">Body</label>
              <textarea
                className="ea-textarea ea-textarea--body"
                rows={8}
                value={draft.body}
                onChange={(e) => setDraft({ ...draft, body: e.target.value })}
              />

              <div className="ea-improve-row">
                <input
                  className="ea-input ea-input--grow"
                  value={improveInstruction}
                  onChange={(e) => setImproveInstruction(e.target.value)}
                  placeholder='Improve instruction (e.g. "make it shorter")'
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && improveInstruction.trim()) {
                      handleImprove(improveInstruction);
                    }
                  }}
                />
                <button
                  className="ea-btn ea-btn--secondary"
                  onClick={() => handleImprove(improveInstruction)}
                  disabled={improving || !improveInstruction.trim()}
                >
                  {improving ? '...' : 'Improve'}
                </button>
              </div>

              <div className="ea-quick-improve">
                {['Make more concise', 'More formal', 'Translate to French'].map((instr) => (
                  <button
                    key={instr}
                    className="ea-btn ea-btn--ghost ea-btn--sm"
                    onClick={() => handleImprove(instr)}
                    disabled={improving}
                  >
                    {instr}
                  </button>
                ))}
              </div>

              <div className="ea-modal-actions">
                <button
                  className="ea-btn ea-btn--primary"
                  onClick={handleSend}
                  disabled={sending || !toField.trim()}
                >
                  {sending ? 'Sending...' : 'Send Email'}
                </button>
                <button className="ea-btn ea-btn--secondary" onClick={onClose}>
                  Cancel
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Thread Detail Panel ──────────────────────────────────────────────────────

interface ThreadDetailProps {
  threadId: number;
  onRefreshList: () => void;
}

function ThreadDetailPanel({ threadId, onRefreshList }: ThreadDetailProps) {
  const [thread, setThread] = useState<EmailThreadDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summarising, setSummarising] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [actionItems, setActionItems] = useState<string[] | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [suggestedReply, setSuggestedReply] = useState<string | null>(null);
  const [replyBody, setReplyBody] = useState('');
  const [sendingReply, setSendingReply] = useState(false);
  const [replyError, setReplyError] = useState<string | null>(null);

  const loadThread = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await emailAgentApi.getThread(threadId);
      setThread(res.data);
    } catch {
      setError('Failed to load thread.');
    } finally {
      setLoading(false);
    }
  }, [threadId]);

  useEffect(() => {
    loadThread();
    setActionItems(null);
    setSuggestedReply(null);
    setReplyBody('');
  }, [loadThread]);

  const handleSummarise = async () => {
    if (!thread) return;
    setSummarising(true);
    try {
      const res = await emailAgentApi.summarizeThread(thread.id);
      setThread({ ...thread, ai_summary: res.data.summary });
    } finally {
      setSummarising(false);
    }
  };

  const handleSuggestReply = async () => {
    if (!thread) return;
    setSuggesting(true);
    try {
      const res = await emailAgentApi.suggestReply(thread.id);
      setSuggestedReply(res.data.suggested_reply);
      setReplyBody(res.data.suggested_reply);
    } finally {
      setSuggesting(false);
    }
  };

  const handleExtractActions = async () => {
    if (!thread) return;
    setExtracting(true);
    try {
      const res = await emailAgentApi.extractActionItems(thread.id);
      setActionItems(res.data.action_items);
    } finally {
      setExtracting(false);
    }
  };

  const handleSendReply = async () => {
    if (!thread || !replyBody.trim()) return;
    setSendingReply(true);
    setReplyError(null);
    try {
      await emailAgentApi.sendMessage({
        thread_id: thread.id,
        recipient_emails: thread.recipient_emails,
        recipient_names: thread.recipient_names,
        subject: `Re: ${thread.subject}`,
        body_text: replyBody,
      });
      setReplyBody('');
      setSuggestedReply(null);
      await loadThread();
      onRefreshList();
    } catch {
      setReplyError('Failed to send reply.');
    } finally {
      setSendingReply(false);
    }
  };

  if (loading) {
    return (
      <div className="ea-detail-panel ea-detail-panel--loading">
        <div className="ea-spinner" aria-label="Loading thread" />
      </div>
    );
  }

  if (error || !thread) {
    return (
      <div className="ea-detail-panel ea-detail-panel--error">
        <p>{error || 'Thread not found.'}</p>
      </div>
    );
  }

  return (
    <div className="ea-detail-panel">
      {/* Header */}
      <div className="ea-detail-header">
        <h2 className="ea-detail-subject">{thread.subject}</h2>
        <div className="ea-detail-ai-actions">
          <button
            className="ea-btn ea-btn--ghost ea-btn--sm"
            onClick={handleSummarise}
            disabled={summarising}
            title="Generate AI summary"
          >
            {summarising ? 'Summarising...' : 'AI Summary'}
          </button>
          <button
            className="ea-btn ea-btn--ghost ea-btn--sm"
            onClick={handleExtractActions}
            disabled={extracting}
            title="Extract action items"
          >
            {extracting ? 'Extracting...' : 'Action Items'}
          </button>
        </div>
      </div>

      {/* AI Summary */}
      {thread.ai_summary && (
        <div className="ea-detail-summary">
          <span className="ea-detail-summary-label">AI Summary</span>
          <p className="ea-detail-summary-text">{thread.ai_summary}</p>
        </div>
      )}

      {/* Action Items */}
      {actionItems && actionItems.length > 0 && (
        <div className="ea-detail-actions-box">
          <span className="ea-detail-summary-label">Action Items</span>
          <ul className="ea-action-list">
            {actionItems.map((item, i) => (
              <li key={i} className="ea-action-item">
                <span className="ea-action-bullet">&#10003;</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Message list */}
      <div className="ea-messages-scroll">
        {thread.messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}
      </div>

      {/* Reply panel */}
      <div className="ea-reply-panel">
        {replyError && <div className="ea-error">{replyError}</div>}
        <textarea
          className="ea-textarea ea-textarea--reply"
          rows={4}
          value={replyBody}
          onChange={(e) => setReplyBody(e.target.value)}
          placeholder="Write your reply..."
        />
        <div className="ea-reply-actions">
          <button
            className="ea-btn ea-btn--primary"
            onClick={handleSendReply}
            disabled={sendingReply || !replyBody.trim()}
          >
            {sendingReply ? 'Sending...' : 'Send Reply'}
          </button>
          <button
            className="ea-btn ea-btn--secondary"
            onClick={handleSuggestReply}
            disabled={suggesting}
          >
            {suggesting ? 'Suggesting...' : 'AI Reply Suggestion'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function EmailAgentPage() {
  const [activeTab, setActiveTab] = useState<Tab>('inbox');
  const [threads, setThreads] = useState<EmailThreadSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedThreadId, setSelectedThreadId] = useState<number | null>(null);
  const [showCompose, setShowCompose] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<EmailThreadSummary[] | null>(null);
  const [searching, setSearching] = useState(false);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadThreads = useCallback(async () => {
    setLoading(true);
    try {
      const res = await emailAgentApi.getThreads({ tab: activeTab });
      setThreads(res.data);
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    loadThreads();
    setSelectedThreadId(null);
    setSearchResults(null);
    setSearchQuery('');
  }, [loadThreads]);

  // Debounced search
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await emailAgentApi.search({ q: searchQuery });
        // Convert search results (messages) to thread summaries for display
        const threadIds = [...new Set(res.data.results.map((m) => m.thread_id))];
        const matchedThreads = threads.filter((t) => threadIds.includes(t.id));
        setSearchResults(matchedThreads);
      } finally {
        setSearching(false);
      }
    }, 400);
    return () => {
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    };
  }, [searchQuery, threads]);

  const displayedThreads = searchResults !== null ? searchResults : threads;

  const tabs: { key: Tab; label: string }[] = [
    { key: 'inbox', label: 'Inbox' },
    { key: 'sent', label: 'Sent' },
    { key: 'drafts', label: 'Drafts' },
    { key: 'archived', label: 'Archived' },
  ];

  return (
    <DashboardLayout>
      <div className="ea-page">
        {/* Page header */}
        <div className="ea-page-header">
          <div className="ea-page-title-row">
            <h1 className="ea-page-title">AI Email Agent</h1>
            <div className="ea-page-header-actions">
              <button
                className="ea-btn ea-btn--primary"
                onClick={() => setShowCompose(true)}
              >
                Compose with AI
              </button>
            </div>
          </div>

          {/* Tabs + Search */}
          <div className="ea-tabs-row">
            <nav className="ea-tabs" role="tablist">
              {tabs.map(({ key, label }) => (
                <button
                  key={key}
                  role="tab"
                  aria-selected={activeTab === key}
                  className={`ea-tab${activeTab === key ? ' ea-tab--active' : ''}`}
                  onClick={() => setActiveTab(key)}
                >
                  {label}
                </button>
              ))}
            </nav>
            <div className="ea-search-wrapper">
              <input
                type="search"
                className="ea-search-input"
                placeholder="Search emails..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Search emails"
              />
              {searching && <span className="ea-search-spinner" aria-hidden="true" />}
            </div>
          </div>
        </div>

        {/* Main content: thread list + detail */}
        <div className="ea-content">
          {/* Thread list */}
          <div className="ea-thread-list" role="list" aria-label="Email threads">
            {loading ? (
              [1, 2, 3].map((i) => <ThreadSkeleton key={i} />)
            ) : displayedThreads.length === 0 ? (
              <div className="ea-empty">
                <p>
                  {searchQuery
                    ? 'No results found.'
                    : `No ${activeTab} emails yet.`}
                </p>
              </div>
            ) : (
              displayedThreads.map((t) => (
                <ThreadCard
                  key={t.id}
                  thread={t}
                  selected={selectedThreadId === t.id}
                  onClick={() => setSelectedThreadId(t.id)}
                />
              ))
            )}
          </div>

          {/* Thread detail */}
          <div className="ea-detail-area">
            {selectedThreadId ? (
              <ThreadDetailPanel
                key={selectedThreadId}
                threadId={selectedThreadId}
                onRefreshList={loadThreads}
              />
            ) : (
              <div className="ea-detail-placeholder">
                <p>Select a thread to view messages</p>
              </div>
            )}
          </div>
        </div>

        {/* AI Compose modal */}
        {showCompose && (
          <AIComposeModal
            onClose={() => setShowCompose(false)}
            onSent={loadThreads}
          />
        )}
      </div>
    </DashboardLayout>
  );
}
