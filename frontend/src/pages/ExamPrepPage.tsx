import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { useAuth } from '../context/AuthContext';
import { coursesApi } from '../api/client';
import { examPrepApi } from '../api/examPrep';
import type { ExamPrepPlan, WeakArea, StudyDay, PrepResource } from '../api/examPrep';
import './ExamPrepPage.css';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
}

function confidenceColor(pct: number): string {
  if (pct >= 75) return 'green';
  if (pct >= 50) return 'amber';
  return 'red';
}

function sourceLabel(source: string): string {
  switch (source) {
    case 'quiz': return 'Quiz';
    case 'test': return 'Test';
    case 'teacher_grade': return 'Teacher Grade';
    default: return source;
  }
}

function resourceTypeIcon(type: string): string {
  switch (type) {
    case 'practice': return '✏️';
    case 'memorize': return '🧠';
    default: return '📖';  // review
  }
}

// ─── Detail Modal ─────────────────────────────────────────────────────────────

interface PlanDetailModalProps {
  plan: ExamPrepPlan;
  onClose: () => void;
  onArchive: (id: number) => void;
}

function PlanDetailModal({ plan, onClose, onArchive }: PlanDetailModalProps) {
  const navigate = useNavigate();
  const [openDays, setOpenDays] = useState<Set<number>>(new Set([0]));
  const [checkedTasks, setCheckedTasks] = useState<Set<string>>(new Set());
  const [archiving, setArchiving] = useState(false);

  const weakAreas: WeakArea[] = plan.weak_areas ?? [];
  const schedule: StudyDay[] = plan.study_schedule ?? [];
  const resources: PrepResource[] = plan.recommended_resources ?? [];

  const toggleDay = (idx: number) => {
    setOpenDays(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const toggleTask = (key: string) => {
    setCheckedTasks(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const handleArchive = async () => {
    if (!confirm('Archive this exam prep plan?')) return;
    setArchiving(true);
    try {
      await examPrepApi.archive(plan.id);
      onArchive(plan.id);
      onClose();
    } catch {
      setArchiving(false);
    }
  };

  return (
    <div className="ep-modal-overlay" onClick={onClose}>
      <div className="ep-modal" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={plan.title}>
        {/* Header */}
        <div className="ep-modal-header">
          <div className="ep-modal-title-group">
            <h2 className="ep-modal-title">{plan.title}</h2>
            <div className="ep-modal-meta">
              {plan.course_name && <span className="ep-modal-tag">{plan.course_name}</span>}
              {plan.exam_date && (
                <span className="ep-modal-tag ep-modal-tag--exam">
                  Exam: {formatDate(plan.exam_date)}
                </span>
              )}
              <span className="ep-modal-tag ep-modal-tag--date">
                Generated {formatDate(plan.generated_at)}
              </span>
            </div>
          </div>
          <div className="ep-modal-actions">
            <button
              className="ep-modal-archive-btn"
              onClick={handleArchive}
              disabled={archiving}
              title="Archive plan"
            >
              {archiving ? 'Archiving...' : 'Archive'}
            </button>
            <button className="ep-modal-close" onClick={onClose} aria-label="Close">
              &times;
            </button>
          </div>
        </div>

        <div className="ep-modal-body">
          {/* ── Weak Areas ───────────────────────── */}
          {weakAreas.length > 0 && (
            <section className="ep-section">
              <h3 className="ep-section-title">
                <span className="ep-section-icon" aria-hidden="true">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                </span>
                Weak Areas to Focus On
              </h3>
              <div className="ep-weak-areas">
                {weakAreas.map((area, i) => (
                  <div key={i} className="ep-weak-area-row">
                    <div className="ep-weak-area-label">
                      <span className="ep-weak-topic">{area.topic}</span>
                      <span className={`ep-weak-source ep-weak-source--${area.source}`}>
                        {sourceLabel(area.source)}
                      </span>
                    </div>
                    <div className="ep-weak-bar-wrap">
                      <div
                        className={`ep-weak-bar ep-weak-bar--${confidenceColor(area.confidence_pct)}`}
                        style={{ width: `${area.confidence_pct}%` }}
                        role="progressbar"
                        aria-valuenow={area.confidence_pct}
                        aria-valuemin={0}
                        aria-valuemax={100}
                      />
                    </div>
                    <span className="ep-weak-pct">{area.confidence_pct}%</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* ── Study Schedule ────────────────────── */}
          {schedule.length > 0 && (
            <section className="ep-section">
              <h3 className="ep-section-title">
                <span className="ep-section-icon" aria-hidden="true">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                    <line x1="16" y1="2" x2="16" y2="6"/>
                    <line x1="8" y1="2" x2="8" y2="6"/>
                    <line x1="3" y1="10" x2="21" y2="10"/>
                  </svg>
                </span>
                {schedule.length}-Day Study Schedule
              </h3>
              <div className="ep-schedule">
                {schedule.map((day, idx) => (
                  <div key={idx} className={`ep-day${openDays.has(idx) ? ' ep-day--open' : ''}`}>
                    <button
                      className="ep-day-header"
                      onClick={() => toggleDay(idx)}
                      aria-expanded={openDays.has(idx)}
                    >
                      <span className="ep-day-label">{day.day}</span>
                      <span className="ep-day-tasks-count">{day.tasks.length} tasks</span>
                      <span className="ep-day-chevron" aria-hidden="true">
                        {openDays.has(idx) ? '▲' : '▼'}
                      </span>
                    </button>
                    {openDays.has(idx) && (
                      <ul className="ep-day-tasks">
                        {day.tasks.map((task, ti) => {
                          const key = `${idx}-${ti}`;
                          return (
                            <li key={ti} className="ep-task-item">
                              <label className="ep-task-label">
                                <input
                                  type="checkbox"
                                  checked={checkedTasks.has(key)}
                                  onChange={() => toggleTask(key)}
                                  className="ep-task-checkbox"
                                />
                                <span className={checkedTasks.has(key) ? 'ep-task-text ep-task-text--done' : 'ep-task-text'}>
                                  {task}
                                </span>
                              </label>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* ── Recommended Resources ─────────────── */}
          {resources.length > 0 && (
            <section className="ep-section">
              <h3 className="ep-section-title">
                <span className="ep-section-icon" aria-hidden="true">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                  </svg>
                </span>
                Recommended Resources
              </h3>
              <ul className="ep-resources">
                {resources.map((res, i) => (
                  <li key={i} className="ep-resource-item">
                    <span className="ep-resource-icon" aria-hidden="true">
                      {resourceTypeIcon(res.type)}
                    </span>
                    <div className="ep-resource-info">
                      <span className="ep-resource-title">{res.title}</span>
                      <span className={`ep-resource-type ep-resource-type--${res.type}`}>
                        {res.type.charAt(0).toUpperCase() + res.type.slice(1)}
                      </span>
                    </div>
                    {res.study_guide_id && (
                      <button
                        className="ep-resource-open"
                        onClick={() => navigate(`/study/guide/${res.study_guide_id}`)}
                      >
                        Open
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* ── AI Advice ─────────────────────────── */}
          {plan.ai_advice && (
            <section className="ep-section">
              <h3 className="ep-section-title">
                <span className="ep-section-icon" aria-hidden="true">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                  </svg>
                </span>
                AI Coach Advice
              </h3>
              <div
                className="ep-advice"
                dangerouslySetInnerHTML={{ __html: markdownToHtml(plan.ai_advice) }}
              />
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

// Minimal markdown renderer for the AI advice text
function markdownToHtml(md: string): string {
  return md
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    // Bold
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    // Headers
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>')
    // Unordered list items
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    // Paragraphs (double newline)
    .replace(/\n\n/g, '</p><p>')
    // Wrap in p tags if not already
    .replace(/^(?!<[h|l|p])(.+)$/gm, '<p>$1</p>')
    .replace(/<\/p><p>/g, '</p><p>');
}

// ─── Plan Card ────────────────────────────────────────────────────────────────

interface PlanCardProps {
  plan: ExamPrepPlan;
  onClick: () => void;
}

function PlanCard({ plan, onClick }: PlanCardProps) {
  const weakCount = plan.weak_areas?.length ?? 0;
  const dayCount = plan.study_schedule?.length ?? 0;

  return (
    <button className="ep-plan-card" onClick={onClick}>
      <div className="ep-plan-card-header">
        <h3 className="ep-plan-card-title">{plan.title}</h3>
        {plan.exam_date && (
          <span className="ep-plan-card-exam-badge">
            Exam: {formatDate(plan.exam_date)}
          </span>
        )}
      </div>
      {plan.course_name && (
        <p className="ep-plan-card-course">{plan.course_name}</p>
      )}
      <div className="ep-plan-card-stats">
        {weakCount > 0 && (
          <span className="ep-plan-card-stat">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            {weakCount} weak area{weakCount !== 1 ? 's' : ''}
          </span>
        )}
        {dayCount > 0 && (
          <span className="ep-plan-card-stat">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
              <line x1="16" y1="2" x2="16" y2="6"/>
              <line x1="8" y1="2" x2="8" y2="6"/>
              <line x1="3" y1="10" x2="21" y2="10"/>
            </svg>
            {dayCount}-day plan
          </span>
        )}
      </div>
      <p className="ep-plan-card-date">Generated {formatDate(plan.generated_at)}</p>
    </button>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

interface CourseOption {
  id: number;
  name: string;
}

export function ExamPrepPage() {
  const { user } = useAuth();

  const [courses, setCourses] = useState<CourseOption[]>([]);
  const [plans, setPlans] = useState<ExamPrepPlan[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<ExamPrepPlan | null>(null);
  const [loading, setLoading] = useState(true);

  // Generate form state
  const [title, setTitle] = useState('');
  const [courseId, setCourseId] = useState('');
  const [examDate, setExamDate] = useState('');
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  // Load initial data
  useEffect(() => {
    const load = async () => {
      try {
        const [courseData, planData] = await Promise.all([
          coursesApi.list().catch(() => []),
          examPrepApi.list().catch(() => []),
        ]);
        setCourses(courseData);
        setPlans(planData);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    setGenerating(true);
    setGenerateError(null);
    try {
      const plan = await examPrepApi.generate({
        title: title.trim(),
        course_id: courseId ? Number(courseId) : undefined,
        exam_date: examDate || undefined,
      });
      setPlans(prev => [plan, ...prev]);
      setTitle('');
      setCourseId('');
      setExamDate('');
      setSelectedPlan(plan);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Failed to generate plan. Please try again.';
      setGenerateError(msg);
    } finally {
      setGenerating(false);
    }
  };

  const handleArchive = (id: number) => {
    setPlans(prev => prev.filter(p => p.id !== id));
  };

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Exam Preparation">
        <div className="ep-loading">Loading your exam prep plans...</div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout welcomeSubtitle="Exam Preparation">
      <div className="ep-page">
        {/* ── Page Header ─────────────────────── */}
        <div className="ep-page-header">
          <div className="ep-page-header-icon" aria-hidden="true">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
              <rect x="9" y="3" width="6" height="4" rx="1"/>
              <line x1="9" y1="12" x2="15" y2="12"/>
              <line x1="9" y1="16" x2="12" y2="16"/>
            </svg>
          </div>
          <div>
            <h1 className="ep-page-title">Exam Preparation</h1>
            <p className="ep-page-subtitle">
              AI-powered personalized study plans based on your quiz history, test scores, and report cards.
            </p>
          </div>
        </div>

        {/* ── Generate Plan Section ────────────── */}
        <section className="ep-generate-section">
          <h2 className="ep-generate-title">Generate My Prep Plan</h2>
          <form className="ep-generate-form" onSubmit={handleGenerate}>
            <div className="ep-form-row">
              <div className="ep-form-group ep-form-group--title">
                <label htmlFor="ep-title" className="ep-form-label">
                  Plan Title <span className="ep-required" aria-hidden="true">*</span>
                </label>
                <input
                  id="ep-title"
                  type="text"
                  className="ep-form-input"
                  placeholder="e.g. Grade 12 Math Final Exam"
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  required
                  disabled={generating}
                  maxLength={300}
                />
              </div>

              <div className="ep-form-group">
                <label htmlFor="ep-course" className="ep-form-label">
                  Course (optional)
                </label>
                <select
                  id="ep-course"
                  className="ep-form-select"
                  value={courseId}
                  onChange={e => setCourseId(e.target.value)}
                  disabled={generating}
                >
                  <option value="">All courses / General</option>
                  {courses.map(c => (
                    <option key={c.id} value={String(c.id)}>{c.name}</option>
                  ))}
                </select>
              </div>

              <div className="ep-form-group">
                <label htmlFor="ep-exam-date" className="ep-form-label">
                  Exam Date (optional)
                </label>
                <input
                  id="ep-exam-date"
                  type="date"
                  className="ep-form-input"
                  value={examDate}
                  onChange={e => setExamDate(e.target.value)}
                  disabled={generating}
                />
              </div>
            </div>

            {generateError && (
              <div className="ep-generate-error" role="alert">
                {generateError}
              </div>
            )}

            <button
              type="submit"
              className="ep-generate-btn"
              disabled={generating || !title.trim()}
            >
              {generating ? (
                <>
                  <span className="ep-spinner" aria-hidden="true" />
                  AI is analyzing your performance...
                </>
              ) : (
                <>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
                  </svg>
                  Generate My Prep Plan
                </>
              )}
            </button>
          </form>
        </section>

        {/* ── Existing Plans Grid ──────────────── */}
        {plans.length > 0 && (
          <section className="ep-plans-section">
            <h2 className="ep-plans-title">Your Prep Plans</h2>
            <div className="ep-plans-grid">
              {plans.map(plan => (
                <PlanCard
                  key={plan.id}
                  plan={plan}
                  onClick={() => setSelectedPlan(plan)}
                />
              ))}
            </div>
          </section>
        )}

        {plans.length === 0 && !generating && (
          <div className="ep-empty-state">
            <div className="ep-empty-icon" aria-hidden="true">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
                <rect x="9" y="3" width="6" height="4" rx="1"/>
                <line x1="9" y1="12" x2="15" y2="12"/>
                <line x1="9" y1="16" x2="12" y2="16"/>
              </svg>
            </div>
            <h3 className="ep-empty-title">No prep plans yet</h3>
            <p className="ep-empty-text">
              Generate your first personalized exam prep plan above. The AI will analyze your quiz history,
              report card marks, and teacher grades to create a targeted study schedule.
            </p>
          </div>
        )}
      </div>

      {/* Plan Detail Modal */}
      {selectedPlan && (
        <PlanDetailModal
          plan={selectedPlan}
          onClose={() => setSelectedPlan(null)}
          onArchive={handleArchive}
        />
      )}
    </DashboardLayout>
  );
}
