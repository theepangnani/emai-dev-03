import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../../components/DashboardLayout';
import { parentApi } from '../../api/parent';
import { parentAIApi } from '../../api/parentAI';
import type { ChildSummary, ChildHighlight } from '../../api/parent';
import type { WeakSpotsResponse, ReadinessCheckResponse, PracticeProblemsResponse } from '../../api/parentAI';
import { PageSkeleton } from '../../components/Skeleton';
import './ParentAITools.css';

type CourseOption = { id: number; name: string };
type AssignmentOption = { id: number; title: string; course_id: number };

export function ParentAITools() {
  const navigate = useNavigate();
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [childHighlights, setChildHighlights] = useState<ChildHighlight[]>([]);
  const [allAssignments, setAllAssignments] = useState<AssignmentOption[]>([]);
  const [loading, setLoading] = useState(true);

  // Tool states
  const [openTool, setOpenTool] = useState<'weak-spots' | 'readiness' | 'practice' | null>(null);

  // Weak spots
  const [wsChildId, setWsChildId] = useState<number | ''>('');
  const [wsCourseId, setWsCourseId] = useState<number | ''>('');
  const [wsLoading, setWsLoading] = useState(false);
  const [wsResult, setWsResult] = useState<WeakSpotsResponse | null>(null);
  const [wsError, setWsError] = useState<string | null>(null);

  // Readiness
  const [rcChildId, setRcChildId] = useState<number | ''>('');
  const [rcAssignmentId, setRcAssignmentId] = useState<number | ''>('');
  const [rcLoading, setRcLoading] = useState(false);
  const [rcResult, setRcResult] = useState<ReadinessCheckResponse | null>(null);
  const [rcError, setRcError] = useState<string | null>(null);

  // Practice problems
  const [ppChildId, setPpChildId] = useState<number | ''>('');
  const [ppCourseId, setPpCourseId] = useState<number | ''>('');
  const [ppTopic, setPpTopic] = useState('');
  const [ppLoading, setPpLoading] = useState(false);
  const [ppResult, setPpResult] = useState<PracticeProblemsResponse | null>(null);
  const [ppError, setPpError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const dash = await parentApi.getDashboard();
        setChildren(dash.children);
        setChildHighlights(dash.child_highlights);
        setAllAssignments(dash.all_assignments.map(a => ({ id: a.id, title: a.title, course_id: a.course_id })));
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const getCoursesForChild = useCallback((studentId: number): CourseOption[] => {
    const hl = childHighlights.find(c => c.student_id === studentId);
    return hl?.courses.map(c => ({ id: c.id, name: c.name })) ?? [];
  }, [childHighlights]);

  const getAssignmentsForChild = useCallback((studentId: number): AssignmentOption[] => {
    const hl = childHighlights.find(c => c.student_id === studentId);
    if (!hl) return [];
    const courseIds = new Set(hl.courses.map(c => c.id));
    return allAssignments.filter(a => courseIds.has(a.course_id));
  }, [childHighlights, allAssignments]);

  // Handlers
  const runWeakSpots = async () => {
    if (!wsChildId) return;
    setWsLoading(true);
    setWsError(null);
    setWsResult(null);
    try {
      const { data } = await parentAIApi.getWeakSpots(wsChildId as number, wsCourseId || undefined);
      setWsResult(data);
    } catch (err: any) {
      setWsError(err.response?.data?.detail || 'Failed to analyze weak spots.');
    } finally {
      setWsLoading(false);
    }
  };

  const runReadiness = async () => {
    if (!rcChildId || !rcAssignmentId) return;
    setRcLoading(true);
    setRcError(null);
    setRcResult(null);
    try {
      const { data } = await parentAIApi.checkReadiness(rcChildId as number, rcAssignmentId as number);
      setRcResult(data);
    } catch (err: any) {
      setRcError(err.response?.data?.detail || 'Failed to check readiness.');
    } finally {
      setRcLoading(false);
    }
  };

  const runPractice = async () => {
    if (!ppChildId || !ppCourseId || !ppTopic.trim()) return;
    setPpLoading(true);
    setPpError(null);
    setPpResult(null);
    try {
      const { data } = await parentAIApi.generatePracticeProblems(ppChildId as number, ppCourseId as number, ppTopic.trim());
      setPpResult(data);
    } catch (err: any) {
      setPpError(err.response?.data?.detail || 'Failed to generate practice problems.');
    } finally {
      setPpLoading(false);
    }
  };

  const severityColor = (s: string) => {
    if (s === 'high') return 'pai-severity-high';
    if (s === 'medium') return 'pai-severity-medium';
    return 'pai-severity-low';
  };

  const readinessStatusIcon = (s: string) => {
    if (s === 'done') return '\u2705';
    if (s === 'partial') return '\u26A0\uFE0F';
    return '\u274C';
  };

  if (loading) {
    return (
      <DashboardLayout>
        <PageSkeleton />
      </DashboardLayout>
    );
  }

  if (children.length === 0) {
    return (
      <DashboardLayout>
        <div className="pai-empty">
          <h2>No children linked</h2>
          <p>Link a child from the My Kids page to use AI tools.</p>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="pai-container">
        <div className="pai-header">
          <h1>Responsible AI Tools</h1>
          <p className="pai-subtitle">Understand your child's progress and help them learn — without shortcuts.</p>
        </div>

        <div className="pai-cards">
          {/* Weak Spots Card */}
          <div className={`pai-card ${openTool === 'weak-spots' ? 'pai-card-open' : ''}`}>
            <button className="pai-card-header" onClick={() => setOpenTool(openTool === 'weak-spots' ? null : 'weak-spots')}>
              <div className="pai-card-icon">&#x1F50D;</div>
              <div className="pai-card-info">
                <h3>Weak Spots Analysis</h3>
                <p>Identify topics where your child is struggling based on quiz and grade data.</p>
              </div>
              <span className="pai-card-toggle">{openTool === 'weak-spots' ? '\u25B2' : '\u25BC'}</span>
            </button>
            {openTool === 'weak-spots' && (
              <div className="pai-card-body">
                <div className="pai-form">
                  <label>
                    Child
                    <select value={wsChildId} onChange={e => { setWsChildId(Number(e.target.value) || ''); setWsCourseId(''); setWsResult(null); }}>
                      <option value="">Select child...</option>
                      {children.map(c => <option key={c.student_id} value={c.student_id}>{c.full_name}</option>)}
                    </select>
                  </label>
                  {wsChildId && (
                    <label>
                      Course (optional)
                      <select value={wsCourseId} onChange={e => setWsCourseId(Number(e.target.value) || '')}>
                        <option value="">All courses</option>
                        {getCoursesForChild(wsChildId as number).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                      </select>
                    </label>
                  )}
                  <button className="pai-btn" onClick={runWeakSpots} disabled={!wsChildId || wsLoading}>
                    {wsLoading ? 'Analyzing...' : 'Analyze Weak Spots'}
                  </button>
                </div>
                {wsError && <div className="pai-error">{wsError}</div>}
                {wsResult && (
                  <div className="pai-results">
                    <p className="pai-summary">{wsResult.summary}</p>
                    <p className="pai-meta">Quizzes analyzed: {wsResult.total_quizzes_analyzed} | Assignments analyzed: {wsResult.total_assignments_analyzed}</p>
                    {wsResult.weak_spots.length > 0 ? (
                      <div className="pai-ws-list">
                        {wsResult.weak_spots.map((ws, i) => (
                          <div key={i} className={`pai-ws-item ${severityColor(ws.severity)}`}>
                            <div className="pai-ws-header">
                              <strong>{ws.topic}</strong>
                              <span className={`pai-badge ${severityColor(ws.severity)}`}>{ws.severity}</span>
                            </div>
                            <p>{ws.detail}</p>
                            {ws.quiz_score_summary && <p className="pai-ws-score">{ws.quiz_score_summary}</p>}
                            <p className="pai-ws-action"><strong>Suggested:</strong> {ws.suggested_action}</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="pai-success">No weak spots found — great job!</p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Readiness Check Card */}
          <div className={`pai-card ${openTool === 'readiness' ? 'pai-card-open' : ''}`}>
            <button className="pai-card-header" onClick={() => setOpenTool(openTool === 'readiness' ? null : 'readiness')}>
              <div className="pai-card-icon">&#x1F4CA;</div>
              <div className="pai-card-info">
                <h3>Readiness Check</h3>
                <p>See if your child has studied enough for a specific assignment or test.</p>
              </div>
              <span className="pai-card-toggle">{openTool === 'readiness' ? '\u25B2' : '\u25BC'}</span>
            </button>
            {openTool === 'readiness' && (
              <div className="pai-card-body">
                <div className="pai-form">
                  <label>
                    Child
                    <select value={rcChildId} onChange={e => { setRcChildId(Number(e.target.value) || ''); setRcAssignmentId(''); setRcResult(null); }}>
                      <option value="">Select child...</option>
                      {children.map(c => <option key={c.student_id} value={c.student_id}>{c.full_name}</option>)}
                    </select>
                  </label>
                  {rcChildId && (
                    <label>
                      Assignment
                      <select value={rcAssignmentId} onChange={e => setRcAssignmentId(Number(e.target.value) || '')}>
                        <option value="">Select assignment...</option>
                        {getAssignmentsForChild(rcChildId as number).map(a => <option key={a.id} value={a.id}>{a.title}</option>)}
                      </select>
                    </label>
                  )}
                  <button className="pai-btn" onClick={runReadiness} disabled={!rcChildId || !rcAssignmentId || rcLoading}>
                    {rcLoading ? 'Checking...' : 'Check Readiness'}
                  </button>
                </div>
                {rcError && <div className="pai-error">{rcError}</div>}
                {rcResult && (
                  <div className="pai-results">
                    <div className="pai-readiness-meter">
                      <div className="pai-readiness-label">
                        <strong>{rcResult.assignment_title}</strong>
                        <span className="pai-meta">{rcResult.course_name}</span>
                      </div>
                      <div className="pai-readiness-bar">
                        {[1,2,3,4,5].map(n => (
                          <div key={n} className={`pai-readiness-dot ${n <= rcResult.readiness_score ? 'pai-readiness-filled' : ''}`} />
                        ))}
                      </div>
                      <p className="pai-readiness-score">Readiness: {rcResult.readiness_score}/5</p>
                    </div>
                    <p className="pai-summary">{rcResult.summary}</p>
                    <div className="pai-checklist">
                      {rcResult.items.map((item, i) => (
                        <div key={i} className="pai-check-item">
                          <span className="pai-check-icon">{readinessStatusIcon(item.status)}</span>
                          <div>
                            <strong>{item.label}</strong>
                            {item.detail && <p className="pai-check-detail">{item.detail}</p>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Practice Problems Card */}
          <div className={`pai-card ${openTool === 'practice' ? 'pai-card-open' : ''}`}>
            <button className="pai-card-header" onClick={() => setOpenTool(openTool === 'practice' ? null : 'practice')}>
              <div className="pai-card-icon">&#x270F;&#xFE0F;</div>
              <div className="pai-card-info">
                <h3>Practice Problems</h3>
                <p>Generate practice problems for your child — problems only, no answers given.</p>
              </div>
              <span className="pai-card-toggle">{openTool === 'practice' ? '\u25B2' : '\u25BC'}</span>
            </button>
            {openTool === 'practice' && (
              <div className="pai-card-body">
                <div className="pai-form">
                  <label>
                    Child
                    <select value={ppChildId} onChange={e => { setPpChildId(Number(e.target.value) || ''); setPpCourseId(''); setPpResult(null); }}>
                      <option value="">Select child...</option>
                      {children.map(c => <option key={c.student_id} value={c.student_id}>{c.full_name}</option>)}
                    </select>
                  </label>
                  {ppChildId && (
                    <label>
                      Course
                      <select value={ppCourseId} onChange={e => setPpCourseId(Number(e.target.value) || '')}>
                        <option value="">Select course...</option>
                        {getCoursesForChild(ppChildId as number).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                      </select>
                    </label>
                  )}
                  {ppCourseId && (
                    <label>
                      Topic
                      <input
                        type="text"
                        value={ppTopic}
                        onChange={e => setPpTopic(e.target.value)}
                        placeholder="e.g. Fractions, Photosynthesis, WW2..."
                        maxLength={500}
                      />
                    </label>
                  )}
                  <button className="pai-btn" onClick={runPractice} disabled={!ppChildId || !ppCourseId || !ppTopic.trim() || ppLoading}>
                    {ppLoading ? 'Generating...' : 'Generate Practice Problems'}
                  </button>
                </div>
                {ppError && <div className="pai-error">{ppError}</div>}
                {ppResult && (
                  <div className="pai-results">
                    <p className="pai-summary"><strong>{ppResult.topic}</strong> — {ppResult.course_name}</p>
                    <p className="pai-instructions">{ppResult.instructions}</p>
                    <div className="pai-problems">
                      {ppResult.problems.map(p => (
                        <div key={p.number} className="pai-problem">
                          <div className="pai-problem-num">{p.number}</div>
                          <div className="pai-problem-body">
                            <p>{p.question}</p>
                            {p.hint && <p className="pai-hint"><strong>Hint:</strong> {p.hint}</p>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Report Card Analysis Card */}
          <div className="pai-card">
            <button className="pai-card-header" onClick={() => navigate('/school-report-cards')}>
              <div className="pai-card-icon">&#x1F4CB;</div>
              <div className="pai-card-info">
                <h3>Report Card Analysis</h3>
                <p>Upload school report cards and get AI-powered analysis with career path suggestions.</p>
              </div>
              <span className="pai-card-toggle">&#x2192;</span>
            </button>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
