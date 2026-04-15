import { useState, useCallback, useEffect, useMemo } from 'react';
import './ASGFContextPanel.css';

/** Context fields confirmed by the user. */
export interface ASGFContext {
  childId?: string;
  childName?: string;
  subject: string;
  gradeLevel: string;
  board: string;
  courseId?: string;
  courseName?: string;
  teacherName?: string;
  testDate?: string;
  taskTitle?: string;
}

export interface ASGFContextPanelProps {
  intentResult?: {
    subject: string;
    grade_level: string;
    topic: string;
    confidence: number;
  };
  userRole: 'parent' | 'student' | 'teacher';
  children?: { id: string; name: string; grade: string; board: string }[];
  courses?: { id: string; name: string; teacher: string }[];
  upcomingTasks?: { id: string; title: string; due_date: string }[];
  onContextConfirmed: (context: ASGFContext) => void;
}

const CONFIDENCE_THRESHOLD = 0.7;

export function ASGFContextPanel({
  intentResult,
  userRole,
  children: childrenList,
  courses,
  upcomingTasks,
  onContextConfirmed,
}: ASGFContextPanelProps) {
  const confidence = intentResult?.confidence ?? 0;
  const allFieldsPopulated =
    confidence >= CONFIDENCE_THRESHOLD &&
    !!intentResult?.subject &&
    !!intentResult?.grade_level;

  const [expanded, setExpanded] = useState(!allFieldsPopulated);

  // Field state
  const [selectedChildId, setSelectedChildId] = useState<string>('');
  const [subject, setSubject] = useState(intentResult?.subject ?? '');
  const [gradeLevel, setGradeLevel] = useState(intentResult?.grade_level ?? '');
  const [board, setBoard] = useState('');
  const [selectedCourseId, setSelectedCourseId] = useState<string>('');
  const [testDate, setTestDate] = useState<string>('');
  const [selectedTaskId, setSelectedTaskId] = useState<string>('');

  // Auto-populate child fields when a child is selected
  const selectedChild = useMemo(
    () => childrenList?.find((c) => c.id === selectedChildId),
    [childrenList, selectedChildId],
  );

  useEffect(() => {
    if (selectedChild) {
      if (selectedChild.grade) setGradeLevel(selectedChild.grade);
      setBoard(selectedChild.board || 'Ontario');
    }
  }, [selectedChild]);

  // Auto-select the first (only) child
  useEffect(() => {
    if (userRole === 'parent' && childrenList?.length === 1 && !selectedChildId) {
      setSelectedChildId(childrenList[0].id);
    }
  }, [userRole, childrenList, selectedChildId]);

  // When a task is selected, populate its due date
  useEffect(() => {
    if (selectedTaskId && upcomingTasks) {
      const task = upcomingTasks.find((t) => t.id === selectedTaskId);
      if (task?.due_date) setTestDate(task.due_date);
    }
  }, [selectedTaskId, upcomingTasks]);

  const selectedCourse = useMemo(
    () => courses?.find((c) => c.id === selectedCourseId),
    [courses, selectedCourseId],
  );

  const lowConfidence = confidence < CONFIDENCE_THRESHOLD;

  const handleConfirm = useCallback(() => {
    onContextConfirmed({
      childId: selectedChildId || undefined,
      childName: selectedChild?.name,
      subject,
      gradeLevel,
      board: board || 'Ontario',
      courseId: selectedCourseId || undefined,
      courseName: selectedCourse?.name,
      teacherName: selectedCourse?.teacher,
      testDate: testDate || undefined,
      taskTitle: upcomingTasks?.find((t) => t.id === selectedTaskId)?.title,
    });
  }, [
    selectedChildId,
    selectedChild,
    subject,
    gradeLevel,
    board,
    selectedCourseId,
    selectedCourse,
    testDate,
    upcomingTasks,
    selectedTaskId,
    onContextConfirmed,
  ]);

  const toggle = useCallback(() => setExpanded((p) => !p), []);

  return (
    <div className="asgf-ctx-panel">
      <button
        className="asgf-ctx-toggle"
        onClick={toggle}
        aria-expanded={expanded}
        aria-controls="asgf-ctx-body"
        type="button"
      >
        <svg
          className={`asgf-ctx-chevron${expanded ? ' asgf-ctx-chevron--open' : ''}`}
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M6 4l4 4-4 4"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <span className="asgf-ctx-title">Study Context</span>
        {!expanded && allFieldsPopulated && (
          <span className="asgf-ctx-ready-badge">Ready</span>
        )}
      </button>

      <div id="asgf-ctx-body" className="asgf-ctx-body" hidden={!expanded}>
        <div className="asgf-ctx-fields">
          {/* Child selector — parent only */}
          {userRole === 'parent' && (
            <div className="asgf-ctx-field">
              <label htmlFor="asgf-child">Which child?</label>
              <select
                id="asgf-child"
                value={selectedChildId}
                onChange={(e) => setSelectedChildId(e.target.value)}
              >
                <option value="">-- Select child --</option>
                {childrenList?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Subject / course */}
          <div className={`asgf-ctx-field${lowConfidence ? ' asgf-ctx-field--low' : ''}`}>
            <label htmlFor="asgf-subject">Subject / Course</label>
            <input
              id="asgf-subject"
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Math, Science"
            />
          </div>

          {/* Grade level */}
          <div className={`asgf-ctx-field${lowConfidence && !selectedChild ? ' asgf-ctx-field--low' : ''}`}>
            <label htmlFor="asgf-grade">Grade Level</label>
            <input
              id="asgf-grade"
              type="text"
              value={gradeLevel}
              onChange={(e) => setGradeLevel(e.target.value)}
              readOnly={!!selectedChild}
              placeholder="e.g. 7"
            />
          </div>

          {/* School board */}
          <div className="asgf-ctx-field">
            <label htmlFor="asgf-board">School Board</label>
            <input
              id="asgf-board"
              type="text"
              value={board}
              onChange={(e) => setBoard(e.target.value)}
              readOnly={!!selectedChild && !!selectedChild.board}
              placeholder="Ontario"
            />
          </div>

          {/* Class / teacher */}
          {courses && courses.length > 0 && (
            <div className="asgf-ctx-field">
              <label htmlFor="asgf-course">Class / Teacher</label>
              <select
                id="asgf-course"
                value={selectedCourseId}
                onChange={(e) => setSelectedCourseId(e.target.value)}
              >
                <option value="">-- Select class --</option>
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}{c.teacher ? ` (${c.teacher})` : ''}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Test / assignment date */}
          <div className="asgf-ctx-field">
            <label htmlFor="asgf-date">Test / Assignment Date</label>
            {upcomingTasks && upcomingTasks.length > 0 ? (
              <select
                id="asgf-date"
                value={selectedTaskId}
                onChange={(e) => {
                  setSelectedTaskId(e.target.value);
                  if (!e.target.value) setTestDate('');
                }}
              >
                <option value="">-- Select task or enter date --</option>
                {upcomingTasks.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title} ({t.due_date})
                  </option>
                ))}
              </select>
            ) : (
              <input
                id="asgf-date"
                type="date"
                value={testDate}
                onChange={(e) => setTestDate(e.target.value)}
              />
            )}
            {/* Allow manual date override when task list exists */}
            {upcomingTasks && upcomingTasks.length > 0 && (
              <input
                className="asgf-ctx-date-override"
                type="date"
                value={testDate}
                onChange={(e) => {
                  setTestDate(e.target.value);
                  setSelectedTaskId('');
                }}
                aria-label="Override date manually"
              />
            )}
          </div>
        </div>

        <button
          className="asgf-ctx-confirm"
          type="button"
          onClick={handleConfirm}
          disabled={!subject}
        >
          Looks Good &mdash; Continue
        </button>
      </div>
    </div>
  );
}
