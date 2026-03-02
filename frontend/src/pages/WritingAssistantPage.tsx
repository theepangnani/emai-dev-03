import { useState, useEffect, useCallback } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import {
  analyzeWriting,
  improveWriting,
  getSessions,
  getSession,
  getTemplates,
} from '../api/writingAssistance';
import type {
  WritingAnalysisResponse,
  WritingFeedbackItem,
  WritingFeedbackType,
  WritingSessionSummary,
  WritingTemplate,
  AssignmentType,
} from '../api/writingAssistance';
import './WritingAssistantPage.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ASSIGNMENT_TYPES: { value: AssignmentType; label: string }[] = [
  { value: 'essay', label: 'Essay' },
  { value: 'report', label: 'Report' },
  { value: 'letter', label: 'Letter' },
  { value: 'lab', label: 'Lab Report' },
];

const FEEDBACK_TABS: { key: WritingFeedbackType | 'all'; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'grammar', label: 'Grammar' },
  { key: 'clarity', label: 'Clarity' },
  { key: 'structure', label: 'Structure' },
  { key: 'argumentation', label: 'Argumentation' },
];

function scoreColor(score: number): string {
  if (score >= 80) return 'score-green';
  if (score >= 60) return 'score-yellow';
  return 'score-red';
}

function severityIcon(severity: string): string {
  if (severity === 'error') return '✕';
  if (severity === 'warning') return '⚠';
  return 'ℹ';
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// ScoreCircle component
// ---------------------------------------------------------------------------

function ScoreCircle({ score }: { score: number }) {
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;

  return (
    <div className={`score-circle-wrapper ${scoreColor(score)}`}>
      <svg width="110" height="110" viewBox="0 0 110 110">
        <circle cx="55" cy="55" r={radius} className="score-track" />
        <circle
          cx="55"
          cy="55"
          r={radius}
          className="score-fill"
          strokeDasharray={`${progress} ${circumference}`}
          strokeDashoffset="0"
          transform="rotate(-90 55 55)"
        />
      </svg>
      <div className="score-label">
        <span className="score-number">{score}</span>
        <span className="score-out-of">/100</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// FeedbackCard component
// ---------------------------------------------------------------------------

function FeedbackCard({ item }: { item: WritingFeedbackItem }) {
  return (
    <div className={`feedback-card feedback-${item.severity}`}>
      <div className="feedback-header">
        <span className={`severity-icon severity-${item.severity}`}>
          {severityIcon(item.severity)}
        </span>
        <span className="feedback-type-badge">{item.type}</span>
      </div>
      <p className="feedback-message">{item.message}</p>
      <p className="feedback-suggestion">
        <strong>Suggestion:</strong> {item.suggestion}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export function WritingAssistantPage() {
  // Left panel state
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [assignmentType, setAssignmentType] = useState<AssignmentType>('essay');
  const [templates, setTemplates] = useState<WritingTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');

  // Right panel / results state
  const [analysisResult, setAnalysisResult] = useState<WritingAnalysisResponse | null>(null);
  const [activeTab, setActiveTab] = useState<WritingFeedbackType | 'all'>('all');
  const [showImproved, setShowImproved] = useState(false);
  const [improveInstruction, setImproveInstruction] = useState('');
  const [furtherImproved, setFurtherImproved] = useState<string | null>(null);

  // Session history
  const [sessions, setSessions] = useState<WritingSessionSummary[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  // Loading / error state
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isImproving, setIsImproving] = useState(false);
  const [isFurtherImproving, setIsFurtherImproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;

  // Load templates and session history on mount
  useEffect(() => {
    getTemplates().then(setTemplates).catch(() => {});
    getSessions().then(setSessions).catch(() => {});
  }, []);

  const handleTemplateSelect = useCallback(
    (templateId: string) => {
      setSelectedTemplate(templateId);
      if (!templateId) return;
      const tmpl = templates.find((t) => String(t.id) === templateId);
      if (tmpl) {
        setText(tmpl.structure_outline);
        setAssignmentType(tmpl.template_type as AssignmentType);
      }
    },
    [templates],
  );

  const handleAnalyze = useCallback(async () => {
    if (!text.trim()) {
      setError('Please enter some text before analyzing.');
      return;
    }
    if (!title.trim()) {
      setError('Please enter a title for your writing.');
      return;
    }

    setError(null);
    setIsAnalyzing(true);
    setAnalysisResult(null);
    setShowImproved(false);
    setFurtherImproved(null);

    try {
      const result = await analyzeWriting({
        title: title.trim(),
        text: text.trim(),
        assignment_type: assignmentType,
      });
      setAnalysisResult(result);
      setActiveTab('all');
      // Refresh session list
      getSessions().then(setSessions).catch(() => {});
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Failed to analyze writing. Please try again.';
      setError(msg);
    } finally {
      setIsAnalyzing(false);
    }
  }, [text, title, assignmentType]);

  const handleApplyImproved = useCallback(() => {
    if (analysisResult?.improved_text) {
      setText(analysisResult.improved_text);
      setShowImproved(false);
    }
  }, [analysisResult]);

  const handleFurtherImprove = useCallback(async () => {
    if (!analysisResult || !improveInstruction.trim()) return;

    setIsFurtherImproving(true);
    setFurtherImproved(null);

    try {
      const result = await improveWriting({
        session_id: analysisResult.session_id,
        instruction: improveInstruction.trim(),
      });
      setFurtherImproved(result.improved_text);
    } catch {
      setError('Failed to apply improvement. Please try again.');
    } finally {
      setIsFurtherImproving(false);
    }
  }, [analysisResult, improveInstruction]);

  const handleApplyFurtherImproved = useCallback(() => {
    if (furtherImproved) {
      setText(furtherImproved);
      setFurtherImproved(null);
      setImproveInstruction('');
    }
  }, [furtherImproved]);

  const handleLoadSession = useCallback(async (sessionId: number) => {
    try {
      const detail = await getSession(sessionId);
      setTitle(detail.title);
      setText(detail.original_text);
      setAssignmentType(detail.assignment_type as AssignmentType);
      // Re-synthesize an analysis result from session detail
      setAnalysisResult({
        session_id: detail.id,
        overall_score: detail.overall_score ?? 0,
        feedback: detail.feedback ?? [],
        improved_text: detail.improved_text ?? '',
        suggestions_count: detail.feedback?.length ?? 0,
        word_count: detail.word_count,
      });
      setShowHistory(false);
      setActiveTab('all');
      setShowImproved(false);
      setFurtherImproved(null);
    } catch {
      setError('Failed to load session.');
    }
  }, []);

  // Filtered feedback based on active tab
  const filteredFeedback: WritingFeedbackItem[] =
    analysisResult?.feedback?.filter(
      (f) => activeTab === 'all' || f.type === activeTab,
    ) ?? [];

  return (
    <DashboardLayout welcomeSubtitle="AI Writing Assistant">
      <div className="writing-assistant-page">
        <div className="writing-assistant-header">
          <h1 className="writing-assistant-title">AI Writing Assistant</h1>
          <button
            className="history-toggle-btn"
            onClick={() => setShowHistory((v) => !v)}
          >
            {showHistory ? 'Hide History' : 'Session History'} ({sessions.length})
          </button>
        </div>

        {/* Session history sidebar */}
        {showHistory && sessions.length > 0 && (
          <div className="session-history-list">
            <h3>Past Sessions</h3>
            {sessions.map((s) => (
              <button
                key={s.id}
                className="session-history-item"
                onClick={() => handleLoadSession(s.id)}
              >
                <span className="sh-title">{s.title}</span>
                <span className="sh-meta">
                  {s.assignment_type} &bull; {formatDate(s.created_at)}
                  {s.overall_score != null && (
                    <span className={`sh-score ${scoreColor(s.overall_score)}`}>
                      {' '}
                      &bull; Score: {s.overall_score}
                    </span>
                  )}
                </span>
              </button>
            ))}
          </div>
        )}

        {error && (
          <div className="writing-error-banner">
            <span>{error}</span>
            <button onClick={() => setError(null)}>&times;</button>
          </div>
        )}

        <div className={`writing-split-panel${analysisResult ? ' has-results' : ''}`}>
          {/* ----------------------------------------------------------------
              Left panel — input
          ---------------------------------------------------------------- */}
          <div className="writing-left-panel">
            <div className="writing-form">
              <div className="writing-form-row">
                <label className="writing-label" htmlFor="writing-title">
                  Title
                </label>
                <input
                  id="writing-title"
                  type="text"
                  className="writing-input"
                  placeholder="e.g. The Causes of World War I"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>

              <div className="writing-form-row writing-form-row--inline">
                <div className="writing-form-field">
                  <label className="writing-label" htmlFor="assignment-type">
                    Type
                  </label>
                  <select
                    id="assignment-type"
                    className="writing-select"
                    value={assignmentType}
                    onChange={(e) => setAssignmentType(e.target.value as AssignmentType)}
                  >
                    {ASSIGNMENT_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </div>

                {templates.length > 0 && (
                  <div className="writing-form-field">
                    <label className="writing-label" htmlFor="template-select">
                      Start from Template
                    </label>
                    <select
                      id="template-select"
                      className="writing-select"
                      value={selectedTemplate}
                      onChange={(e) => handleTemplateSelect(e.target.value)}
                    >
                      <option value="">-- Choose a template --</option>
                      {templates.map((t) => (
                        <option key={t.id} value={String(t.id)}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              <div className="writing-form-row">
                <div className="writing-textarea-header">
                  <label className="writing-label" htmlFor="writing-text">
                    Your Text
                  </label>
                  <span className="word-count">{wordCount} words</span>
                </div>
                <textarea
                  id="writing-text"
                  className="writing-textarea"
                  placeholder="Paste or type your essay / assignment here..."
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  rows={20}
                />
              </div>

              <button
                className="analyze-btn"
                onClick={handleAnalyze}
                disabled={isAnalyzing}
              >
                {isAnalyzing ? (
                  <>
                    <span className="btn-spinner" /> Analyzing...
                  </>
                ) : (
                  'Analyze Writing'
                )}
              </button>
            </div>
          </div>

          {/* ----------------------------------------------------------------
              Right panel — results
          ---------------------------------------------------------------- */}
          {analysisResult && (
            <div className="writing-right-panel">
              {/* Score */}
              <div className="score-section">
                <ScoreCircle score={analysisResult.overall_score} />
                <div className="score-details">
                  <h3 className="score-heading">Overall Score</h3>
                  <p className="score-sub">
                    {analysisResult.suggestions_count} suggestion
                    {analysisResult.suggestions_count !== 1 ? 's' : ''} &bull;{' '}
                    {analysisResult.word_count} words
                  </p>
                </div>
              </div>

              {/* Feedback tabs */}
              <div className="feedback-tabs">
                {FEEDBACK_TABS.map((tab) => (
                  <button
                    key={tab.key}
                    className={`feedback-tab${activeTab === tab.key ? ' active' : ''}`}
                    onClick={() => setActiveTab(tab.key)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Feedback cards */}
              <div className="feedback-list">
                {filteredFeedback.length === 0 ? (
                  <p className="no-feedback">No feedback in this category.</p>
                ) : (
                  filteredFeedback.map((item, idx) => (
                    <FeedbackCard key={idx} item={item} />
                  ))
                )}
              </div>

              {/* Improved version */}
              {analysisResult.improved_text && (
                <div className="improved-section">
                  <button
                    className="improved-toggle-btn"
                    onClick={() => setShowImproved((v) => !v)}
                  >
                    {showImproved ? 'Hide' : 'Show'} Improved Version
                  </button>

                  {showImproved && (
                    <div className="improved-content">
                      <pre className="improved-text">{analysisResult.improved_text}</pre>
                      <button className="apply-btn" onClick={handleApplyImproved}>
                        Apply to Editor
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Further improve */}
              <div className="further-improve-section">
                <h4 className="further-improve-heading">Further Improve</h4>
                <p className="further-improve-hint">
                  Give an instruction like "make it more formal" or "strengthen the conclusion".
                </p>
                <div className="further-improve-row">
                  <input
                    type="text"
                    className="further-improve-input"
                    placeholder="e.g. make it more formal"
                    value={improveInstruction}
                    onChange={(e) => setImproveInstruction(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleFurtherImprove();
                    }}
                  />
                  <button
                    className="further-improve-btn"
                    onClick={handleFurtherImprove}
                    disabled={isFurtherImproving || !improveInstruction.trim()}
                  >
                    {isFurtherImproving ? (
                      <>
                        <span className="btn-spinner" /> Working...
                      </>
                    ) : (
                      'Improve'
                    )}
                  </button>
                </div>

                {furtherImproved && (
                  <div className="further-improved-result">
                    <pre className="improved-text">{furtherImproved}</pre>
                    <button className="apply-btn" onClick={handleApplyFurtherImproved}>
                      Apply to Editor
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
