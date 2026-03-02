import { useState, useEffect, useRef, useCallback } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageSkeleton } from '../components/Skeleton';
import { useToast } from '../components/Toast';
import { coursesApi } from '../api/courses';
import { gradeEntriesApi } from '../api/gradeEntries';
import type { CourseGradeMatrix, BulkEntryItem, GradeCell } from '../api/gradeEntries';
import './GradeEntryPage.css';

// --- Letter grade color mapping ---

type GradeColor = 'green' | 'blue' | 'amber' | 'red' | 'none';

function gradeColor(letter: string | null): GradeColor {
  if (!letter) return 'none';
  if (letter.startsWith('A')) return 'green';
  if (letter.startsWith('B')) return 'blue';
  if (letter.startsWith('C')) return 'amber';
  return 'red'; // D or F
}

function computeLetter(grade: number | null, maxGrade: number): string | null {
  if (grade === null || grade === undefined || isNaN(grade)) return null;
  const mg = maxGrade > 0 ? maxGrade : 100;
  const pct = (grade / mg) * 100;
  if (pct >= 90) return 'A+';
  if (pct >= 85) return 'A';
  if (pct >= 80) return 'A-';
  if (pct >= 77) return 'B+';
  if (pct >= 73) return 'B';
  if (pct >= 70) return 'B-';
  if (pct >= 67) return 'C+';
  if (pct >= 63) return 'C';
  if (pct >= 60) return 'C-';
  if (pct >= 50) return 'D';
  return 'F';
}

// --- Cell edit state ---

interface CellState {
  grade: string;   // raw input string, empty = no grade
  feedback: string;
  isPublished: boolean;
  dirty: boolean;
}

type GridState = Record<string, Record<string, CellState>>;
// gridState[studentId][colKey] = CellState

interface Course {
  id: number;
  name: string;
}

export function GradeEntryPage() {
  const { toast } = useToast();

  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [matrix, setMatrix] = useState<CourseGradeMatrix | null>(null);
  const [gridState, setGridState] = useState<GridState>({});
  const [expandedFeedback, setExpandedFeedback] = useState<Set<string>>(new Set());

  const [loadingCourses, setLoadingCourses] = useState(true);
  const [loadingMatrix, setLoadingMatrix] = useState(false);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [confirmPublish, setConfirmPublish] = useState(false);

  // Refs for Tab navigation: inputRefs[studentIndex][colIndex]
  const inputRefs = useRef<(HTMLInputElement | null)[][]>([]);

  // Load teacher's courses on mount
  useEffect(() => {
    setLoadingCourses(true);
    coursesApi.teachingList()
      .then((data: Course[]) => {
        setCourses(data || []);
        if (data && data.length > 0) {
          setSelectedCourseId(data[0].id);
        }
      })
      .catch(() => {
        toast('Failed to load courses', 'error');
      })
      .finally(() => setLoadingCourses(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Load matrix when course changes
  useEffect(() => {
    if (!selectedCourseId) return;
    setLoadingMatrix(true);
    setMatrix(null);
    setGridState({});
    gradeEntriesApi.getCourseMatrix(selectedCourseId)
      .then((data) => {
        setMatrix(data);
        // Initialise grid state from existing entries
        const state: GridState = {};
        for (const student of data.students) {
          state[student.student_id] = {};
          for (const asgn of data.assignments) {
            const colKey = String(asgn.id);
            const cell: GradeCell | null = student.grades[colKey] ?? null;
            state[student.student_id][colKey] = {
              grade: cell?.grade != null ? String(cell.grade) : '',
              feedback: cell?.feedback ?? '',
              isPublished: cell?.is_published ?? false,
              dirty: false,
            };
          }
        }
        setGridState(state);
      })
      .catch(() => {
        toast('Failed to load grade matrix', 'error');
      })
      .finally(() => setLoadingMatrix(false));
  }, [selectedCourseId]); // eslint-disable-line react-hooks/exhaustive-deps

  const setCellValue = useCallback((studentId: number, colKey: string, field: keyof CellState, value: string | boolean) => {
    setGridState(prev => ({
      ...prev,
      [studentId]: {
        ...prev[studentId],
        [colKey]: {
          ...prev[studentId]?.[colKey],
          [field]: value,
          dirty: true,
        },
      },
    }));
  }, []);

  const toggleFeedback = useCallback((key: string) => {
    setExpandedFeedback(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  // Tab key: move to next grade input in the grid
  const handleKeyDown = useCallback((
    e: React.KeyboardEvent<HTMLInputElement>,
    studentIndex: number,
    colIndex: number,
  ) => {
    if (e.key !== 'Tab') return;
    e.preventDefault();
    const totalCols = matrix?.assignments.length ?? 0;
    const totalRows = matrix?.students.length ?? 0;

    let nextRow = studentIndex;
    let nextCol = colIndex + 1;
    if (nextCol >= totalCols) {
      nextCol = 0;
      nextRow = studentIndex + 1;
    }
    if (nextRow >= totalRows) {
      nextRow = 0;
    }

    const ref = inputRefs.current[nextRow]?.[nextCol];
    if (ref) {
      ref.focus();
      ref.select();
    }
  }, [matrix]);

  const handleSaveAll = async () => {
    if (!matrix || !selectedCourseId) return;

    const entries: BulkEntryItem[] = [];
    for (const student of matrix.students) {
      const studentState = gridState[student.student_id] ?? {};
      for (const asgn of matrix.assignments) {
        const colKey = String(asgn.id);
        const cell = studentState[colKey];
        if (!cell?.dirty) continue;

        const gradeNum = cell.grade === '' ? null : parseFloat(cell.grade);
        entries.push({
          student_id: student.student_id,
          course_id: selectedCourseId,
          assignment_id: asgn.id,
          grade: gradeNum,
          max_grade: 100,
          feedback: cell.feedback || null,
          is_published: cell.isPublished,
        });
      }
    }

    if (entries.length === 0) {
      toast('No changes to save', 'info');
      return;
    }

    setSaving(true);
    try {
      const result = await gradeEntriesApi.bulkUpsert(entries);
      toast(`Saved ${result.updated + result.created} grade entries`, 'success');

      // Mark all as clean
      setGridState(prev => {
        const next = { ...prev };
        for (const student of matrix.students) {
          if (next[student.student_id]) {
            next[student.student_id] = Object.fromEntries(
              Object.entries(next[student.student_id]).map(([k, v]) => [k, { ...v, dirty: false }])
            );
          }
        }
        return next;
      });

      // Refresh matrix to pick up server-computed letter grades
      const fresh = await gradeEntriesApi.getCourseMatrix(selectedCourseId);
      setMatrix(fresh);
    } catch {
      toast('Failed to save grades', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handlePublish = async () => {
    if (!selectedCourseId) return;
    setPublishing(true);
    setConfirmPublish(false);
    try {
      const result = await gradeEntriesApi.publishCourseGrades(selectedCourseId);
      toast(result.message, 'success');

      // Refresh matrix to reflect published status
      const fresh = await gradeEntriesApi.getCourseMatrix(selectedCourseId);
      setMatrix(fresh);
      // Re-sync isPublished state
      setGridState(prev => {
        const next = { ...prev };
        for (const student of fresh.students) {
          if (next[student.student_id]) {
            for (const asgn of fresh.assignments) {
              const colKey = String(asgn.id);
              const cell = student.grades[colKey];
              if (next[student.student_id][colKey] && cell) {
                next[student.student_id][colKey] = {
                  ...next[student.student_id][colKey],
                  isPublished: cell.is_published,
                };
              }
            }
          }
        }
        return next;
      });
    } catch {
      toast('Failed to publish grades', 'error');
    } finally {
      setPublishing(false);
    }
  };

  const hasDirty = matrix?.students.some(s =>
    Object.values(gridState[s.student_id] ?? {}).some(c => c.dirty)
  ) ?? false;

  if (loadingCourses) {
    return (
      <DashboardLayout welcomeSubtitle="Grade Entry">
        <PageSkeleton />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout welcomeSubtitle="Enter grades and feedback for your students">
      <div className="gep-container">
        <div className="gep-header">
          <div className="gep-header-left">
            <h1 className="gep-title">Grade Entry</h1>
            <p className="gep-subtitle">Spreadsheet-style bulk grading per student per assignment</p>
          </div>
          <div className="gep-header-actions">
            <button
              className="gep-btn gep-btn--primary"
              onClick={handleSaveAll}
              disabled={saving || !hasDirty}
              aria-busy={saving}
            >
              {saving ? 'Saving...' : 'Save All'}
            </button>
            <button
              className="gep-btn gep-btn--publish"
              onClick={() => setConfirmPublish(true)}
              disabled={publishing || !matrix}
            >
              {publishing ? 'Publishing...' : 'Publish Grades'}
            </button>
          </div>
        </div>

        {/* Course selector */}
        <div className="gep-course-selector">
          <label htmlFor="course-select" className="gep-course-label">Course:</label>
          <select
            id="course-select"
            className="gep-course-select"
            value={selectedCourseId ?? ''}
            onChange={e => setSelectedCourseId(Number(e.target.value))}
          >
            {courses.length === 0 && <option value="">No courses found</option>}
            {courses.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>

        {/* Publish confirmation dialog */}
        {confirmPublish && (
          <div className="gep-confirm-overlay" role="dialog" aria-modal="true" aria-label="Confirm publish">
            <div className="gep-confirm-box">
              <h3>Publish Grades</h3>
              <p>This will make all draft grades for <strong>{matrix?.course_name}</strong> visible to students and parents. Are you sure?</p>
              <div className="gep-confirm-actions">
                <button className="gep-btn gep-btn--publish" onClick={handlePublish}>
                  Yes, Publish
                </button>
                <button className="gep-btn gep-btn--cancel" onClick={() => setConfirmPublish(false)}>
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {loadingMatrix ? (
          <PageSkeleton />
        ) : !matrix ? (
          <div className="gep-empty">
            <p>Select a course above to start entering grades.</p>
          </div>
        ) : matrix.students.length === 0 ? (
          <div className="gep-empty">
            <p>No students enrolled in <strong>{matrix.course_name}</strong> yet.</p>
          </div>
        ) : matrix.assignments.length === 0 ? (
          <div className="gep-empty">
            <p>No assignments found for <strong>{matrix.course_name}</strong>. Create assignments first.</p>
          </div>
        ) : (
          <div className="gep-table-wrapper" role="region" aria-label="Grade entry spreadsheet">
            <table className="gep-table">
              <thead>
                <tr>
                  <th className="gep-th gep-th--student">Student</th>
                  {matrix.assignments.map(asgn => (
                    <th key={asgn.id} className="gep-th gep-th--assignment" title={asgn.due_date ?? undefined}>
                      <span className="gep-asgn-title">{asgn.title}</span>
                      {asgn.due_date && (
                        <span className="gep-asgn-due">
                          {new Date(asgn.due_date).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                        </span>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {matrix.students.map((student, si) => {
                  // Ensure ref row exists
                  if (!inputRefs.current[si]) inputRefs.current[si] = [];
                  return (
                    <tr key={student.student_id} className="gep-tr">
                      <td className="gep-td gep-td--student">
                        <span className="gep-student-name">{student.student_name}</span>
                      </td>
                      {matrix.assignments.map((asgn, ci) => {
                        const colKey = String(asgn.id);
                        const cell = gridState[student.student_id]?.[colKey];
                        const serverCell = student.grades[colKey];
                        const gradeVal = cell?.grade ?? '';
                        const gradeNum = gradeVal === '' ? null : parseFloat(gradeVal);
                        const letter = gradeNum !== null && !isNaN(gradeNum)
                          ? computeLetter(gradeNum, 100)
                          : (serverCell?.letter_grade ?? null);
                        const color = gradeColor(letter);
                        const feedbackKey = `${student.student_id}-${colKey}`;
                        const isFeedbackOpen = expandedFeedback.has(feedbackKey);
                        const isDirty = cell?.dirty ?? false;
                        const isPublished = serverCell?.is_published ?? false;

                        return (
                          <td key={asgn.id} className={`gep-td gep-td--grade${isDirty ? ' gep-td--dirty' : ''}`}>
                            <div className="gep-cell">
                              <div className="gep-cell-row">
                                <input
                                  ref={el => { inputRefs.current[si][ci] = el; }}
                                  type="number"
                                  min="0"
                                  max="100"
                                  step="0.5"
                                  className={`gep-grade-input gep-grade--${color}`}
                                  value={gradeVal}
                                  placeholder="—"
                                  aria-label={`Grade for ${student.student_name}, ${asgn.title}`}
                                  onChange={e => setCellValue(student.student_id, colKey, 'grade', e.target.value)}
                                  onKeyDown={e => handleKeyDown(e, si, ci)}
                                />
                                {letter && (
                                  <span className={`gep-letter gep-letter--${color}`} aria-label={`Letter grade: ${letter}`}>
                                    {letter}
                                  </span>
                                )}
                                {isPublished && (
                                  <span className="gep-published-badge" title="Published to student">P</span>
                                )}
                              </div>
                              <div className="gep-feedback-row">
                                <button
                                  type="button"
                                  className={`gep-feedback-toggle${isFeedbackOpen ? ' open' : ''}`}
                                  onClick={() => toggleFeedback(feedbackKey)}
                                  aria-expanded={isFeedbackOpen}
                                  aria-label="Toggle feedback"
                                >
                                  {isFeedbackOpen ? 'Hide' : 'Feedback'}
                                </button>
                              </div>
                              {isFeedbackOpen && (
                                <textarea
                                  className="gep-feedback-textarea"
                                  value={cell?.feedback ?? ''}
                                  placeholder="Add feedback..."
                                  rows={3}
                                  aria-label={`Feedback for ${student.student_name}, ${asgn.title}`}
                                  onChange={e => setCellValue(student.student_id, colKey, 'feedback', e.target.value)}
                                />
                              )}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {hasDirty && (
          <div className="gep-unsaved-banner" role="status" aria-live="polite">
            You have unsaved changes. Click <strong>Save All</strong> to save.
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
