import { useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { useToast } from '../components/Toast';
import {
  recommendationsApi,
  ONTARIO_PROGRAMS,
  type GoalPathway,
  type RecommendationItem,
  type PathwayProgramResult,
  type RecommendationsResponse,
  type UniversityPathwaysResponse,
} from '../api/recommendations';
import './AIRecommendationsPage.css';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const GOAL_OPTIONS: { value: GoalPathway; label: string; description: string; icon: string }[] = [
  {
    value: 'university',
    label: 'University',
    description: 'Aim for degree programs at Ontario universities',
    icon: '🎓',
  },
  {
    value: 'college',
    label: 'College',
    description: 'Diploma and certificate programs at Ontario colleges',
    icon: '📚',
  },
  {
    value: 'workplace',
    label: 'Workplace',
    description: 'Enter the workforce directly after high school',
    icon: '💼',
  },
  {
    value: 'undecided',
    label: 'Undecided',
    description: 'Keep all options open with a balanced course selection',
    icon: '🔭',
  },
];

const INTEREST_OPTIONS = [
  'Sciences',
  'Mathematics',
  'Arts',
  'Technology',
  'Business',
  'Health',
  'Social Sciences',
  'Languages',
  'Trades',
] as const;

const PRIORITY_CONFIG: Record<
  string,
  { label: string; className: string }
> = {
  high: { label: 'High Priority', className: 'badge-high' },
  medium: { label: 'Medium', className: 'badge-medium' },
  low: { label: 'Low', className: 'badge-low' },
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ReadinessBar({ pct }: { pct: number }) {
  const colorClass =
    pct >= 80 ? 'readiness-high' : pct >= 50 ? 'readiness-medium' : 'readiness-low';
  return (
    <div className="readiness-bar-wrap">
      <div className="readiness-bar-bg">
        <div
          className={`readiness-bar-fill ${colorClass}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`readiness-pct ${colorClass}`}>{pct.toFixed(0)}%</span>
    </div>
  );
}

function CourseChip({
  code,
  variant,
}: {
  code: string;
  variant: 'covered' | 'missing' | 'recommended';
}) {
  return <span className={`course-chip course-chip-${variant}`}>{code}</span>;
}

function RecommendationCard({
  rec,
  onAddToPlan,
  addingCode,
}: {
  rec: RecommendationItem;
  onAddToPlan?: (code: string, name: string, gradeLevel: number) => void;
  addingCode: string | null;
}) {
  const priority = PRIORITY_CONFIG[rec.priority] ?? PRIORITY_CONFIG.medium;
  return (
    <div className="rec-card">
      <div className="rec-card-header">
        <div className="rec-card-title-group">
          <span className="rec-course-code">{rec.course_code}</span>
          <span className="rec-course-name">{rec.course_name}</span>
          <span className="rec-grade-badge">Grade {rec.grade_level}</span>
        </div>
        <span className={`rec-priority-badge ${priority.className}`}>{priority.label}</span>
      </div>
      <p className="rec-reason">{rec.reason}</p>
      {onAddToPlan && (
        <button
          className="btn-add-to-plan"
          disabled={addingCode === rec.course_code}
          onClick={() => onAddToPlan(rec.course_code, rec.course_name, rec.grade_level)}
        >
          {addingCode === rec.course_code ? 'Adding…' : '+ Add to Plan'}
        </button>
      )}
    </div>
  );
}

function PathwayTab({
  program,
}: {
  program: PathwayProgramResult;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`pathway-tab ${expanded ? 'expanded' : ''}`}>
      <button className="pathway-tab-header" onClick={() => setExpanded((e) => !e)}>
        <span className="pathway-program-name">{program.name}</span>
        <ReadinessBar pct={program.readiness_pct} />
        <span className="pathway-chevron">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className="pathway-tab-body">
          {program.universities.length > 0 && (
            <p className="pathway-universities">
              <strong>Universities:</strong> {program.universities.join(', ')}
            </p>
          )}
          {program.min_average != null && (
            <p className="pathway-min-avg">
              <strong>Typical minimum average:</strong> {program.min_average}%
            </p>
          )}

          <div className="pathway-courses-section">
            <div className="pathway-courses-group">
              <h4>Required Courses</h4>
              <div className="course-chips">
                {program.required_courses.map((code) => (
                  <CourseChip
                    key={code}
                    code={code}
                    variant={program.covered.includes(code) ? 'covered' : 'missing'}
                  />
                ))}
              </div>
            </div>

            {program.recommended_courses.length > 0 && (
              <div className="pathway-courses-group">
                <h4>Recommended Courses</h4>
                <div className="course-chips">
                  {program.recommended_courses.map((code) => (
                    <CourseChip
                      key={code}
                      code={code}
                      variant={program.recommended_covered.includes(code) ? 'covered' : 'recommended'}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>

          {program.missing.length > 0 && (
            <div className="pathway-missing-alert">
              <strong>Missing:</strong> {program.missing.join(', ')}
            </div>
          )}

          <p className="pathway-notes">{program.notes}</p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function AIRecommendationsPage() {
  const [searchParams] = useSearchParams();
  const { showToast } = useToast();

  // Form state
  const planId = parseInt(searchParams.get('plan_id') ?? '0', 10) || null;
  const [goal, setGoal] = useState<GoalPathway>('university');
  const [selectedInterests, setSelectedInterests] = useState<string[]>([]);
  const [selectedPrograms, setSelectedPrograms] = useState<string[]>([]);
  const [programSearch, setProgramSearch] = useState('');

  // Results state
  const [loading, setLoading] = useState(false);
  const [recommendations, setRecommendations] = useState<RecommendationsResponse | null>(null);
  const [pathways, setPathways] = useState<UniversityPathwaysResponse | null>(null);
  const [pathwaysLoading, setPathwaysLoading] = useState(false);
  const [addingCode, setAddingCode] = useState<string | null>(null);

  // UI state
  const [activeSection, setActiveSection] = useState<'recommendations' | 'pathways'>('recommendations');

  const toggleInterest = useCallback((interest: string) => {
    setSelectedInterests((prev) =>
      prev.includes(interest) ? prev.filter((i) => i !== interest) : [...prev, interest],
    );
  }, []);

  const toggleProgram = useCallback((program: string) => {
    setSelectedPrograms((prev) =>
      prev.includes(program) ? prev.filter((p) => p !== program) : [...prev, program],
    );
  }, []);

  const handleGetRecommendations = useCallback(async () => {
    if (!planId) {
      showToast('No plan selected. Please open this page from your Academic Plan.', 'error');
      return;
    }

    setLoading(true);
    try {
      const result = await recommendationsApi.generateCourseRecommendations({
        plan_id: planId,
        goal,
        interests: selectedInterests,
        target_programs: selectedPrograms.length > 0 ? selectedPrograms : undefined,
      });
      setRecommendations(result);
      setActiveSection('recommendations');
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Failed to generate recommendations. Please try again.';
      showToast(msg, 'error');
    } finally {
      setLoading(false);
    }
  }, [planId, goal, selectedInterests, selectedPrograms, showToast]);

  const handleCheckPathways = useCallback(async () => {
    if (!planId) {
      showToast('No plan selected. Please open this page from your Academic Plan.', 'error');
      return;
    }

    setPathwaysLoading(true);
    try {
      const result = await recommendationsApi.getUniversityPathways(
        planId,
        selectedPrograms.length > 0 ? selectedPrograms : undefined,
      );
      setPathways(result);
      setActiveSection('pathways');
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Failed to load pathway analysis.';
      showToast(msg, 'error');
    } finally {
      setPathwaysLoading(false);
    }
  }, [planId, selectedPrograms, showToast]);

  const handleAddToPlan = useCallback(
    async (courseCode: string, courseName: string, gradeLevel: number) => {
      if (!planId) return;
      setAddingCode(courseCode);
      try {
        await import('../api/client').then(({ api }) =>
          api.post(`/api/academic-plans/${planId}/courses`, {
            course_code: courseCode,
            course_name: courseName,
            grade_level: gradeLevel,
            semester: 1,
          }),
        );
        showToast(`${courseCode} added to your plan!`, 'success');
      } catch (err: unknown) {
        const msg =
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          'Failed to add course to plan.';
        showToast(msg, 'error');
      } finally {
        setAddingCode(null);
      }
    },
    [planId, showToast],
  );

  const filteredPrograms = ONTARIO_PROGRAMS.filter((p) =>
    p.toLowerCase().includes(programSearch.toLowerCase()),
  );

  return (
    <DashboardLayout>
      <div className="ai-rec-page">
        <header className="ai-rec-header">
          <h1>AI Course Recommendations</h1>
          <p className="ai-rec-subtitle">
            Get personalized course suggestions and check your readiness for Ontario university programs.
          </p>
          {!planId && (
            <div className="ai-rec-no-plan-warning">
              No academic plan selected. Open this page from your Academic Planner to enable course
              recommendations.
            </div>
          )}
        </header>

        {/* ---- Configuration panel ---- */}
        <section className="ai-rec-config">
          {/* Goal selector */}
          <div className="config-section">
            <h2>1. What is your goal pathway?</h2>
            <div className="goal-cards">
              {GOAL_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  className={`goal-card ${goal === opt.value ? 'selected' : ''}`}
                  onClick={() => setGoal(opt.value)}
                >
                  <span className="goal-icon">{opt.icon}</span>
                  <span className="goal-label">{opt.label}</span>
                  <span className="goal-description">{opt.description}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Interests */}
          <div className="config-section">
            <h2>2. Select your interests</h2>
            <div className="interest-chips">
              {INTEREST_OPTIONS.map((interest) => (
                <button
                  key={interest}
                  className={`interest-chip ${selectedInterests.includes(interest) ? 'selected' : ''}`}
                  onClick={() => toggleInterest(interest)}
                >
                  {interest}
                </button>
              ))}
            </div>
          </div>

          {/* Target programs */}
          <div className="config-section">
            <h2>3. Target university programs (optional)</h2>
            <input
              className="program-search-input"
              type="text"
              placeholder="Search programs..."
              value={programSearch}
              onChange={(e) => setProgramSearch(e.target.value)}
            />
            <div className="program-chips">
              {filteredPrograms.map((prog) => (
                <button
                  key={prog}
                  className={`interest-chip ${selectedPrograms.includes(prog) ? 'selected' : ''}`}
                  onClick={() => toggleProgram(prog)}
                >
                  {prog}
                </button>
              ))}
            </div>
          </div>

          {/* Action buttons */}
          <div className="ai-rec-actions">
            <button
              className="btn-primary"
              onClick={handleGetRecommendations}
              disabled={loading || !planId}
            >
              {loading ? (
                <span className="btn-loading">
                  <span className="spinner" />
                  Generating…
                </span>
              ) : (
                'Get Recommendations'
              )}
            </button>
            <button
              className="btn-secondary"
              onClick={handleCheckPathways}
              disabled={pathwaysLoading || !planId}
            >
              {pathwaysLoading ? (
                <span className="btn-loading">
                  <span className="spinner" />
                  Analysing…
                </span>
              ) : (
                'Check University Pathways'
              )}
            </button>
          </div>
        </section>

        {/* ---- Results ---- */}
        {(recommendations || pathways) && (
          <section className="ai-rec-results">
            <div className="results-tabs">
              <button
                className={`results-tab-btn ${activeSection === 'recommendations' ? 'active' : ''}`}
                onClick={() => setActiveSection('recommendations')}
                disabled={!recommendations}
              >
                Course Recommendations
              </button>
              <button
                className={`results-tab-btn ${activeSection === 'pathways' ? 'active' : ''}`}
                onClick={() => setActiveSection('pathways')}
                disabled={!pathways}
              >
                University Pathways
              </button>
            </div>

            {/* Recommendations panel */}
            {activeSection === 'recommendations' && recommendations && (
              <div className="results-panel">
                {recommendations.cached && (
                  <p className="cached-notice">
                    Showing cached results from {new Date(recommendations.generated_at).toLocaleString()}
                  </p>
                )}

                {recommendations.overall_advice && (
                  <div className="overall-advice">
                    <h3>Guidance Counselor Advice</h3>
                    <p>{recommendations.overall_advice}</p>
                  </div>
                )}

                <h3>Recommended Courses ({recommendations.recommendations.length})</h3>
                <div className="rec-cards-grid">
                  {recommendations.recommendations.map((rec) => (
                    <RecommendationCard
                      key={rec.course_code}
                      rec={rec}
                      onAddToPlan={planId ? handleAddToPlan : undefined}
                      addingCode={addingCode}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Pathways panel */}
            {activeSection === 'pathways' && pathways && (
              <div className="results-panel">
                <p className="pathway-intro">
                  Your plan has been evaluated against {pathways.programs.length} Ontario university
                  program requirements. Green = course covered, red = missing required course,
                  blue = recommended course covered.
                </p>

                <div className="pathway-legend">
                  <CourseChip code="MHF4U" variant="covered" />
                  <span>Covered</span>
                  <CourseChip code="MCV4U" variant="missing" />
                  <span>Missing (required)</span>
                  <CourseChip code="ICS4U" variant="recommended" />
                  <span>Recommended</span>
                </div>

                <div className="pathway-list">
                  {pathways.programs.map((prog) => (
                    <PathwayTab key={prog.name} program={prog} />
                  ))}
                </div>
              </div>
            )}
          </section>
        )}
      </div>
    </DashboardLayout>
  );
}
