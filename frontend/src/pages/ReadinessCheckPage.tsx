import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/Toast';
import { readinessApi } from '../api/readiness';
import type {
  ReadinessCheckResponse,
  ReadinessReport,
  ReadinessListItem,
} from '../api/readiness';
import { parentApi } from '../api/client';
import type { ChildSummary } from '../api/client';
import './ReadinessCheckPage.css';

// ── Score helpers ──
function scoreLabel(score: number): string {
  if (score >= 5) return 'Excellent';
  if (score >= 4) return 'Good';
  if (score >= 3) return 'Developing';
  if (score >= 2) return 'Below Expectations';
  return 'Significant Gaps';
}

function scoreColor(score: number): string {
  if (score >= 4) return 'var(--color-success, #22c55e)';
  if (score >= 3) return 'var(--color-warning, #f59e0b)';
  return 'var(--color-error, #ef4444)';
}

function statusColor(status: string): string {
  if (status === 'strong') return 'var(--color-success, #22c55e)';
  if (status === 'developing') return 'var(--color-warning, #f59e0b)';
  return 'var(--color-error, #ef4444)';
}

interface CourseOption {
  id: number;
  name: string;
}

type View = 'list' | 'create' | 'quiz' | 'report';

export function ReadinessCheckPage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [searchParams] = useSearchParams();
  const isParent = user?.role === 'parent';

  // State
  const [view, setView] = useState<View>('list');
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<ReadinessListItem[]>([]);

  // Create form
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [courses, setCourses] = useState<CourseOption[]>([]);
  const [selectedChild, setSelectedChild] = useState<number | null>(null);
  const [selectedCourse, setSelectedCourse] = useState<number | null>(null);
  const [topic, setTopic] = useState('');

  // Quiz state
  const [assessment, setAssessment] = useState<ReadinessCheckResponse | null>(null);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [submitting, setSubmitting] = useState(false);

  // Report state
  const [report, setReport] = useState<ReadinessReport | null>(null);

  // ── Load list ──
  const loadList = useCallback(async () => {
    try {
      setLoading(true);
      const data = await readinessApi.list();
      setItems(data);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadList(); }, [loadList]);

  // Handle deep link: ?id=123&view=quiz or &view=report
  useEffect(() => {
    const id = searchParams.get('id');
    const v = searchParams.get('view');
    if (id && v === 'report') {
      readinessApi.getReport(Number(id)).then(r => {
        setReport(r);
        setView('report');
      }).catch(() => toast('Failed to load report', 'error'));
    }
  }, [searchParams, toast]);

  // ── Load children + courses for create form ──
  useEffect(() => {
    if (!isParent) return;
    parentApi.getChildren().then(setChildren).catch(() => {});
  }, [isParent]);

  useEffect(() => {
    if (!selectedChild) { setCourses([]); return; }
    parentApi.getChildOverview(selectedChild).then(ov => {
      setCourses(ov.courses?.map((c: any) => ({ id: c.id, name: c.name })) || []);
    }).catch(() => setCourses([]));
  }, [selectedChild]);

  // ── Create assessment ──
  const handleCreate = async () => {
    if (!selectedChild || !selectedCourse) {
      toast('Select a child and course', 'error');
      return;
    }
    try {
      setLoading(true);
      const res = await readinessApi.create({
        student_id: selectedChild,
        course_id: selectedCourse,
        topic: topic || undefined,
      });
      setAssessment(res);
      setAnswers({});
      setView('quiz');
      toast('Assessment created! Share with your child to complete.', 'success');
      loadList();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Failed to create assessment';
      toast(msg, 'error');
    } finally {
      setLoading(false);
    }
  };

  // ── Submit answers ──
  const handleSubmit = async () => {
    if (!assessment) return;
    const missing = assessment.questions.filter(q => !answers[q.id]?.trim());
    if (missing.length > 0) {
      toast('Please answer all questions', 'error');
      return;
    }
    try {
      setSubmitting(true);
      const answerList = Object.entries(answers).map(([qid, ans]) => ({
        question_id: Number(qid),
        answer: ans,
      }));
      const res = await readinessApi.submit(assessment.id, answerList);
      toast(`Assessment submitted! Score: ${res.overall_score}/5`, 'success');
      // Load report
      const rpt = await readinessApi.getReport(assessment.id);
      setReport(rpt);
      setView('report');
      loadList();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Failed to submit';
      toast(msg, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  // ── View report ──
  const openReport = async (id: number) => {
    try {
      setLoading(true);
      const rpt = await readinessApi.getReport(id);
      setReport(rpt);
      setView('report');
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Report not available yet';
      toast(msg, 'error');
    } finally {
      setLoading(false);
    }
  };

  // ── Open pending quiz (student view) ──
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const openQuiz = async (_item: ReadinessListItem) => {
    // We need to re-fetch the assessment to get questions
    // The list endpoint doesn't have questions, so use the report endpoint which will 400 if not complete
    // Instead, fetch from the study guide directly — but we don't have that API
    // For now, show a message
    toast('Open the link in your notification to take this assessment', 'info');
  };

  // ── Render ──
  return (
    <DashboardLayout>
      <div className="readiness-page">
        <div className="readiness-header">
          <h1>Is My Kid Ready?</h1>
          <p className="readiness-subtitle">
            {isParent
              ? 'Create a quick diagnostic quiz to check your child\'s understanding'
              : 'Complete readiness assessments assigned to you'}
          </p>
          {isParent && view !== 'create' && (
            <button
              className="readiness-btn readiness-btn-primary"
              onClick={() => setView('create')}
            >
              + New Assessment
            </button>
          )}
        </div>

        {/* ── CREATE VIEW ── */}
        {view === 'create' && isParent && (
          <div className="readiness-card readiness-create-form">
            <h2>Create Readiness Check</h2>

            <label className="readiness-label">
              Select Child
              <select
                className="readiness-select"
                value={selectedChild ?? ''}
                onChange={e => setSelectedChild(Number(e.target.value) || null)}
              >
                <option value="">Choose a child...</option>
                {children.map(c => (
                  <option key={c.student_id} value={c.student_id}>
                    {c.full_name}
                  </option>
                ))}
              </select>
            </label>

            <label className="readiness-label">
              Select Course
              <select
                className="readiness-select"
                value={selectedCourse ?? ''}
                onChange={e => setSelectedCourse(Number(e.target.value) || null)}
                disabled={!selectedChild || courses.length === 0}
              >
                <option value="">
                  {!selectedChild ? 'Select a child first' : courses.length === 0 ? 'No courses found' : 'Choose a course...'}
                </option>
                {courses.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </label>

            <label className="readiness-label">
              Topic (optional)
              <input
                className="readiness-input"
                type="text"
                placeholder="e.g. Fractions, Photosynthesis..."
                value={topic}
                onChange={e => setTopic(e.target.value)}
                maxLength={500}
              />
            </label>

            <div className="readiness-form-actions">
              <button
                className="readiness-btn readiness-btn-secondary"
                onClick={() => setView('list')}
              >
                Cancel
              </button>
              <button
                className="readiness-btn readiness-btn-primary"
                onClick={handleCreate}
                disabled={loading || !selectedChild || !selectedCourse}
              >
                {loading ? 'Generating...' : 'Generate 5 Questions'}
              </button>
            </div>
          </div>
        )}

        {/* ── QUIZ VIEW ── */}
        {view === 'quiz' && assessment && (
          <div className="readiness-card readiness-quiz">
            <h2>Readiness Assessment</h2>
            <p className="readiness-quiz-info">
              Answer all 5 questions below. Take your time — this is not timed.
            </p>

            {assessment.questions.map((q, idx) => (
              <div key={q.id} className="readiness-question">
                <div className="readiness-question-header">
                  <span className="readiness-question-number">Q{idx + 1}</span>
                  <span className={`readiness-question-type readiness-type-${q.type}`}>
                    {q.type === 'multiple_choice' ? 'Multiple Choice'
                      : q.type === 'short_answer' ? 'Short Answer'
                      : 'Application'}
                  </span>
                </div>
                <p className="readiness-question-text">{q.question}</p>

                {q.type === 'multiple_choice' && q.options ? (
                  <div className="readiness-options">
                    {q.options.map((opt, i) => (
                      <label key={i} className={`readiness-option ${answers[q.id] === opt ? 'selected' : ''}`}>
                        <input
                          type="radio"
                          name={`q-${q.id}`}
                          value={opt}
                          checked={answers[q.id] === opt}
                          onChange={() => setAnswers(prev => ({ ...prev, [q.id]: opt }))}
                        />
                        <span>{opt}</span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <textarea
                    className="readiness-textarea"
                    placeholder={q.type === 'application'
                      ? 'Describe your approach and reasoning...'
                      : 'Type your answer...'}
                    value={answers[q.id] || ''}
                    onChange={e => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                    rows={q.type === 'application' ? 5 : 3}
                  />
                )}
              </div>
            ))}

            <div className="readiness-form-actions">
              <button
                className="readiness-btn readiness-btn-secondary"
                onClick={() => { setView('list'); setAssessment(null); }}
              >
                Cancel
              </button>
              <button
                className="readiness-btn readiness-btn-primary"
                onClick={handleSubmit}
                disabled={submitting}
              >
                {submitting ? 'Evaluating...' : 'Submit Answers'}
              </button>
            </div>
          </div>
        )}

        {/* ── REPORT VIEW ── */}
        {view === 'report' && report && (
          <div className="readiness-report">
            <button
              className="readiness-btn readiness-btn-secondary readiness-back-btn"
              onClick={() => { setView('list'); setReport(null); }}
            >
              &larr; Back to List
            </button>

            <div className="readiness-card readiness-report-header">
              <div className="readiness-report-score" style={{ borderColor: scoreColor(report.overall_score) }}>
                <span className="readiness-score-number" style={{ color: scoreColor(report.overall_score) }}>
                  {report.overall_score}
                </span>
                <span className="readiness-score-label">/5</span>
              </div>
              <div className="readiness-report-meta">
                <h2>{report.student_name} — {report.course_name}</h2>
                {report.topic && <p className="readiness-report-topic">Topic: {report.topic}</p>}
                <p className="readiness-report-grade">{scoreLabel(report.overall_score)}</p>
              </div>
            </div>

            <div className="readiness-card">
              <h3>Summary</h3>
              <p>{report.summary}</p>
            </div>

            <div className="readiness-card">
              <h3>Topic Breakdown</h3>
              <div className="readiness-breakdown">
                {report.topic_breakdown.map((t, i) => (
                  <div key={i} className="readiness-breakdown-item">
                    <div className="readiness-breakdown-header">
                      <span className="readiness-breakdown-topic">{t.topic}</span>
                      <span
                        className="readiness-breakdown-badge"
                        style={{ backgroundColor: statusColor(t.status) }}
                      >
                        {t.status === 'strong' ? 'Strong' : t.status === 'developing' ? 'Developing' : 'Needs Work'}
                      </span>
                    </div>
                    <div className="readiness-score-bar">
                      <div
                        className="readiness-score-fill"
                        style={{ width: `${(t.score / 5) * 100}%`, backgroundColor: statusColor(t.status) }}
                      />
                    </div>
                    <p className="readiness-breakdown-feedback">{t.feedback}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="readiness-card">
              <h3>Suggestions</h3>
              <ul className="readiness-suggestions">
                {report.suggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>

            {report.questions && report.answers && (
              <div className="readiness-card">
                <h3>Questions & Answers</h3>
                {report.questions.map((q, idx) => {
                  const ans = report.answers?.find(a => a.question_id === q.id);
                  return (
                    <div key={q.id} className="readiness-qa-item">
                      <p className="readiness-qa-question">
                        <strong>Q{idx + 1}:</strong> {q.question}
                      </p>
                      <p className="readiness-qa-answer">
                        <strong>Answer:</strong> {ans?.answer || 'No answer'}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ── LIST VIEW ── */}
        {view === 'list' && (
          <div className="readiness-list">
            {loading && <p className="readiness-loading">Loading...</p>}
            {!loading && items.length === 0 && (
              <div className="readiness-empty">
                <p>No readiness checks yet.</p>
                {isParent && (
                  <button
                    className="readiness-btn readiness-btn-primary"
                    onClick={() => setView('create')}
                  >
                    Create Your First Assessment
                  </button>
                )}
              </div>
            )}
            {items.map(item => (
              <div
                key={item.id}
                className={`readiness-card readiness-list-item ${item.status}`}
                onClick={() => item.status === 'completed' ? openReport(item.id) : openQuiz(item)}
                role="button"
                tabIndex={0}
                onKeyDown={e => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    if (item.status === 'completed') { openReport(item.id); } else { openQuiz(item); }
                  }
                }}
              >
                <div className="readiness-list-item-left">
                  <h3>{item.student_name}</h3>
                  <p>{item.course_name}{item.topic ? ` — ${item.topic}` : ''}</p>
                  <span className="readiness-list-date">
                    {new Date(item.created_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="readiness-list-item-right">
                  {item.status === 'completed' && item.overall_score != null ? (
                    <span
                      className="readiness-list-score"
                      style={{ color: scoreColor(item.overall_score) }}
                    >
                      {item.overall_score}/5
                    </span>
                  ) : (
                    <span className="readiness-list-pending">Pending</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
