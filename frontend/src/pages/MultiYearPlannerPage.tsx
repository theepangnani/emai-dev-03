import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { useAuth } from '../context/AuthContext';
import './MultiYearPlannerPage.css';

// ─── Types ───────────────────────────────────────────────────────────────────

interface PlanCourse {
  id: number;
  course_code: string;
  course_name: string;
  credits: number;
  subject_area: string;
  grade: number;
  semester: 1 | 2;
  status: 'planned' | 'in_progress' | 'completed' | 'dropped';
  prerequisites?: string[];
  course_type?: string; // U, M, C, O, E
}

interface AcademicPlan {
  id: number;
  name: string;
  student_name: string;
  total_credits_earned: number;
  total_credits_planned: number;
  graduation_year: number;
  plan_courses: PlanCourse[];
}

interface OssdRequirement {
  category: string;
  required: number;
  earned: number;
  label: string;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const SUBJECT_COLORS: Record<string, string> = {
  English: '#3b82f6',
  Math: '#8b5cf6',
  Science: '#10b981',
  Languages: '#f97316',
  Arts: '#ec4899',
  'Social Sciences': '#06b6d4',
  'Canadian & World Studies': '#06b6d4',
  'Guidance & Career Education': '#84cc16',
  'Health & Physical Education': '#22c55e',
  'Technological Education': '#f59e0b',
  'Business Studies': '#64748b',
  default: '#94a3b8',
};

function getSubjectColor(subjectArea: string): string {
  for (const [key, color] of Object.entries(SUBJECT_COLORS)) {
    if (subjectArea?.toLowerCase().includes(key.toLowerCase())) return color;
  }
  return SUBJECT_COLORS.default;
}

const GRADES = [9, 10, 11, 12] as const;
const SEMESTERS = [1, 2] as const;

const OSSD_REQUIREMENTS: OssdRequirement[] = [
  { category: 'english', required: 4, earned: 0, label: 'English (4 credits)' },
  { category: 'math', required: 3, earned: 0, label: 'Math (3 credits)' },
  { category: 'science', required: 2, earned: 0, label: 'Science (2 credits)' },
  { category: 'french', required: 1, earned: 0, label: 'French (1 credit)' },
  { category: 'canadian', required: 1, earned: 0, label: 'Canadian History (1 credit)' },
  { category: 'geography', required: 1, earned: 0, label: 'Geography (1 credit)' },
  { category: 'arts', required: 1, earned: 0, label: 'Arts (1 credit)' },
  { category: 'health', required: 1, earned: 0, label: 'Health & PE (1 credit)' },
  { category: 'civics', required: 0.5, earned: 0, label: 'Civics (0.5)' },
  { category: 'careers', required: 0.5, earned: 0, label: 'Careers (0.5)' },
];

const TOTAL_CREDITS_REQUIRED = 30;

// ─── Mock data (used when API is unavailable) ─────────────────────────────────

const MOCK_PLAN: AcademicPlan = {
  id: 1,
  name: 'My Academic Plan',
  student_name: 'Student',
  total_credits_earned: 8,
  total_credits_planned: 14,
  graduation_year: 2027,
  plan_courses: [
    { id: 1, course_code: 'ENG1D', course_name: 'English', credits: 1, subject_area: 'English', grade: 9, semester: 1, status: 'completed', course_type: 'D' },
    { id: 2, course_code: 'MPM1D', course_name: 'Principles of Mathematics', credits: 1, subject_area: 'Math', grade: 9, semester: 1, status: 'completed', course_type: 'D' },
    { id: 3, course_code: 'SNC1D', course_name: 'Science', credits: 1, subject_area: 'Science', grade: 9, semester: 1, status: 'completed', course_type: 'D' },
    { id: 4, course_code: 'CGC1D', course_name: 'Issues in Canadian Geography', credits: 1, subject_area: 'Geography', grade: 9, semester: 2, status: 'completed', course_type: 'D' },
    { id: 5, course_code: 'FSF1D', course_name: 'Core French', credits: 1, subject_area: 'Languages', grade: 9, semester: 2, status: 'completed', course_type: 'D' },
    { id: 6, course_code: 'PPL1O', course_name: 'Health & Physical Education', credits: 1, subject_area: 'Health & Physical Education', grade: 9, semester: 2, status: 'completed', course_type: 'O' },
    { id: 7, course_code: 'ENG2D', course_name: 'English', credits: 1, subject_area: 'English', grade: 10, semester: 1, status: 'completed', course_type: 'D' },
    { id: 8, course_code: 'MPM2D', course_name: 'Principles of Mathematics', credits: 1, subject_area: 'Math', grade: 10, semester: 1, status: 'completed', course_type: 'D' },
    { id: 9, course_code: 'CHC2D', course_name: 'Canadian History Since WW1', credits: 1, subject_area: 'Canadian & World Studies', grade: 10, semester: 1, status: 'in_progress', course_type: 'D' },
    { id: 10, course_code: 'CHV2O', course_name: 'Civics and Citizenship', credits: 0.5, subject_area: 'Guidance & Career Education', grade: 10, semester: 2, status: 'in_progress', course_type: 'O' },
    { id: 11, course_code: 'GLC2O', course_name: 'Learning Strategies', credits: 0.5, subject_area: 'Guidance & Career Education', grade: 10, semester: 2, status: 'in_progress', course_type: 'O' },
    { id: 12, course_code: 'ENG3U', course_name: 'English', credits: 1, subject_area: 'English', grade: 11, semester: 1, status: 'planned', course_type: 'U' },
    { id: 13, course_code: 'MCR3U', course_name: 'Functions', credits: 1, subject_area: 'Math', grade: 11, semester: 1, status: 'planned', course_type: 'U' },
    { id: 14, course_code: 'SCH3U', course_name: 'Chemistry', credits: 1, subject_area: 'Science', grade: 11, semester: 2, status: 'planned', course_type: 'U' },
    { id: 15, course_code: 'ENG4U', course_name: 'English', credits: 1, subject_area: 'English', grade: 12, semester: 1, status: 'planned', course_type: 'U' },
    { id: 16, course_code: 'MHF4U', course_name: 'Advanced Functions', credits: 1, subject_area: 'Math', grade: 12, semester: 1, status: 'planned', course_type: 'U' },
    { id: 17, course_code: 'SPH4U', course_name: 'Physics', credits: 1, subject_area: 'Science', grade: 12, semester: 2, status: 'planned', course_type: 'U' },
  ],
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function truncate(str: string, max: number): string {
  return str.length > max ? str.slice(0, max - 1) + '\u2026' : str;
}

function computeRequirements(courses: PlanCourse[]): OssdRequirement[] {
  const countedCourses = courses.filter(c => c.status !== 'dropped');

  return OSSD_REQUIREMENTS.map(req => {
    let earned = 0;
    for (const c of countedCourses) {
      const area = c.subject_area?.toLowerCase() ?? '';
      const code = c.course_code?.toLowerCase() ?? '';
      if (req.category === 'english' && area.includes('english')) earned += c.credits;
      else if (req.category === 'math' && area.includes('math')) earned += c.credits;
      else if (req.category === 'science' && area.includes('science')) earned += c.credits;
      else if (req.category === 'french' && (area.includes('french') || code.startsWith('fs'))) earned += c.credits;
      else if (req.category === 'canadian' && (area.includes('canadian') || code.startsWith('chc'))) earned += c.credits;
      else if (req.category === 'geography' && (area.includes('geography') || code.startsWith('cgc'))) earned += c.credits;
      else if (req.category === 'arts' && area.includes('arts')) earned += c.credits;
      else if (req.category === 'health' && area.includes('health')) earned += c.credits;
      else if (req.category === 'civics' && code.startsWith('chv')) earned += c.credits;
      else if (req.category === 'careers' && code.startsWith('glc')) earned += c.credits;
    }
    return { ...req, earned: Math.min(earned, req.required) };
  });
}

function computePathway(courses: PlanCourse[]) {
  const uMCredits = courses.filter(c => c.status !== 'dropped' && (c.course_type === 'U' || c.course_type === 'M')).reduce((s, c) => s + c.credits, 0);
  const cCredits = courses.filter(c => c.status !== 'dropped' && c.course_type === 'C').reduce((s, c) => s + c.credits, 0);
  const universityOk = uMCredits >= 6;
  const collegeOk = cCredits >= 3 || uMCredits >= 3;
  return { uMCredits, cCredits, universityOk, collegeOk };
}

// ─── Tooltip component ────────────────────────────────────────────────────────

interface CourseTooltipProps {
  course: PlanCourse;
  onClose: () => void;
}

function CourseTooltip({ course, onClose }: CourseTooltipProps) {
  const statusLabels: Record<string, string> = {
    planned: 'Planned',
    in_progress: 'In Progress',
    completed: 'Completed',
    dropped: 'Dropped',
  };
  return (
    <div className="myp-tooltip" role="tooltip" onClick={onClose}>
      <div className="myp-tooltip-header">
        <span className="myp-tooltip-code">{course.course_code}</span>
        <span className={`myp-tooltip-status myp-status-${course.status}`}>{statusLabels[course.status]}</span>
      </div>
      <div className="myp-tooltip-name">{course.course_name}</div>
      <div className="myp-tooltip-meta">
        <span>{course.credits} credit{course.credits !== 1 ? 's' : ''}</span>
        <span>{course.subject_area}</span>
        {course.course_type && <span>Type: {course.course_type}</span>}
      </div>
      {course.prerequisites && course.prerequisites.length > 0 && (
        <div className="myp-tooltip-prereqs">
          <span className="myp-tooltip-prereq-label">Prerequisites:</span>
          {course.prerequisites.map(p => <span key={p} className="myp-tooltip-prereq-chip">{p}</span>)}
        </div>
      )}
    </div>
  );
}

// ─── Course Chip ─────────────────────────────────────────────────────────────

interface CourseChipProps {
  course: PlanCourse;
  onSelect: (course: PlanCourse) => void;
  selected: boolean;
}

function CourseChip({ course, onSelect, selected }: CourseChipProps) {
  const color = getSubjectColor(course.subject_area);
  return (
    <button
      className={`myp-chip myp-chip-${course.status}${selected ? ' myp-chip-selected' : ''}`}
      style={{ '--chip-color': color } as React.CSSProperties}
      onClick={() => onSelect(course)}
      title={course.course_name}
      type="button"
      aria-pressed={selected}
    >
      {course.status === 'completed' && (
        <svg className="myp-chip-check" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      )}
      <span className="myp-chip-code">{course.course_code}</span>
      <span className="myp-chip-name">{truncate(course.course_name, 20)}</span>
    </button>
  );
}

// ─── Circular Progress ────────────────────────────────────────────────────────

interface CircularProgressProps {
  value: number; // 0–100
  size?: number;
  strokeWidth?: number;
  label?: string;
}

function CircularProgress({ value, size = 80, strokeWidth = 8, label }: CircularProgressProps) {
  const r = (size - strokeWidth) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (value / 100) * circ;
  return (
    <div className="myp-circle-wrap" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-border)" strokeWidth={strokeWidth} />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none"
          stroke="var(--color-accent)"
          strokeWidth={strokeWidth}
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: 'stroke-dashoffset 0.6s ease' }}
        />
      </svg>
      <span className="myp-circle-label">{label ?? `${Math.round(value)}%`}</span>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export function MultiYearPlannerPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [plan, setPlan] = useState<AcademicPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCourse, setSelectedCourse] = useState<PlanCourse | null>(null);
  const [hoveredGrade, setHoveredGrade] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    // Try to fetch from API; fall back to mock data gracefully
    fetch('/api/academic-plans/', {
      headers: {
        Authorization: `Bearer ${localStorage.getItem('token') ?? ''}`,
      },
    })
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: AcademicPlan[]) => {
        if (cancelled) return;
        if (data.length > 0) {
          setPlan(data[0]);
        } else {
          setPlan({ ...MOCK_PLAN, student_name: user?.full_name ?? 'Student' });
        }
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        // API not available yet — show mock data
        setPlan({ ...MOCK_PLAN, student_name: user?.full_name ?? 'Student' });
        setLoading(false);
        setError(null); // not an error to surface
      });
    return () => { cancelled = true; };
  }, [user]);

  const handleChipSelect = (course: PlanCourse) => {
    setSelectedCourse(prev => prev?.id === course.id ? null : course);
  };

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Academic Overview">
        <div className="myp-loading" aria-busy="true" aria-label="Loading plan">
          <div className="myp-loading-grid">
            {[...Array(8)].map((_, i) => <div key={i} className="skeleton myp-loading-cell" />)}
          </div>
        </div>
      </DashboardLayout>
    );
  }

  if (!plan) {
    return (
      <DashboardLayout welcomeSubtitle="Academic Overview">
        <div className="myp-empty">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <line x1="3" y1="9" x2="21" y2="9" />
            <line x1="9" y1="21" x2="9" y2="9" />
          </svg>
          <h2>No Academic Plan Yet</h2>
          <p>Start building your 4-year plan to see the overview here.</p>
          <button className="myp-btn-primary" onClick={() => navigate('/planner')}>
            Start Planning
          </button>
        </div>
      </DashboardLayout>
    );
  }

  const allCourses = plan.plan_courses ?? [];
  const totalCredits = allCourses.filter(c => c.status !== 'dropped').reduce((s, c) => s + c.credits, 0);
  const pct = Math.min(100, Math.round((totalCredits / TOTAL_CREDITS_REQUIRED) * 100));

  const requirements = computeRequirements(allCourses);
  const pathway = computePathway(allCourses);

  const missingCodes: string[] = [];
  if (!allCourses.some(c => c.course_code === 'ENG4U')) missingCodes.push('ENG4U');
  if (!allCourses.some(c => c.course_code.startsWith('CHV'))) missingCodes.push('CHV2O');
  if (!allCourses.some(c => c.course_code.startsWith('GLC'))) missingCodes.push('GLC2O');

  return (
    <DashboardLayout welcomeSubtitle="Academic Overview">
      {error && <div className="myp-api-notice" role="status">{error}</div>}

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="myp-header">
        <div className="myp-header-left">
          <h1 className="myp-plan-name">{plan.name}</h1>
          <p className="myp-student-name">{plan.student_name}</p>
        </div>
        <div className="myp-header-center">
          <CircularProgress value={pct} size={80} label={`${pct}%`} />
          <div className="myp-header-stats">
            <span className="myp-credit-count">{totalCredits}/{TOTAL_CREDITS_REQUIRED} credits</span>
            <span className="myp-credit-pct">{pct}% complete</span>
            <span className="myp-grad-year">Grad {plan.graduation_year}</span>
          </div>
        </div>
        <div className="myp-header-right">
          <button className="myp-btn-primary" onClick={() => navigate('/planner')}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
            Edit in Planner
          </button>
        </div>
      </div>

      <div className="myp-body">
        {/* ── Main Grid ─────────────────────────────────────────────────── */}
        <div className="myp-grid-wrap">
          <div className="myp-grid">
            {/* Column headers */}
            <div className="myp-grid-corner" />
            {GRADES.map(grade => (
              <div
                key={grade}
                className={`myp-col-header${hoveredGrade === grade ? ' myp-col-hovered' : ''}`}
                onMouseEnter={() => setHoveredGrade(grade)}
                onMouseLeave={() => setHoveredGrade(null)}
              >
                Grade {grade}
              </div>
            ))}

            {/* Rows */}
            {SEMESTERS.map(sem => (
              <>
                <div key={`sem-${sem}`} className="myp-row-header">Sem {sem}</div>
                {GRADES.map(grade => {
                  const cell = allCourses.filter(c => c.grade === grade && c.semester === sem);
                  return (
                    <div
                      key={`${grade}-${sem}`}
                      className={`myp-cell${hoveredGrade === grade ? ' myp-cell-hovered' : ''}`}
                      onMouseEnter={() => setHoveredGrade(grade)}
                      onMouseLeave={() => setHoveredGrade(null)}
                    >
                      {cell.length === 0 ? (
                        <span className="myp-cell-empty">No courses</span>
                      ) : (
                        cell.map(course => (
                          <CourseChip
                            key={course.id}
                            course={course}
                            onSelect={handleChipSelect}
                            selected={selectedCourse?.id === course.id}
                          />
                        ))
                      )}
                    </div>
                  );
                })}
              </>
            ))}
          </div>

          {/* Course tooltip */}
          {selectedCourse && (
            <CourseTooltip
              course={selectedCourse}
              onClose={() => setSelectedCourse(null)}
            />
          )}
        </div>

        {/* ── Right Panel ───────────────────────────────────────────────── */}
        <aside className="myp-side-panel">
          <h2 className="myp-panel-title">Graduation Progress</h2>

          {/* OSSD Requirements */}
          <div className="myp-requirements">
            {requirements.map(req => {
              const done = req.earned >= req.required;
              const partial = !done && req.earned > 0;
              return (
                <div key={req.category} className={`myp-req-row${done ? ' myp-req-done' : partial ? ' myp-req-partial' : ''}`}>
                  <span className="myp-req-icon" aria-hidden="true">
                    {done ? (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    ) : (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="12" r="10" />
                      </svg>
                    )}
                  </span>
                  <span className="myp-req-label">{req.label}</span>
                  <span className="myp-req-count">
                    {req.earned}/{req.required}
                    {done && <span className="myp-req-check-text"> ✓</span>}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Total credits */}
          <div className="myp-total-credits">
            <span className="myp-total-label">Total Credits</span>
            <span className="myp-total-value">{totalCredits}/{TOTAL_CREDITS_REQUIRED}</span>
          </div>

          {/* Missing courses */}
          {missingCodes.length > 0 && (
            <div className="myp-missing">
              <span className="myp-missing-label">Missing compulsory:</span>
              <div className="myp-missing-list">
                {missingCodes.map(code => (
                  <span key={code} className="myp-missing-chip">{code}</span>
                ))}
              </div>
            </div>
          )}

          {/* Pathway Indicator */}
          <div className="myp-pathway">
            <h3 className="myp-pathway-title">Pathway</h3>
            <div className={`myp-pathway-row${pathway.universityOk ? ' myp-pathway-ok' : ' myp-pathway-warn'}`}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
              <span>University: {pathway.uMCredits} U/M credits</span>
              <span className="myp-pathway-verdict">{pathway.universityOk ? 'University-bound ✓' : 'Insufficient'}</span>
            </div>
            <div className={`myp-pathway-row${pathway.collegeOk ? ' myp-pathway-ok' : ' myp-pathway-warn'}`}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
              <span>College: {pathway.cCredits} C credits</span>
              <span className="myp-pathway-verdict">{pathway.collegeOk ? 'College-ready ✓' : 'Insufficient'}</span>
            </div>
          </div>
        </aside>
      </div>

      {/* Legend */}
      <div className="myp-legend">
        <span className="myp-legend-title">Status:</span>
        {(['completed', 'in_progress', 'planned', 'dropped'] as const).map(s => (
          <span key={s} className={`myp-legend-item myp-chip-${s}`}>
            {s === 'in_progress' ? 'In Progress' : s.charAt(0).toUpperCase() + s.slice(1)}
          </span>
        ))}
      </div>
    </DashboardLayout>
  );
}
