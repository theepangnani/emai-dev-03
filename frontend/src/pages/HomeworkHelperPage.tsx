import { useState, useRef, useEffect } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import {
  homeworkHelpApi,
  type HelpMode,
  type HomeworkHelpResponse,
  type HomeworkSessionSummary,
  type SavedSolutionOut,
  type SubjectArea,
} from '../api/homeworkHelp';
import './HomeworkHelperPage.css';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SUBJECTS: { value: SubjectArea; label: string; icon: string; color: string }[] = [
  { value: 'math', label: 'Math', icon: '∑', color: 'math' },
  { value: 'science', label: 'Science', icon: '⚗', color: 'science' },
  { value: 'english', label: 'English', icon: '✍', color: 'english' },
  { value: 'history', label: 'History', icon: '🏛', color: 'history' },
  { value: 'french', label: 'French', icon: '🇫🇷', color: 'french' },
  { value: 'geography', label: 'Geography', icon: '🌍', color: 'geography' },
  { value: 'other', label: 'Other', icon: '📚', color: 'other' },
];

const MODES: { value: HelpMode; label: string; description: string }[] = [
  { value: 'hint', label: 'Get a Hint', description: '1–2 hints to help you figure it out' },
  { value: 'explain', label: 'Explain It', description: 'Step-by-step concept explanation' },
  { value: 'solve', label: 'Show Solution', description: 'Full step-by-step solution' },
  { value: 'check', label: 'Check My Work', description: 'Verify your attempt and find errors' },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatResponse(text: string): JSX.Element {
  const lines = text.split('\n').filter((l) => l.trim() !== '');
  const elements: JSX.Element[] = [];
  let stepBuffer: string[] = [];
  let keyIdx = 0;

  const flushSteps = () => {
    if (stepBuffer.length === 0) return;
    elements.push(
      <ol key={`steps-${keyIdx++}`} className="hw-steps-list">
        {stepBuffer.map((step, i) => (
          <li key={i}>{step}</li>
        ))}
      </ol>,
    );
    stepBuffer = [];
  };

  for (const line of lines) {
    const stepMatch = line.match(/^\d+[\.\)]\s+(.+)$/);
    if (stepMatch) {
      stepBuffer.push(stepMatch[1]);
    } else {
      flushSteps();
      const boldLine = line.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      elements.push(
        <p key={`p-${keyIdx++}`} dangerouslySetInnerHTML={{ __html: boldLine }} />,
      );
    }
  }
  flushSteps();

  return <>{elements}</>;
}

function truncate(text: string, max = 80): string {
  return text.length > max ? text.slice(0, max) + '…' : text;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function HomeworkHelperPage() {
  // Form state
  const [selectedSubject, setSelectedSubject] = useState<SubjectArea>('math');
  const [selectedMode, setSelectedMode] = useState<HelpMode>('hint');
  const [question, setQuestion] = useState('');
  const [context, setContext] = useState(''); // for "check" mode

  // Conversation state
  const [currentSession, setCurrentSession] = useState<HomeworkHelpResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Follow-up state
  const [followUpText, setFollowUpText] = useState('');
  const [followUpLoading, setFollowUpLoading] = useState(false);

  // Save solution state
  const [saveTitle, setSaveTitle] = useState('');
  const [saveTags, setSaveTags] = useState('');
  const [saveLoading, setSaveLoading] = useState(false);
  const [savedId, setSavedId] = useState<number | null>(null);

  // Sidebar state
  const [activeTab, setActiveTab] = useState<'history' | 'saved'>('history');
  const [sessions, setSessions] = useState<HomeworkSessionSummary[]>([]);
  const [savedSolutions, setSavedSolutions] = useState<SavedSolutionOut[]>([]);
  const [historySubjectFilter, setHistorySubjectFilter] = useState<SubjectArea | ''>('');
  const [savedSearch, setSavedSearch] = useState('');
  const [sidebarLoading, setSidebarLoading] = useState(false);

  const responseRef = useRef<HTMLDivElement>(null);

  // Load sidebar data on mount
  useEffect(() => {
    loadSessions();
    loadSavedSolutions();
  }, []);

  // Scroll to response when it arrives
  useEffect(() => {
    if (currentSession && responseRef.current) {
      responseRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [currentSession]);

  const loadSessions = async (subject?: SubjectArea) => {
    setSidebarLoading(true);
    try {
      const data = await homeworkHelpApi.getSessions(subject || undefined);
      setSessions(data);
    } catch {
      // Silently fail
    } finally {
      setSidebarLoading(false);
    }
  };

  const loadSavedSolutions = async () => {
    try {
      const data = await homeworkHelpApi.getSavedSolutions();
      setSavedSolutions(data);
    } catch {
      // Silently fail
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    setCurrentSession(null);
    setSavedId(null);
    setSaveTitle('');
    setSaveTags('');

    try {
      const response = await homeworkHelpApi.getHelp({
        subject: selectedSubject,
        question: question.trim(),
        mode: selectedMode,
        context: selectedMode === 'check' && context.trim() ? context.trim() : undefined,
      });
      setCurrentSession(response);
      await loadSessions(historySubjectFilter || undefined);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to get help. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleFollowUp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!followUpText.trim() || !currentSession) return;
    setFollowUpLoading(true);
    setError(null);

    try {
      const response = await homeworkHelpApi.followUp({
        session_id: currentSession.session_id,
        follow_up: followUpText.trim(),
      });
      setCurrentSession((prev) =>
        prev ? { ...prev, response: response.response } : prev,
      );
      setFollowUpText('');
      await loadSessions(historySubjectFilter || undefined);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to send follow-up.';
      setError(msg);
    } finally {
      setFollowUpLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!saveTitle.trim() || !currentSession) return;
    setSaveLoading(true);

    try {
      const tags = saveTags
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean);
      const saved = await homeworkHelpApi.saveSolution(currentSession.session_id, {
        title: saveTitle.trim(),
        tags,
      });
      setSavedId(saved.id);
      await loadSavedSolutions();
      await loadSessions(historySubjectFilter || undefined);
    } catch {
      setError('Failed to save solution.');
    } finally {
      setSaveLoading(false);
    }
  };

  const handleDeleteSaved = async (savedId: number) => {
    try {
      await homeworkHelpApi.deleteSavedSolution(savedId);
      setSavedSolutions((prev) => prev.filter((s) => s.id !== savedId));
    } catch {
      // Silently fail
    }
  };

  const handleHistoryFilterChange = (subject: SubjectArea | '') => {
    setHistorySubjectFilter(subject);
    loadSessions(subject || undefined);
  };

  const loadSessionIntoChat = (sess: HomeworkSessionSummary) => {
    setSelectedSubject(sess.subject);
    setSelectedMode(sess.mode);
    setQuestion(sess.question);
    setCurrentSession({
      session_id: sess.id,
      subject: sess.subject,
      mode: sess.mode,
      question: sess.question,
      response: sess.response,
    });
    setSavedId(null);
    setSaveTitle('');
    setSaveTags('');
  };

  const filteredSavedSolutions = savedSolutions.filter((s) => {
    if (!savedSearch.trim()) return true;
    const q = savedSearch.toLowerCase();
    return (
      s.title.toLowerCase().includes(q) ||
      s.question.toLowerCase().includes(q) ||
      (s.tags || []).some((t) => t.toLowerCase().includes(q))
    );
  });

  const subjectColor = SUBJECTS.find((s) => s.value === selectedSubject)?.color || 'other';

  return (
    <DashboardLayout welcomeSubtitle="AI Homework Helper">
      <div className="hw-page">
        {/* Main chat area */}
        <div className="hw-main">
          <div className="hw-header">
            <h1 className="hw-title">AI Homework Helper</h1>
            <p className="hw-subtitle">Get hints, explanations, solutions, or check your work — powered by AI.</p>
          </div>

          {/* Subject selector */}
          <div className="hw-section">
            <h2 className="hw-section-label">Choose a subject</h2>
            <div className="hw-subjects">
              {SUBJECTS.map((sub) => (
                <button
                  key={sub.value}
                  className={`hw-subject-btn hw-subject-${sub.color}${selectedSubject === sub.value ? ' active' : ''}`}
                  onClick={() => setSelectedSubject(sub.value)}
                  type="button"
                >
                  <span className="hw-subject-icon">{sub.icon}</span>
                  <span className="hw-subject-label">{sub.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Mode tabs */}
          <div className="hw-section">
            <h2 className="hw-section-label">What do you need?</h2>
            <div className="hw-mode-tabs">
              {MODES.map((mode) => (
                <button
                  key={mode.value}
                  className={`hw-mode-tab${selectedMode === mode.value ? ' active' : ''}`}
                  onClick={() => setSelectedMode(mode.value)}
                  type="button"
                >
                  <span className="hw-mode-label">{mode.label}</span>
                  <span className="hw-mode-desc">{mode.description}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Question form */}
          <form className="hw-form" onSubmit={handleSubmit}>
            <div className="hw-section">
              <label htmlFor="hw-question" className="hw-section-label">
                Your question
              </label>
              <textarea
                id="hw-question"
                className="hw-textarea"
                placeholder="Type your homework question here..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows={4}
                required
              />
            </div>

            {selectedMode === 'check' && (
              <div className="hw-section">
                <label htmlFor="hw-context" className="hw-section-label">
                  Your attempt (required for Check My Work)
                </label>
                <textarea
                  id="hw-context"
                  className="hw-textarea"
                  placeholder="Paste or type your work/answer here so the AI can check it..."
                  value={context}
                  onChange={(e) => setContext(e.target.value)}
                  rows={3}
                />
              </div>
            )}

            <button
              type="submit"
              className={`hw-submit-btn hw-subject-${subjectColor}`}
              disabled={loading || !question.trim()}
            >
              {loading ? 'Thinking...' : 'Get Help'}
            </button>
          </form>

          {error && <div className="hw-error">{error}</div>}

          {/* AI response */}
          {currentSession && (
            <div className="hw-response-section" ref={responseRef}>
              <div className={`hw-response-bubble hw-subject-${subjectColor}`}>
                <div className="hw-response-meta">
                  <span className="hw-response-mode">
                    {MODES.find((m) => m.value === currentSession.mode)?.label}
                  </span>
                  <span className="hw-response-subject">
                    {SUBJECTS.find((s) => s.value === currentSession.subject)?.label}
                  </span>
                </div>
                <div className="hw-response-text">
                  {formatResponse(currentSession.response)}
                </div>
              </div>

              {/* Follow-up */}
              <form className="hw-followup-form" onSubmit={handleFollowUp}>
                <input
                  className="hw-followup-input"
                  type="text"
                  placeholder="Ask a follow-up question..."
                  value={followUpText}
                  onChange={(e) => setFollowUpText(e.target.value)}
                />
                <button
                  type="submit"
                  className="hw-followup-btn"
                  disabled={followUpLoading || !followUpText.trim()}
                >
                  {followUpLoading ? '...' : 'Ask'}
                </button>
              </form>

              {/* Save solution */}
              {!savedId ? (
                <form className="hw-save-form" onSubmit={handleSave}>
                  <input
                    className="hw-save-input"
                    type="text"
                    placeholder="Save this solution as... (title)"
                    value={saveTitle}
                    onChange={(e) => setSaveTitle(e.target.value)}
                  />
                  <input
                    className="hw-save-input"
                    type="text"
                    placeholder="Tags (comma separated, optional)"
                    value={saveTags}
                    onChange={(e) => setSaveTags(e.target.value)}
                  />
                  <button
                    type="submit"
                    className="hw-save-btn"
                    disabled={saveLoading || !saveTitle.trim()}
                  >
                    {saveLoading ? 'Saving...' : 'Save This Solution'}
                  </button>
                </form>
              ) : (
                <div className="hw-save-success">Solution saved!</div>
              )}
            </div>
          )}
        </div>

        {/* Sidebar */}
        <aside className="hw-sidebar">
          <div className="hw-sidebar-tabs">
            <button
              className={`hw-sidebar-tab${activeTab === 'history' ? ' active' : ''}`}
              onClick={() => setActiveTab('history')}
            >
              Recent Sessions
            </button>
            <button
              className={`hw-sidebar-tab${activeTab === 'saved' ? ' active' : ''}`}
              onClick={() => setActiveTab('saved')}
            >
              Saved Solutions
            </button>
          </div>

          {activeTab === 'history' && (
            <div className="hw-history">
              <select
                className="hw-history-filter"
                value={historySubjectFilter}
                onChange={(e) => handleHistoryFilterChange(e.target.value as SubjectArea | '')}
              >
                <option value="">All subjects</option>
                {SUBJECTS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>

              {sidebarLoading && <div className="hw-sidebar-loading">Loading...</div>}

              {!sidebarLoading && sessions.length === 0 && (
                <div className="hw-sidebar-empty">No sessions yet. Ask your first question!</div>
              )}

              <div className="hw-history-list">
                {sessions.map((sess) => {
                  const subMeta = SUBJECTS.find((s) => s.value === sess.subject);
                  return (
                    <button
                      key={sess.id}
                      className={`hw-history-item hw-subject-${subMeta?.color || 'other'}`}
                      onClick={() => loadSessionIntoChat(sess)}
                    >
                      <div className="hw-history-item-top">
                        <span className="hw-history-icon">{subMeta?.icon}</span>
                        <span className="hw-history-subject">{subMeta?.label}</span>
                        <span className="hw-history-mode">
                          {MODES.find((m) => m.value === sess.mode)?.label}
                        </span>
                        {sess.is_saved && <span className="hw-history-saved-badge">Saved</span>}
                      </div>
                      <div className="hw-history-question">{truncate(sess.question)}</div>
                      <div className="hw-history-date">
                        {new Date(sess.created_at).toLocaleDateString()}
                        {sess.follow_up_count > 0 && (
                          <span className="hw-history-followups"> · {sess.follow_up_count} follow-up{sess.follow_up_count !== 1 ? 's' : ''}</span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {activeTab === 'saved' && (
            <div className="hw-saved">
              <input
                className="hw-saved-search"
                type="text"
                placeholder="Search saved solutions..."
                value={savedSearch}
                onChange={(e) => setSavedSearch(e.target.value)}
              />

              {filteredSavedSolutions.length === 0 && (
                <div className="hw-sidebar-empty">
                  {savedSearch ? 'No matching solutions.' : 'No saved solutions yet.'}
                </div>
              )}

              <div className="hw-saved-list">
                {filteredSavedSolutions.map((sol) => {
                  const subMeta = SUBJECTS.find((s) => s.value === sol.subject);
                  return (
                    <div key={sol.id} className={`hw-saved-item hw-subject-${subMeta?.color || 'other'}`}>
                      <div className="hw-saved-item-header">
                        <span className="hw-saved-title">{sol.title}</span>
                        <button
                          className="hw-saved-delete"
                          onClick={() => handleDeleteSaved(sol.id)}
                          title="Delete saved solution"
                        >
                          &times;
                        </button>
                      </div>
                      <div className="hw-saved-meta">
                        <span>{subMeta?.icon} {subMeta?.label}</span>
                        <span>{MODES.find((m) => m.value === sol.mode)?.label}</span>
                      </div>
                      {(sol.tags || []).length > 0 && (
                        <div className="hw-saved-tags">
                          {(sol.tags || []).map((tag) => (
                            <span key={tag} className="hw-saved-tag">{tag}</span>
                          ))}
                        </div>
                      )}
                      <div className="hw-saved-question">{truncate(sol.question)}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </aside>
      </div>
    </DashboardLayout>
  );
}

export default HomeworkHelperPage;
