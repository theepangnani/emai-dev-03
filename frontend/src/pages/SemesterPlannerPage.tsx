import { useState, useEffect, useRef, useCallback } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { useAuth } from '../context/AuthContext';
import {
  academicPlanApi,
  type AcademicPlan,
  type CourseCatalogItem,
  type OntarioBoard,
  type PlanCourse,
  type ValidationResult,
  type CoursePathway,
} from '../api/academicPlan';
import './SemesterPlannerPage.css';

// ─── Constants ────────────────────────────────────────────────────────────────

const GRADES = [9, 10, 11, 12] as const;
type Grade = (typeof GRADES)[number];
const SEMESTERS = [1, 2] as const;
type Semester = (typeof SEMESTERS)[number];

const SUBJECT_TABS = [
  'All',
  'English',
  'Math',
  'Science',
  'Languages',
  'Arts',
  'Tech',
  'Electives',
] as const;
type SubjectTab = (typeof SUBJECT_TABS)[number];

const SUBJECT_FILTER_MAP: Record<SubjectTab, string | undefined> = {
  All: undefined,
  English: 'English',
  Math: 'Mathematics',
  Science: 'Science',
  Languages: 'Languages',
  Arts: 'Arts',
  Tech: 'Technology',
  Electives: 'Electives',
};

const PATHWAY_LABELS: Record<CoursePathway, string> = {
  U: 'University',
  C: 'College',
  M: 'Mixed',
  E: 'Workplace',
  O: 'Open',
};

const OSSD_CREDIT_TARGET = 30;

// ─── Sub-components ───────────────────────────────────────────────────────────

function PathwayBadge({ pathway }: { pathway: CoursePathway }) {
  return (
    <span className={`pathway-badge pathway-${pathway.toLowerCase()}`} title={PATHWAY_LABELS[pathway]}>
      {pathway}
    </span>
  );
}

function CreditChip({ credits }: { credits: number }) {
  return <span className="credit-chip">{credits} cr</span>;
}

function CatalogCourseCard({
  course,
  onAddClick,
  onDragStart,
}: {
  course: CourseCatalogItem;
  onAddClick: (course: CourseCatalogItem) => void;
  onDragStart: (e: React.DragEvent, course: CourseCatalogItem) => void;
}) {
  return (
    <div
      className="catalog-course-card"
      draggable
      onDragStart={(e) => onDragStart(e, course)}
      aria-label={`${course.course_code} ${course.course_name}`}
    >
      <div className="catalog-card-header">
        <span className="catalog-course-code">{course.course_code}</span>
        <div className="catalog-card-badges">
          <PathwayBadge pathway={course.pathway} />
          <CreditChip credits={course.credits} />
        </div>
      </div>
      <div className="catalog-course-name">{course.course_name}</div>
      <div className="catalog-card-footer">
        <span className="catalog-subject">{course.subject_area}</span>
        <div className="catalog-card-actions">
          <span className="drag-handle" aria-hidden="true" title="Drag to add">⠿</span>
          <button
            className="catalog-add-btn"
            onClick={() => onAddClick(course)}
            aria-label={`Add ${course.course_code}`}
          >
            + Add
          </button>
        </div>
      </div>
    </div>
  );
}

function PlanCourseCard({
  course,
  onRemove,
}: {
  course: PlanCourse;
  onRemove: (id: number) => void;
}) {
  return (
    <div
      className={`plan-course-card${course.has_prerequisite_warning ? ' prereq-warning' : ''}`}
      title={course.has_prerequisite_warning ? 'Prerequisite may not be met in prior semesters' : undefined}
    >
      <div className="plan-card-header">
        <span className="plan-course-code">{course.course_code}</span>
        <button
          className="plan-remove-btn"
          onClick={() => onRemove(course.id)}
          aria-label={`Remove ${course.course_code}`}
        >
          &times;
        </button>
      </div>
      <div className="plan-course-name">{course.course_name}</div>
      <div className="plan-card-footer">
        <PathwayBadge pathway={course.pathway} />
        <CreditChip credits={course.credits} />
        {course.has_prerequisite_warning && (
          <span className="prereq-chip" title="Prerequisite not yet met">
            Prereq
          </span>
        )}
      </div>
    </div>
  );
}

// ─── Add-to-semester modal ─────────────────────────────────────────────────────

function AddCourseModal({
  course,
  onConfirm,
  onClose,
}: {
  course: CourseCatalogItem;
  onConfirm: (grade: Grade, semester: Semester) => void;
  onClose: () => void;
}) {
  const [selectedGrade, setSelectedGrade] = useState<Grade>(course.grade_level);
  const [selectedSemester, setSelectedSemester] = useState<Semester>(1);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Close">&times;</button>
        <h3 className="modal-title">Add to Semester</h3>
        <p className="modal-subtitle">
          <strong>{course.course_code}</strong> — {course.course_name}
        </p>
        <div className="modal-field">
          <label className="modal-label">Grade</label>
          <div className="modal-btn-group">
            {GRADES.map((g) => (
              <button
                key={g}
                className={`modal-btn${selectedGrade === g ? ' active' : ''}`}
                onClick={() => setSelectedGrade(g)}
              >
                {g}
              </button>
            ))}
          </div>
        </div>
        <div className="modal-field">
          <label className="modal-label">Semester</label>
          <div className="modal-btn-group">
            {SEMESTERS.map((s) => (
              <button
                key={s}
                className={`modal-btn${selectedSemester === s ? ' active' : ''}`}
                onClick={() => setSelectedSemester(s)}
              >
                Semester {s}
              </button>
            ))}
          </div>
        </div>
        <div className="modal-actions">
          <button className="modal-cancel" onClick={onClose}>Cancel</button>
          <button
            className="modal-confirm"
            onClick={() => onConfirm(selectedGrade, selectedSemester)}
          >
            Add Course
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Validation modal ─────────────────────────────────────────────────────────

function ValidationModal({
  result,
  onClose,
}: {
  result: ValidationResult;
  onClose: () => void;
}) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box modal-validation" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Close">&times;</button>
        <h3 className="modal-title">Plan Validation</h3>
        <div className={`validation-status ${result.is_valid ? 'valid' : 'invalid'}`}>
          {result.is_valid ? 'Plan is valid' : 'Plan has issues'}
        </div>

        <div className="validation-credits">
          <span>{result.total_credits} / {OSSD_CREDIT_TARGET} credits</span>
          {result.credits_needed > 0 && (
            <span className="credits-needed"> — {result.credits_needed} more needed</span>
          )}
        </div>

        {result.ossd_requirements.length > 0 && (
          <div className="validation-section">
            <h4 className="validation-section-title">OSSD Requirements</h4>
            <ul className="validation-req-list">
              {result.ossd_requirements.map((req) => (
                <li key={req.name} className={`validation-req-item ${req.fulfilled ? 'fulfilled' : 'missing'}`}>
                  <span className="req-icon">{req.fulfilled ? '✓' : '✗'}</span>
                  <span className="req-name">{req.name}</span>
                  <span className="req-credits">{req.earned_credits}/{req.required_credits} cr</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {result.issues.length > 0 && (
          <div className="validation-section">
            <h4 className="validation-section-title">Issues</h4>
            <ul className="validation-issue-list">
              {result.issues.map((issue, i) => (
                <li key={i} className={`validation-issue ${issue.severity}`}>
                  <span className="issue-code">{issue.course_code}</span>
                  <span className="issue-msg">{issue.message}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="modal-actions">
          <button className="modal-confirm" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

// ─── Create plan prompt ───────────────────────────────────────────────────────

function CreatePlanPrompt({
  boards,
  onCreate,
  loading,
}: {
  boards: OntarioBoard[];
  onCreate: (name: string, boardId: number) => void;
  loading: boolean;
}) {
  const [planName, setPlanName] = useState('My Academic Plan');
  const [boardId, setBoardId] = useState<number>(boards[0]?.id ?? 0);

  return (
    <div className="create-plan-prompt">
      <h2 className="create-plan-title">Create Your Academic Plan</h2>
      <p className="create-plan-subtitle">
        Plan your course selections for Grades 9–12 to meet OSSD requirements.
      </p>
      <div className="create-plan-form">
        <label className="create-plan-label">Plan Name</label>
        <input
          className="create-plan-input"
          value={planName}
          onChange={(e) => setPlanName(e.target.value)}
          placeholder="e.g. My Academic Plan"
        />
        <label className="create-plan-label">School Board</label>
        <select
          className="create-plan-select"
          value={boardId}
          onChange={(e) => setBoardId(Number(e.target.value))}
        >
          {boards.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
        <button
          className="create-plan-btn"
          disabled={loading || !planName.trim() || !boardId}
          onClick={() => onCreate(planName.trim(), boardId)}
        >
          {loading ? 'Creating...' : 'Create Plan'}
        </button>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export function SemesterPlannerPage() {
  const { user } = useAuth();

  // Plan state
  const [plans, setPlans] = useState<AcademicPlan[]>([]);
  const [activePlan, setActivePlan] = useState<AcademicPlan | null>(null);
  const [planName, setPlanName] = useState('');
  const [editingPlanName, setEditingPlanName] = useState(false);
  const planNameRef = useRef<HTMLInputElement>(null);

  // Board + catalog state
  const [boards, setBoards] = useState<OntarioBoard[]>([]);
  const [selectedBoardId, setSelectedBoardId] = useState<number>(0);
  const [catalog, setCatalog] = useState<CourseCatalogItem[]>([]);
  const [filteredCatalog, setFilteredCatalog] = useState<CourseCatalogItem[]>([]);

  // Filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [activeSubject, setActiveSubject] = useState<SubjectTab>('All');
  const [gradeFilter, setGradeFilter] = useState<Grade | 'All'>('All');

  // UI state
  const [loading, setLoading] = useState(true);
  const [creatingPlan, setCreatingPlan] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addModalCourse, setAddModalCourse] = useState<CourseCatalogItem | null>(null);
  const [draggedCourse, setDraggedCourse] = useState<CourseCatalogItem | null>(null);
  const [dragOverCell, setDragOverCell] = useState<string | null>(null);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [validating, setValidating] = useState(false);

  const searchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Load on mount ──────────────────────────────────────────────────────────
  useEffect(() => {
    async function init() {
      try {
        setLoading(true);
        const [fetchedBoards, fetchedPlans] = await Promise.all([
          academicPlanApi.getBoards(),
          academicPlanApi.getPlans(),
        ]);
        setBoards(fetchedBoards);
        setPlans(fetchedPlans);

        if (fetchedPlans.length > 0) {
          const plan = fetchedPlans[0];
          setActivePlan(plan);
          setPlanName(plan.plan_name);
          setSelectedBoardId(plan.board_id);
        } else if (fetchedBoards.length > 0) {
          setSelectedBoardId(fetchedBoards[0].id);
        }
      } catch (err) {
        setError('Failed to load academic plans. Please try again.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  // ── Load catalog when board changes ────────────────────────────────────────
  useEffect(() => {
    if (!selectedBoardId) return;
    academicPlanApi
      .getCourses(selectedBoardId)
      .then((courses) => {
        setCatalog(courses);
        setFilteredCatalog(courses);
      })
      .catch(() => {
        // Catalog load failure is non-fatal; show empty state
        setCatalog([]);
        setFilteredCatalog([]);
      });
  }, [selectedBoardId]);

  // ── Filter catalog ─────────────────────────────────────────────────────────
  useEffect(() => {
    let result = catalog;

    if (activeSubject !== 'All') {
      const subjectValue = SUBJECT_FILTER_MAP[activeSubject];
      if (subjectValue) {
        result = result.filter((c) =>
          c.subject_area.toLowerCase().includes(subjectValue.toLowerCase()),
        );
      }
    }

    if (gradeFilter !== 'All') {
      result = result.filter((c) => c.grade_level === gradeFilter);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (c) =>
          c.course_code.toLowerCase().includes(q) ||
          c.course_name.toLowerCase().includes(q),
      );
    }

    setFilteredCatalog(result);
  }, [catalog, activeSubject, gradeFilter, searchQuery]);

  // ── Debounced search ───────────────────────────────────────────────────────
  const handleSearchChange = useCallback((value: string) => {
    if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
    searchDebounceRef.current = setTimeout(() => {
      setSearchQuery(value);
    }, 300);
  }, []);

  // ── Plan name inline edit ──────────────────────────────────────────────────
  const handlePlanNameSave = useCallback(async () => {
    setEditingPlanName(false);
    if (!activePlan || planName === activePlan.plan_name) return;
    // Optimistic update — backend update not yet specced; just update local state
    setActivePlan((prev) => prev ? { ...prev, plan_name: planName } : prev);
  }, [activePlan, planName]);

  // ── Create plan ────────────────────────────────────────────────────────────
  const handleCreatePlan = useCallback(
    async (name: string, boardId: number) => {
      try {
        setCreatingPlan(true);
        const plan = await academicPlanApi.createPlan({
          plan_name: name,
          board_id: boardId,
        });
        setPlans((prev) => [plan, ...prev]);
        setActivePlan(plan);
        setPlanName(plan.plan_name);
        setSelectedBoardId(plan.board_id);
      } catch {
        setError('Failed to create plan. Please try again.');
      } finally {
        setCreatingPlan(false);
      }
    },
    [],
  );

  // ── Add course ─────────────────────────────────────────────────────────────
  const handleAddCourse = useCallback(
    async (course: CourseCatalogItem, grade: Grade, semester: Semester) => {
      if (!activePlan) return;

      // Optimistic UI: create a temporary PlanCourse
      const tempCourse: PlanCourse = {
        id: -Date.now(), // temporary negative id
        course_code: course.course_code,
        course_name: course.course_name,
        grade_level: grade,
        semester,
        credits: course.credits,
        pathway: course.pathway,
        subject_area: course.subject_area,
        prerequisites: course.prerequisites,
        has_prerequisite_warning: false,
      };

      setActivePlan((prev) => {
        if (!prev) return prev;
        // Prevent duplicates
        if (prev.courses.some((c) => c.course_code === course.course_code && c.grade_level === grade && c.semester === semester)) {
          return prev;
        }
        const newCourses = [...prev.courses, tempCourse];
        return {
          ...prev,
          courses: newCourses,
          total_credits: prev.total_credits + course.credits,
        };
      });

      try {
        const added = await academicPlanApi.addCourse(activePlan.id, {
          course_code: course.course_code,
          grade_level: grade,
          semester,
        });
        // Replace temp with real
        setActivePlan((prev) => {
          if (!prev) return prev;
          const courses = prev.courses.map((c) =>
            c.id === tempCourse.id ? added : c,
          );
          return { ...prev, courses };
        });
      } catch {
        // Revert optimistic update
        setActivePlan((prev) => {
          if (!prev) return prev;
          const courses = prev.courses.filter((c) => c.id !== tempCourse.id);
          return {
            ...prev,
            courses,
            total_credits: prev.total_credits - course.credits,
          };
        });
        setError('Failed to add course. Please try again.');
      }
    },
    [activePlan],
  );

  // ── Remove course ──────────────────────────────────────────────────────────
  const handleRemoveCourse = useCallback(
    async (planCourseId: number) => {
      if (!activePlan) return;

      const removed = activePlan.courses.find((c) => c.id === planCourseId);
      if (!removed) return;

      // Optimistic remove
      setActivePlan((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          courses: prev.courses.filter((c) => c.id !== planCourseId),
          total_credits: Math.max(0, prev.total_credits - removed.credits),
        };
      });

      try {
        await academicPlanApi.removeCourse(activePlan.id, planCourseId);
      } catch {
        // Revert
        setActivePlan((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            courses: [...prev.courses, removed],
            total_credits: prev.total_credits + removed.credits,
          };
        });
        setError('Failed to remove course. Please try again.');
      }
    },
    [activePlan],
  );

  // ── Drag-and-drop ──────────────────────────────────────────────────────────
  const handleDragStart = useCallback(
    (e: React.DragEvent, course: CourseCatalogItem) => {
      setDraggedCourse(course);
      e.dataTransfer.effectAllowed = 'copy';
      e.dataTransfer.setData('text/plain', course.course_code);
    },
    [],
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent, cellKey: string) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
      setDragOverCell(cellKey);
    },
    [],
  );

  const handleDragLeave = useCallback(() => {
    setDragOverCell(null);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent, grade: Grade, semester: Semester) => {
      e.preventDefault();
      setDragOverCell(null);
      if (!draggedCourse) return;
      handleAddCourse(draggedCourse, grade, semester);
      setDraggedCourse(null);
    },
    [draggedCourse, handleAddCourse],
  );

  const handleDragEnd = useCallback(() => {
    setDraggedCourse(null);
    setDragOverCell(null);
  }, []);

  // ── Validate plan ──────────────────────────────────────────────────────────
  const handleValidate = useCallback(async () => {
    if (!activePlan) return;
    try {
      setValidating(true);
      const result = await academicPlanApi.validatePlan(activePlan.id);
      setValidationResult(result);
    } catch {
      setError('Failed to validate plan. Please try again.');
    } finally {
      setValidating(false);
    }
  }, [activePlan]);

  // ── Derived state ──────────────────────────────────────────────────────────
  const totalCredits = activePlan?.total_credits ?? 0;
  const creditPercent = Math.min(100, (totalCredits / OSSD_CREDIT_TARGET) * 100);
  const creditBarClass =
    totalCredits >= OSSD_CREDIT_TARGET
      ? 'green'
      : totalCredits >= 20
      ? 'amber'
      : 'red';

  const getCoursesForCell = useCallback(
    (grade: Grade, semester: Semester): PlanCourse[] => {
      if (!activePlan) return [];
      return activePlan.courses.filter(
        (c) => c.grade_level === grade && c.semester === semester,
      );
    },
    [activePlan],
  );

  // Build a simple prerequisite warning map:
  // For each course, check if its prereqs are present in prior grades
  const prerequisiteWarnings = useCallback(
    (course: PlanCourse): boolean => {
      if (!activePlan || !course.prerequisites.length) return false;
      const priorCodes = new Set(
        activePlan.courses
          .filter((c) => c.grade_level < course.grade_level || (c.grade_level === course.grade_level && c.semester < course.semester))
          .map((c) => c.course_code),
      );
      return course.prerequisites.some((prereq) => !priorCodes.has(prereq));
    },
    [activePlan],
  );

  // ── Render ─────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Course Planner">
        <div className="planner-loading">Loading academic planner...</div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout welcomeSubtitle="Course Planner">
      {error && (
        <div className="planner-error-banner">
          {error}
          <button onClick={() => setError(null)}>&times;</button>
        </div>
      )}

      {/* ── Plan header ── */}
      <div className="planner-page-header">
        <div className="planner-plan-title-row">
          {editingPlanName ? (
            <input
              ref={planNameRef}
              className="planner-plan-name-input"
              value={planName}
              onChange={(e) => setPlanName(e.target.value)}
              onBlur={handlePlanNameSave}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handlePlanNameSave();
                if (e.key === 'Escape') {
                  setPlanName(activePlan?.plan_name ?? '');
                  setEditingPlanName(false);
                }
              }}
              autoFocus
            />
          ) : (
            <h1
              className="planner-plan-name"
              onClick={() => activePlan && setEditingPlanName(true)}
              title={activePlan ? 'Click to edit plan name' : ''}
            >
              {planName || 'Academic Plan'}
              {activePlan && <span className="planner-plan-name-edit-hint"> ✏</span>}
            </h1>
          )}

          {plans.length > 1 && (
            <select
              className="planner-plan-select"
              value={activePlan?.id ?? ''}
              onChange={async (e) => {
                const plan = await academicPlanApi.getPlan(Number(e.target.value));
                setActivePlan(plan);
                setPlanName(plan.plan_name);
                setSelectedBoardId(plan.board_id);
              }}
            >
              {plans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.plan_name}
                </option>
              ))}
            </select>
          )}
        </div>

        {activePlan && (
          <div className="planner-header-meta">
            <label className="planner-board-label">Board:</label>
            <select
              className="planner-board-select"
              value={selectedBoardId}
              onChange={(e) => setSelectedBoardId(Number(e.target.value))}
            >
              {boards.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.short_name || b.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* ── No plan state ── */}
      {!activePlan && !loading && (
        <CreatePlanPrompt
          boards={boards}
          onCreate={handleCreatePlan}
          loading={creatingPlan}
        />
      )}

      {/* ── Main 3-column layout ── */}
      {activePlan && (
        <div className="planner-layout">
          {/* ── Left sidebar: Course catalog ── */}
          <aside className="planner-sidebar planner-sidebar-left">
            <div className="catalog-sticky-header">
              <h2 className="catalog-title">Course Catalog</h2>
              <input
                className="catalog-search"
                type="search"
                placeholder="Search courses..."
                onChange={(e) => handleSearchChange(e.target.value)}
                aria-label="Search course catalog"
              />
              <div className="catalog-subject-tabs" role="tablist">
                {SUBJECT_TABS.map((tab) => (
                  <button
                    key={tab}
                    role="tab"
                    aria-selected={activeSubject === tab}
                    className={`catalog-subject-tab${activeSubject === tab ? ' active' : ''}`}
                    onClick={() => setActiveSubject(tab)}
                  >
                    {tab}
                  </button>
                ))}
              </div>
              <div className="catalog-grade-filter">
                {(['All', 9, 10, 11, 12] as const).map((g) => (
                  <button
                    key={g}
                    className={`catalog-grade-btn${gradeFilter === g ? ' active' : ''}`}
                    onClick={() => setGradeFilter(g as Grade | 'All')}
                  >
                    {g === 'All' ? 'All' : `Gr ${g}`}
                  </button>
                ))}
              </div>
            </div>
            <div className="catalog-course-list">
              {filteredCatalog.length === 0 ? (
                <div className="catalog-empty">
                  {catalog.length === 0
                    ? 'Course catalog loading...'
                    : 'No courses match your filters.'}
                </div>
              ) : (
                filteredCatalog.map((course) => (
                  <CatalogCourseCard
                    key={course.id}
                    course={course}
                    onAddClick={setAddModalCourse}
                    onDragStart={handleDragStart}
                  />
                ))
              )}
            </div>
          </aside>

          {/* ── Main grid ── */}
          <main className="planner-grid-area">
            <div className="planner-grid">
              {GRADES.map((grade) => (
                <div key={grade} className="planner-grade-col">
                  <div className="planner-grade-header">Grade {grade}</div>
                  {SEMESTERS.map((semester) => {
                    const cellKey = `${grade}-${semester}`;
                    const cellCourses = getCoursesForCell(grade, semester);
                    const isOver = dragOverCell === cellKey;
                    return (
                      <div
                        key={semester}
                        className={`planner-cell${isOver ? ' drag-over' : ''}`}
                        onDragOver={(e) => handleDragOver(e, cellKey)}
                        onDragLeave={handleDragLeave}
                        onDrop={(e) => handleDrop(e, grade, semester)}
                      >
                        <div className="planner-cell-header">Semester {semester}</div>
                        <div className="planner-cell-courses">
                          {cellCourses.length === 0 && (
                            <div className="planner-cell-empty">
                              Drop courses here
                            </div>
                          )}
                          {cellCourses.map((course) => (
                            <PlanCourseCard
                              key={course.id}
                              course={{
                                ...course,
                                has_prerequisite_warning: prerequisiteWarnings(course),
                              }}
                              onRemove={handleRemoveCourse}
                            />
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </main>

          {/* ── Right sidebar: Summary ── */}
          <aside className="planner-sidebar planner-sidebar-right">
            <h2 className="summary-title">Summary</h2>

            <div className="summary-credits">
              <div className="summary-credits-label">
                <span>Credits</span>
                <span className="summary-credits-count">
                  {totalCredits} / {OSSD_CREDIT_TARGET}
                </span>
              </div>
              <div className="summary-credits-bar-bg">
                <div
                  className={`summary-credits-bar ${creditBarClass}`}
                  style={{ width: `${creditPercent}%` }}
                />
              </div>
            </div>

            <div className="summary-requirements">
              <h3 className="summary-req-title">OSSD Requirements</h3>
              <ul className="summary-req-list">
                <li className={`summary-req-item ${totalCredits >= 30 ? 'fulfilled' : 'missing'}`}>
                  <span className="req-icon">{totalCredits >= 30 ? '✓' : '✗'}</span>
                  <span>30 total credits</span>
                </li>
                <li className={`summary-req-item ${activePlan.courses.some(c => c.subject_area.toLowerCase().includes('english')) ? 'fulfilled' : 'missing'}`}>
                  <span className="req-icon">{activePlan.courses.some(c => c.subject_area.toLowerCase().includes('english')) ? '✓' : '✗'}</span>
                  <span>English (all grades)</span>
                </li>
                <li className={`summary-req-item ${activePlan.courses.some(c => c.subject_area.toLowerCase().includes('math')) ? 'fulfilled' : 'missing'}`}>
                  <span className="req-icon">{activePlan.courses.some(c => c.subject_area.toLowerCase().includes('math')) ? '✓' : '✗'}</span>
                  <span>Math (Gr 11 or 12)</span>
                </li>
                <li className={`summary-req-item ${activePlan.courses.some(c => c.subject_area.toLowerCase().includes('science')) ? 'fulfilled' : 'missing'}`}>
                  <span className="req-icon">{activePlan.courses.some(c => c.subject_area.toLowerCase().includes('science')) ? '✓' : '✗'}</span>
                  <span>Science</span>
                </li>
                <li className={`summary-req-item ${activePlan.courses.some(c => c.subject_area.toLowerCase().includes('canadian')) ? 'fulfilled' : 'missing'}`}>
                  <span className="req-icon">{activePlan.courses.some(c => c.subject_area.toLowerCase().includes('canadian')) ? '✓' : '✗'}</span>
                  <span>Canadian History / Geography</span>
                </li>
                <li className={`summary-req-item ${activePlan.courses.some(c => ['arts', 'music', 'drama', 'visual'].some(k => c.subject_area.toLowerCase().includes(k))) ? 'fulfilled' : 'missing'}`}>
                  <span className="req-icon">{activePlan.courses.some(c => ['arts', 'music', 'drama', 'visual'].some(k => c.subject_area.toLowerCase().includes(k))) ? '✓' : '✗'}</span>
                  <span>Arts</span>
                </li>
                <li className={`summary-req-item ${activePlan.courses.some(c => c.subject_area.toLowerCase().includes('health') || c.subject_area.toLowerCase().includes('phys')) ? 'fulfilled' : 'missing'}`}>
                  <span className="req-icon">{activePlan.courses.some(c => c.subject_area.toLowerCase().includes('health') || c.subject_area.toLowerCase().includes('phys')) ? '✓' : '✗'}</span>
                  <span>Health &amp; Phys Ed</span>
                </li>
                <li className={`summary-req-item ${activePlan.courses.some(c => c.subject_area.toLowerCase().includes('civics') || c.subject_area.toLowerCase().includes('career')) ? 'fulfilled' : 'missing'}`}>
                  <span className="req-icon">{activePlan.courses.some(c => c.subject_area.toLowerCase().includes('civics') || c.subject_area.toLowerCase().includes('career')) ? '✓' : '✗'}</span>
                  <span>Civics &amp; Career Studies</span>
                </li>
              </ul>
            </div>

            <button
              className="validate-plan-btn"
              onClick={handleValidate}
              disabled={validating}
            >
              {validating ? 'Validating...' : 'Validate Plan'}
            </button>
          </aside>
        </div>
      )}

      {/* ── Add course modal ── */}
      {addModalCourse && (
        <AddCourseModal
          course={addModalCourse}
          onClose={() => setAddModalCourse(null)}
          onConfirm={(grade, semester) => {
            handleAddCourse(addModalCourse, grade, semester);
            setAddModalCourse(null);
          }}
        />
      )}

      {/* ── Validation result modal ── */}
      {validationResult && (
        <ValidationModal
          result={validationResult}
          onClose={() => setValidationResult(null)}
        />
      )}
    </DashboardLayout>
  );
}
