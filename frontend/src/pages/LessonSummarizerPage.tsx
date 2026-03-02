import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import {
  generateSummary,
  listSummaries,
  getSummary,
  deleteSummary,
  convertToFlashcards,
  type InputType,
  type LessonSummaryListItem,
  type LessonSummaryResponse,
  type KeyConcept,
  type ImportantDate,
} from '../api/lessonSummary';
import './LessonSummarizerPage.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function wordCount(text: string) {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function KeyConceptCard({ concept }: { concept: KeyConcept }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="ls-concept-card" onClick={() => setExpanded(p => !p)} role="button" tabIndex={0} onKeyDown={e => e.key === 'Enter' && setExpanded(p => !p)}>
      <div className="ls-concept-header">
        <span className="ls-concept-term">{concept.concept}</span>
        <span className="ls-concept-toggle">{expanded ? '▲' : '▼'}</span>
      </div>
      {expanded && <p className="ls-concept-definition">{concept.definition}</p>}
    </div>
  );
}

function StudyQuestion({ index, question }: { index: number; question: string }) {
  const [revealed, setRevealed] = useState(false);
  return (
    <div className="ls-question-item">
      <div className="ls-question-row" onClick={() => setRevealed(p => !p)} role="button" tabIndex={0} onKeyDown={e => e.key === 'Enter' && setRevealed(p => !p)}>
        <span className="ls-question-num">{index + 1}.</span>
        <span className="ls-question-text">{question}</span>
        <span className="ls-question-hint">{revealed ? 'Hide hint' : 'Hint'}</span>
      </div>
      {revealed && (
        <p className="ls-question-hint-text">
          Review your notes section on this topic for the answer.
        </p>
      )}
    </div>
  );
}

function ActionItemList({ items }: { items: string[] }) {
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const toggle = (i: number) => setChecked(prev => {
    const next = new Set(prev);
    next.has(i) ? next.delete(i) : next.add(i);
    return next;
  });
  return (
    <ul className="ls-action-list">
      {items.map((item, i) => (
        <li key={i} className={`ls-action-item${checked.has(i) ? ' done' : ''}`}>
          <input
            type="checkbox"
            id={`action-${i}`}
            checked={checked.has(i)}
            onChange={() => toggle(i)}
            className="ls-action-checkbox"
          />
          <label htmlFor={`action-${i}`} className="ls-action-label">{item}</label>
        </li>
      ))}
    </ul>
  );
}

function DateTimeline({ dates }: { dates: ImportantDate[] }) {
  return (
    <ul className="ls-date-timeline">
      {dates.map((d, i) => (
        <li key={i} className="ls-date-item">
          <span className="ls-date-badge">{d.date}</span>
          <span className="ls-date-event">{d.event}</span>
        </li>
      ))}
    </ul>
  );
}

function HistorySidebar({
  items,
  activeId,
  onSelect,
  onDelete,
  loading,
}: {
  items: LessonSummaryListItem[];
  activeId: number | null;
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
  loading: boolean;
}) {
  return (
    <aside className="ls-history-sidebar">
      <h3 className="ls-history-title">Recent Summaries</h3>
      {loading && <p className="ls-history-loading">Loading...</p>}
      {!loading && items.length === 0 && (
        <p className="ls-history-empty">No summaries yet. Create your first one!</p>
      )}
      {items.map(item => (
        <div
          key={item.id}
          className={`ls-history-item${activeId === item.id ? ' active' : ''}`}
          onClick={() => onSelect(item.id)}
          role="button"
          tabIndex={0}
          onKeyDown={e => e.key === 'Enter' && onSelect(item.id)}
        >
          <div className="ls-history-item-title">{item.title}</div>
          <div className="ls-history-item-meta">
            <span>{formatDate(item.created_at)}</span>
            <span>{item.word_count} words</span>
          </div>
          {item.course_name && (
            <div className="ls-history-item-course">{item.course_name}</div>
          )}
          <button
            className="ls-history-delete"
            onClick={e => { e.stopPropagation(); onDelete(item.id); }}
            aria-label="Delete summary"
            title="Delete"
          >
            &times;
          </button>
        </div>
      ))}
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function LessonSummarizerPage() {
  const navigate = useNavigate();

  // --- Input state ---
  const [title, setTitle] = useState('');
  const [rawInput, setRawInput] = useState('');
  const [inputType, setInputType] = useState<InputType>('text');
  const [courseId] = useState<number | undefined>(undefined);

  // --- Result state ---
  const [result, setResult] = useState<LessonSummaryResponse | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);

  // --- History state ---
  const [history, setHistory] = useState<LessonSummaryListItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [activeId, setActiveId] = useState<number | null>(null);

  // --- Flashcard conversion ---
  const [flashcardLoading, setFlashcardLoading] = useState(false);
  const [flashcardMsg, setFlashcardMsg] = useState<string | null>(null);

  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load history on mount
  useState(() => {
    setHistoryLoading(true);
    listSummaries()
      .then(setHistory)
      .catch(console.error)
      .finally(() => setHistoryLoading(false));
  });

  const handleGenerate = async () => {
    if (!title.trim()) {
      setGenError('Please enter a title for your notes.');
      return;
    }
    if (!rawInput.trim() || rawInput.trim().split(/\s+/).length < 5) {
      setGenError('Please paste at least a few words of class notes.');
      return;
    }
    setGenError(null);
    setGenerating(true);
    setFlashcardMsg(null);
    try {
      const response = await generateSummary({ title, raw_input: rawInput, input_type: inputType, course_id: courseId });
      setResult(response);
      setActiveId(response.id);
      // Refresh history
      const updated = await listSummaries();
      setHistory(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Generation failed. Please try again.';
      setGenError(msg);
    } finally {
      setGenerating(false);
    }
  };

  const handleSelectHistory = async (id: number) => {
    setActiveId(id);
    setFlashcardMsg(null);
    try {
      const full = await getSummary(id);
      setResult(full);
      setTitle(full.title);
      setRawInput(full.raw_input);
      setInputType(full.input_type);
    } catch {
      // silently ignore
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Delete this summary?')) return;
    try {
      await deleteSummary(id);
      setHistory(prev => prev.filter(h => h.id !== id));
      if (activeId === id) {
        setResult(null);
        setActiveId(null);
      }
    } catch {
      // silently ignore
    }
  };

  const handleConvertFlashcards = async () => {
    if (!result) return;
    setFlashcardLoading(true);
    setFlashcardMsg(null);
    try {
      const res = await convertToFlashcards(result.id);
      setFlashcardMsg(`Created ${res.card_count} flashcards! Opening study guide...`);
      setTimeout(() => navigate(`/study/flashcards/${res.study_guide_id}`), 1500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create flashcards.';
      setFlashcardMsg(msg);
    } finally {
      setFlashcardLoading(false);
    }
  };

  const wc = wordCount(rawInput);

  return (
    <DashboardLayout welcomeSubtitle="Turn your class notes into structured study materials">
      <div className="ls-root">
        <HistorySidebar
          items={history}
          activeId={activeId}
          onSelect={handleSelectHistory}
          onDelete={handleDelete}
          loading={historyLoading}
        />

        <div className="ls-main">
          {/* LEFT PANEL — Input */}
          <section className="ls-input-panel">
            <h2 className="ls-panel-title">Lesson Summarizer</h2>
            <p className="ls-panel-subtitle">
              Paste your class notes or lecture transcript and get an AI-structured summary with key concepts, study questions, and action items.
            </p>

            <div className="ls-form-row">
              <label className="ls-label" htmlFor="ls-title">Summary Title</label>
              <input
                id="ls-title"
                className="ls-input"
                type="text"
                placeholder="e.g. Chapter 5 — Cell Division"
                value={title}
                onChange={e => setTitle(e.target.value)}
              />
            </div>

            <div className="ls-form-row">
              <label className="ls-label">Input Type</label>
              <div className="ls-tabs">
                {(
                  [
                    { value: 'text', label: 'Type / Paste Notes' },
                    { value: 'transcript', label: 'Lecture Transcript' },
                    { value: 'audio_transcript', label: 'Audio Transcript' },
                    { value: 'uploaded_notes', label: 'Uploaded Notes' },
                  ] as const
                ).map(tab => (
                  <button
                    key={tab.value}
                    className={`ls-tab${inputType === tab.value ? ' active' : ''}`}
                    onClick={() => setInputType(tab.value)}
                    type="button"
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="ls-form-row ls-notes-row">
              <label className="ls-label" htmlFor="ls-notes">
                {inputType === 'text' ? 'Class Notes' : inputType === 'transcript' ? 'Lecture Transcript' : inputType === 'audio_transcript' ? 'Audio Transcript' : 'Uploaded Notes'}
                <span className="ls-word-count">{wc} words</span>
              </label>
              <textarea
                id="ls-notes"
                ref={inputRef}
                className="ls-textarea"
                placeholder={
                  inputType === 'text'
                    ? 'Paste or type your class notes here...'
                    : 'Paste your transcript here...'
                }
                value={rawInput}
                onChange={e => setRawInput(e.target.value)}
                rows={16}
              />
            </div>

            {genError && <p className="ls-error">{genError}</p>}

            <button
              className="ls-summarize-btn"
              onClick={handleGenerate}
              disabled={generating}
            >
              {generating ? 'Generating...' : 'Summarize'}
            </button>
          </section>

          {/* RIGHT PANEL — Results */}
          {result && (
            <section className="ls-result-panel">
              <div className="ls-result-header">
                <h2 className="ls-result-title">{result.title}</h2>
                {result.course_name && (
                  <span className="ls-result-course">{result.course_name}</span>
                )}
              </div>

              {/* Summary */}
              {result.summary && (
                <div className="ls-section ls-summary-card">
                  <h3 className="ls-section-title">Summary</h3>
                  <p className="ls-summary-text">{result.summary}</p>
                </div>
              )}

              {/* Key Concepts */}
              {result.key_concepts && result.key_concepts.length > 0 && (
                <div className="ls-section">
                  <h3 className="ls-section-title">Key Concepts ({result.key_concepts.length})</h3>
                  <p className="ls-section-hint">Click a concept to expand its definition.</p>
                  <div className="ls-concepts-grid">
                    {result.key_concepts.map((c, i) => (
                      <KeyConceptCard key={i} concept={c} />
                    ))}
                  </div>
                </div>
              )}

              {/* Study Questions */}
              {result.study_questions && result.study_questions.length > 0 && (
                <div className="ls-section">
                  <h3 className="ls-section-title">Study Questions</h3>
                  <p className="ls-section-hint">Test your understanding. Click for a hint.</p>
                  <div className="ls-questions-list">
                    {result.study_questions.map((q, i) => (
                      <StudyQuestion key={i} index={i} question={q} />
                    ))}
                  </div>
                </div>
              )}

              {/* Action Items */}
              {result.action_items && result.action_items.length > 0 && (
                <div className="ls-section">
                  <h3 className="ls-section-title">Action Items</h3>
                  <ActionItemList items={result.action_items} />
                </div>
              )}

              {/* Important Dates */}
              {result.important_dates && result.important_dates.length > 0 && (
                <div className="ls-section">
                  <h3 className="ls-section-title">Important Dates</h3>
                  <DateTimeline dates={result.important_dates} />
                </div>
              )}

              {/* Convert to Flashcards */}
              <div className="ls-section ls-flashcard-section">
                <button
                  className="ls-flashcard-btn"
                  onClick={handleConvertFlashcards}
                  disabled={flashcardLoading}
                >
                  {flashcardLoading ? 'Creating flashcards...' : 'Convert to Flashcards'}
                </button>
                {flashcardMsg && (
                  <p className="ls-flashcard-msg">{flashcardMsg}</p>
                )}
              </div>
            </section>
          )}

          {!result && !generating && (
            <section className="ls-empty-panel">
              <div className="ls-empty-icon" aria-hidden="true">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
              </div>
              <p className="ls-empty-text">Paste your class notes on the left and click <strong>Summarize</strong> to get started.</p>
            </section>
          )}

          {generating && (
            <section className="ls-empty-panel">
              <div className="ls-generating-spinner" aria-label="Generating..."></div>
              <p className="ls-generating-text">Analyzing your notes with AI...</p>
            </section>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}

export default LessonSummarizerPage;
