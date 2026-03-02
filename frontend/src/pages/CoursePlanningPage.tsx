import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { useAuth } from '../context/AuthContext';
import './CoursePlanningPage.css';

// ─── Types ───────────────────────────────────────────────────────────────────

interface PlanSummary {
  id: number;
  name: string;
  student_name: string;
  student_id?: number;
  total_credits: number;
  completion_pct: number;
  graduation_year: number;
  has_plan: boolean;
}

interface ChildPlan {
  child_id: number;
  child_name: string;
  plan: PlanSummary | null;
}

// ─── Mock helpers ─────────────────────────────────────────────────────────────

function makeMockSummary(studentName: string, studentId?: number): PlanSummary {
  return {
    id: studentId ?? 1,
    name: `${studentName}'s Plan`,
    student_name: studentName,
    student_id: studentId,
    total_credits: 14,
    completion_pct: 47,
    graduation_year: 2027,
    has_plan: true,
  };
}

// ─── Sub-components ───────────────────────────────────────────────────────────

interface PlanCardProps {
  summary: PlanSummary;
  onOpenPlanner: () => void;
  onViewOverview: () => void;
}

function PlanSummaryCard({ summary, onOpenPlanner, onViewOverview }: PlanCardProps) {
  return (
    <div className="cp-plan-card">
      <div className="cp-plan-card-header">
        <div>
          <h3 className="cp-plan-card-name">{summary.name}</h3>
          <p className="cp-plan-card-student">{summary.student_name}</p>
        </div>
        <div className="cp-plan-card-grad">
          <span className="cp-plan-card-grad-label">Grad Year</span>
          <span className="cp-plan-card-grad-value">{summary.graduation_year}</span>
        </div>
      </div>

      <div className="cp-plan-card-progress">
        <div className="cp-plan-card-progress-bar">
          <div
            className="cp-plan-card-progress-fill"
            style={{ width: `${summary.completion_pct}%` }}
            role="progressbar"
            aria-valuenow={summary.completion_pct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${summary.completion_pct}% complete`}
          />
        </div>
        <span className="cp-plan-card-progress-label">
          {summary.total_credits} / 30 credits &mdash; {summary.completion_pct}%
        </span>
      </div>

      <div className="cp-plan-card-actions">
        <button className="cp-btn-primary" onClick={onOpenPlanner}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
          </svg>
          Open Planner
        </button>
        <button className="cp-btn-secondary" onClick={onViewOverview}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <line x1="3" y1="9" x2="21" y2="9" />
            <line x1="9" y1="21" x2="9" y2="9" />
          </svg>
          View Overview
        </button>
      </div>
    </div>
  );
}

// ─── Start Planning CTA ───────────────────────────────────────────────────────

function StartPlanningCard({ onStart }: { onStart: () => void }) {
  return (
    <div className="cp-start-card">
      <div className="cp-start-card-icon" aria-hidden="true">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5z" />
          <path d="M2 17l10 5 10-5" />
          <path d="M2 12l10 5 10-5" />
        </svg>
      </div>
      <h3 className="cp-start-card-title">No Plan Yet</h3>
      <p className="cp-start-card-desc">
        Start mapping out your Ontario high school journey. Plan courses across all four grades to stay on track for graduation.
      </p>
      <button className="cp-btn-primary cp-btn-lg" onClick={onStart}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        Start Planning
      </button>
    </div>
  );
}

// ─── Mini Plan Summary ────────────────────────────────────────────────────────

function MiniPlanSummary({ plan, onView }: { plan: PlanSummary | null; onView: () => void }) {
  if (!plan) {
    return (
      <div className="cp-mini-no-plan">
        <span>No plan yet</span>
        <button className="cp-btn-link" onClick={onView}>Start</button>
      </div>
    );
  }
  return (
    <div className="cp-mini-plan">
      <div className="cp-mini-progress-bar">
        <div className="cp-mini-progress-fill" style={{ width: `${plan.completion_pct}%` }} />
      </div>
      <div className="cp-mini-stats">
        <span className="cp-mini-credits">{plan.total_credits}/30 credits</span>
        <span className="cp-mini-pct">{plan.completion_pct}%</span>
        <span className="cp-mini-grad">Grad {plan.graduation_year}</span>
      </div>
      <button className="cp-btn-link cp-mini-view" onClick={onView}>View</button>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export function CoursePlanningPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [planSummary, setPlanSummary] = useState<PlanSummary | null>(null);
  const [childPlans, setChildPlans] = useState<ChildPlan[]>([]);
  const [activeChildTab, setActiveChildTab] = useState<number | null>(null);

  const isParent = user?.role === 'parent';
  const firstName = user?.full_name?.split(' ')[0] ?? 'there';

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    fetch('/api/academic-plans/', {
      headers: { Authorization: `Bearer ${localStorage.getItem('token') ?? ''}` },
    })
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: Array<{ id: number; name: string; student_name: string; student_id?: number; plan_courses?: Array<{ credits: number; status: string }>; graduation_year?: number }>) => {
        if (cancelled) return;
        if (data.length > 0) {
          const p = data[0];
          const courses = p.plan_courses ?? [];
          const counted = courses.filter((c) => c.status !== 'dropped');
          const total = counted.reduce((s: number, c: { credits: number }) => s + c.credits, 0);
          const pct = Math.min(100, Math.round((total / 30) * 100));
          setPlanSummary({
            id: p.id,
            name: p.name,
            student_name: p.student_name,
            total_credits: total,
            completion_pct: pct,
            graduation_year: p.graduation_year ?? 2027,
            has_plan: true,
          });

          if (isParent) {
            setChildPlans(data.map((plan) => {
              const cs = plan.plan_courses ?? [];
              const ct = cs.filter((c) => c.status !== 'dropped');
              const t = ct.reduce((s: number, c: { credits: number }) => s + c.credits, 0);
              return {
                child_id: plan.student_id ?? plan.id,
                child_name: plan.student_name,
                plan: {
                  id: plan.id,
                  name: plan.name,
                  student_name: plan.student_name,
                  total_credits: t,
                  completion_pct: Math.min(100, Math.round((t / 30) * 100)),
                  graduation_year: plan.graduation_year ?? 2027,
                  has_plan: true,
                },
              };
            }));
            if (data.length > 0 && data[0].student_id) setActiveChildTab(data[0].student_id);
          }
        } else {
          // No plans → show "Start Planning"
          if (isParent) {
            // Would normally load children list here
            setChildPlans([
              { child_id: 1, child_name: 'Child 1', plan: null },
            ]);
          }
        }
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        // Fall back to mock data
        const mock = makeMockSummary(isParent ? 'Alex' : (user?.full_name ?? 'Student'));
        setPlanSummary(mock);
        if (isParent) {
          const mockChildren: ChildPlan[] = [
            { child_id: 1, child_name: 'Alex', plan: makeMockSummary('Alex', 1) },
            { child_id: 2, child_name: 'Sam', plan: makeMockSummary('Sam', 2) },
          ];
          setChildPlans(mockChildren);
          setActiveChildTab(1);
        }
        setLoading(false);
      });

    return () => { cancelled = true; };
  }, [isParent, user]);

  const activeChild = childPlans.find(c => c.child_id === activeChildTab) ?? childPlans[0] ?? null;

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Course Planning">
        <div className="cp-loading">
          <div className="skeleton cp-skeleton-hero" />
          <div className="skeleton cp-skeleton-card" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout welcomeSubtitle="Course Planning">
      {/* ── Hero ────────────────────────────────────────────────────────── */}
      <div className="cp-hero">
        <div className="cp-hero-text">
          <h1 className="cp-hero-title">Plan Your Ontario High School Journey</h1>
          <p className="cp-hero-subtitle">
            {isParent
              ? `Monitor and guide ${firstName.endsWith('s') ? firstName + "'" : firstName + "'s"} academic planning`
              : `Hi ${firstName}, map out your path to graduation — one course at a time`}
          </p>
        </div>
        <div className="cp-hero-icon" aria-hidden="true">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5z" opacity="0.5" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        </div>
      </div>

      {/* ── Student view: plan summary + quick links ──────────────────── */}
      {!isParent && (
        <>
          {planSummary ? (
            <PlanSummaryCard
              summary={planSummary}
              onOpenPlanner={() => navigate('/planner')}
              onViewOverview={() => navigate('/planner/overview')}
            />
          ) : (
            <StartPlanningCard onStart={() => navigate('/planner')} />
          )}

          {/* Quick links */}
          <div className="cp-quick-links">
            <h2 className="cp-section-title">Quick Links</h2>
            <div className="cp-quick-links-grid">
              <button className="cp-quick-link-item" onClick={() => navigate('/planner')}>
                <span className="cp-quick-link-icon" aria-hidden="true">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                    <line x1="16" y1="2" x2="16" y2="6" />
                    <line x1="8" y1="2" x2="8" y2="6" />
                    <line x1="3" y1="10" x2="21" y2="10" />
                  </svg>
                </span>
                <span className="cp-quick-link-label">Open Planner</span>
                <span className="cp-quick-link-desc">Semester-by-semester view</span>
              </button>

              <button className="cp-quick-link-item" onClick={() => navigate('/planner/overview')}>
                <span className="cp-quick-link-icon" aria-hidden="true">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <line x1="3" y1="9" x2="21" y2="9" />
                    <line x1="9" y1="21" x2="9" y2="9" />
                  </svg>
                </span>
                <span className="cp-quick-link-label">View Overview</span>
                <span className="cp-quick-link-desc">4-year grid at a glance</span>
              </button>

              <button className="cp-quick-link-item" onClick={() => navigate('/planner/ai')}>
                <span className="cp-quick-link-icon cp-quick-link-icon-ai" aria-hidden="true">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2a10 10 0 1 0 10 10" />
                    <path d="M22 2 12 12" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                </span>
                <span className="cp-quick-link-label">AI Recommendations</span>
                <span className="cp-quick-link-desc">Get personalized guidance</span>
              </button>
            </div>
          </div>
        </>
      )}

      {/* ── Parent view: My Kids' Plans ───────────────────────────────── */}
      {isParent && (
        <>
          {childPlans.length === 0 ? (
            <div className="cp-no-children">
              <p>No children linked yet. Add a child to track their course planning.</p>
              <button className="cp-btn-primary" onClick={() => navigate('/my-kids')}>
                Manage Children
              </button>
            </div>
          ) : (
            <div className="cp-kids-plans">
              <h2 className="cp-section-title">My Kids' Plans</h2>

              {/* Child tabs */}
              <div className="cp-child-tabs" role="tablist" aria-label="Children">
                {childPlans.map(child => (
                  <button
                    key={child.child_id}
                    role="tab"
                    aria-selected={activeChildTab === child.child_id}
                    className={`cp-child-tab${activeChildTab === child.child_id ? ' cp-child-tab-active' : ''}`}
                    onClick={() => setActiveChildTab(child.child_id)}
                  >
                    <span className="cp-child-tab-avatar">{child.child_name.charAt(0)}</span>
                    {child.child_name}
                  </button>
                ))}
              </div>

              {/* Active child plan */}
              {activeChild && (
                <div className="cp-child-panel" role="tabpanel">
                  {activeChild.plan ? (
                    <PlanSummaryCard
                      summary={activeChild.plan}
                      onOpenPlanner={() => navigate('/planner')}
                      onViewOverview={() => navigate('/planner/overview')}
                    />
                  ) : (
                    <StartPlanningCard onStart={() => navigate('/planner')} />
                  )}
                </div>
              )}

              {/* Mini summaries for all children */}
              {childPlans.length > 1 && (
                <div className="cp-all-mini-plans">
                  <h3 className="cp-subsection-title">All Children at a Glance</h3>
                  <div className="cp-mini-plans-grid">
                    {childPlans.map(child => (
                      <div key={child.child_id} className="cp-mini-plan-wrap">
                        <div className="cp-mini-plan-child-name">{child.child_name}</div>
                        <MiniPlanSummary
                          plan={child.plan}
                          onView={() => {
                            setActiveChildTab(child.child_id);
                            navigate('/planner/overview');
                          }}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Parent quick links */}
          <div className="cp-quick-links">
            <h2 className="cp-section-title">Planning Tools</h2>
            <div className="cp-quick-links-grid">
              <button className="cp-quick-link-item" onClick={() => navigate('/planner')}>
                <span className="cp-quick-link-icon" aria-hidden="true">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                    <line x1="16" y1="2" x2="16" y2="6" />
                    <line x1="8" y1="2" x2="8" y2="6" />
                    <line x1="3" y1="10" x2="21" y2="10" />
                  </svg>
                </span>
                <span className="cp-quick-link-label">Open Planner</span>
                <span className="cp-quick-link-desc">Edit semester courses</span>
              </button>

              <button className="cp-quick-link-item" onClick={() => navigate('/planner/overview')}>
                <span className="cp-quick-link-icon" aria-hidden="true">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <line x1="3" y1="9" x2="21" y2="9" />
                    <line x1="9" y1="21" x2="9" y2="9" />
                  </svg>
                </span>
                <span className="cp-quick-link-label">View Overview</span>
                <span className="cp-quick-link-desc">4-year grid</span>
              </button>

              <button className="cp-quick-link-item" onClick={() => navigate('/planner/ai')}>
                <span className="cp-quick-link-icon cp-quick-link-icon-ai" aria-hidden="true">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2a10 10 0 1 0 10 10" />
                    <path d="M22 2 12 12" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                </span>
                <span className="cp-quick-link-label">AI Recommendations</span>
                <span className="cp-quick-link-desc">Personalized guidance</span>
              </button>
            </div>
          </div>
        </>
      )}
    </DashboardLayout>
  );
}
