import { useState, useRef } from 'react';
import { mockExamsApi } from '../api/mockExams';
import type { GenerateExamResponse, QuestionItem, MockExam } from '../api/mockExams';
import { useFocusTrap } from '../hooks/useFocusTrap';
import './GenerateMockExamModal.css';

interface Course {
  id: number;
  name: string;
  student_count?: number;
}

interface Student {
  id: number;
  name: string;
}

interface GenerateMockExamModalProps {
  courses: Course[];
  onClose: () => void;
  onExamSaved: (exam: MockExam) => void;
  /** Optionally fetch students for a course for assignment */
  fetchStudents?: (courseId: number) => Promise<Student[]>;
}

const QUESTION_COUNTS = [10, 20, 30, 40];
const DIFFICULTIES = ['easy', 'medium', 'hard'] as const;

export function GenerateMockExamModal({
  courses,
  onClose,
  onExamSaved,
  fetchStudents,
}: GenerateMockExamModalProps) {
  const modalRef = useFocusTrap<HTMLDivElement>(true, onClose);

  // Form state
  const [courseId, setCourseId] = useState<number | ''>(courses[0]?.id ?? '');
  const [topic, setTopic] = useState('');
  const [numQuestions, setNumQuestions] = useState(10);
  const [difficulty, setDifficulty] = useState<'easy' | 'medium' | 'hard'>('medium');
  const [timeLimitMinutes, setTimeLimitMinutes] = useState(60);

  // Generation state
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState('');
  const [preview, setPreview] = useState<GenerateExamResponse | null>(null);

  // Editable title / description
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');

  // Accordion open state per question index
  const [openQuestions, setOpenQuestions] = useState<Set<number>>(new Set([0]));

  // Saving state
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  // Assign state
  const [showAssign, setShowAssign] = useState(false);
  const [savedExam, setSavedExam] = useState<MockExam | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [loadingStudents, setLoadingStudents] = useState(false);
  const [selectedStudentIds, setSelectedStudentIds] = useState<Set<number>>(new Set());
  const [assignAll, setAssignAll] = useState(false);
  const [dueDate, setDueDate] = useState('');
  const [assigning, setAssigning] = useState(false);
  const [assignSuccess, setAssignSuccess] = useState('');
  const [assignError, setAssignError] = useState('');

  const handleGenerate = async () => {
    if (!courseId || !topic.trim()) {
      setGenerateError('Please select a course and enter a topic.');
      return;
    }
    setGenerating(true);
    setGenerateError('');
    setPreview(null);
    try {
      const result = await mockExamsApi.generate({
        course_id: Number(courseId),
        topic: topic.trim(),
        num_questions: numQuestions,
        difficulty,
        time_limit_minutes: timeLimitMinutes,
      });
      setPreview(result);
      setTitle(result.suggested_title);
      setOpenQuestions(new Set([0]));
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || 'Failed to generate exam. Please try again.';
      setGenerateError(msg);
    } finally {
      setGenerating(false);
    }
  };

  const toggleQuestion = (idx: number) => {
    setOpenQuestions(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const updateQuestion = (idx: number, field: keyof QuestionItem, value: string | number) => {
    if (!preview) return;
    const updated = preview.questions.map((q, i) => {
      if (i !== idx) return q;
      return { ...q, [field]: value };
    });
    setPreview({ ...preview, questions: updated });
  };

  const updateOption = (qIdx: number, optIdx: number, value: string) => {
    if (!preview) return;
    const updated = preview.questions.map((q, i) => {
      if (i !== qIdx) return q;
      const opts = [...q.options];
      opts[optIdx] = value;
      return { ...q, options: opts };
    });
    setPreview({ ...preview, questions: updated });
  };

  const handleSave = async () => {
    if (!preview || !title.trim()) {
      setSaveError('Title is required.');
      return;
    }
    setSaving(true);
    setSaveError('');
    try {
      const exam = await mockExamsApi.save({
        course_id: Number(courseId),
        title: title.trim(),
        description: description.trim() || undefined,
        questions: preview.questions,
        time_limit_minutes: timeLimitMinutes,
        total_marks: preview.questions.length,
      });
      setSavedExam(exam);
      onExamSaved(exam);

      // Load students for assignment
      if (fetchStudents) {
        setShowAssign(true);
        setLoadingStudents(true);
        try {
          const sts = await fetchStudents(Number(courseId));
          setStudents(sts);
        } catch {
          setStudents([]);
        } finally {
          setLoadingStudents(false);
        }
      } else {
        setShowAssign(true);
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || 'Failed to save exam.';
      setSaveError(msg);
    } finally {
      setSaving(false);
    }
  };

  const handleAssign = async () => {
    if (!savedExam) return;
    setAssigning(true);
    setAssignError('');
    setAssignSuccess('');
    try {
      const student_ids = assignAll ? 'all' : Array.from(selectedStudentIds);
      const result = await mockExamsApi.assign(savedExam.id, {
        student_ids,
        due_date: dueDate || null,
      });
      setAssignSuccess(
        `Assigned to ${result.assigned_count} student${result.assigned_count !== 1 ? 's' : ''}.`
        + (result.skipped_count > 0 ? ` (${result.skipped_count} skipped — already assigned)` : '')
      );
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || 'Failed to assign exam.';
      setAssignError(msg);
    } finally {
      setAssigning(false);
    }
  };

  const toggleStudent = (id: number) => {
    setSelectedStudentIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="gme-overlay" role="dialog" aria-modal="true" aria-label="Generate Mock Exam">
      <div className="gme-modal" ref={modalRef}>
        <div className="gme-header">
          <h2 className="gme-title">Generate Mock Exam</h2>
          <button className="gme-close" onClick={onClose} aria-label="Close">&#x2715;</button>
        </div>

        {!preview && !showAssign && (
          <div className="gme-form">
            <div className="gme-field">
              <label htmlFor="gme-course">Course</label>
              <select
                id="gme-course"
                value={courseId}
                onChange={e => setCourseId(Number(e.target.value))}
              >
                <option value="">Select course…</option>
                {courses.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>

            <div className="gme-field">
              <label htmlFor="gme-topic">Topic / Focus Area</label>
              <input
                id="gme-topic"
                type="text"
                placeholder="e.g. Photosynthesis, World War II, Quadratic Equations"
                value={topic}
                onChange={e => setTopic(e.target.value)}
                maxLength={500}
              />
            </div>

            <div className="gme-field">
              <label>Number of Questions</label>
              <div className="gme-pill-group">
                {QUESTION_COUNTS.map(n => (
                  <button
                    key={n}
                    type="button"
                    className={`gme-pill ${numQuestions === n ? 'active' : ''}`}
                    onClick={() => setNumQuestions(n)}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>

            <div className="gme-field">
              <label>Difficulty</label>
              <div className="gme-pill-group">
                {DIFFICULTIES.map(d => (
                  <button
                    key={d}
                    type="button"
                    className={`gme-pill gme-pill-${d} ${difficulty === d ? 'active' : ''}`}
                    onClick={() => setDifficulty(d)}
                  >
                    {d.charAt(0).toUpperCase() + d.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            <div className="gme-field">
              <label htmlFor="gme-timelimit">Time Limit (minutes)</label>
              <input
                id="gme-timelimit"
                type="number"
                min={5}
                max={300}
                value={timeLimitMinutes}
                onChange={e => setTimeLimitMinutes(Number(e.target.value))}
              />
            </div>

            {generateError && <p className="gme-error">{generateError}</p>}

            <div className="gme-actions">
              <button className="gme-btn-secondary" onClick={onClose}>Cancel</button>
              <button
                className="gme-btn-primary"
                onClick={handleGenerate}
                disabled={generating || !courseId || !topic.trim()}
              >
                {generating ? (
                  <span className="gme-spinner-row">
                    <span className="gme-spinner" /> Generating…
                  </span>
                ) : 'Generate Questions'}
              </button>
            </div>
          </div>
        )}

        {preview && !showAssign && (
          <div className="gme-preview">
            <div className="gme-preview-meta">
              <span className="gme-meta-badge">{preview.num_questions} questions</span>
              <span className={`gme-meta-badge gme-badge-${preview.difficulty}`}>
                {preview.difficulty}
              </span>
              <span className="gme-meta-badge">{timeLimitMinutes} min</span>
            </div>

            <div className="gme-field">
              <label htmlFor="gme-title">Exam Title</label>
              <input
                id="gme-title"
                type="text"
                value={title}
                onChange={e => setTitle(e.target.value)}
                maxLength={500}
              />
            </div>

            <div className="gme-field">
              <label htmlFor="gme-desc">Description (optional)</label>
              <textarea
                id="gme-desc"
                value={description}
                onChange={e => setDescription(e.target.value)}
                rows={2}
                placeholder="Add exam instructions or notes for students…"
              />
            </div>

            <h3 className="gme-questions-heading">Questions (editable)</h3>
            <div className="gme-questions-list">
              {preview.questions.map((q, idx) => (
                <div key={idx} className="gme-question-card">
                  <button
                    className="gme-question-toggle"
                    onClick={() => toggleQuestion(idx)}
                    type="button"
                  >
                    <span className="gme-q-num">Q{idx + 1}</span>
                    <span className="gme-q-preview">{q.question.slice(0, 80)}{q.question.length > 80 ? '…' : ''}</span>
                    <span className="gme-chevron">{openQuestions.has(idx) ? '▲' : '▼'}</span>
                  </button>

                  {openQuestions.has(idx) && (
                    <div className="gme-question-body">
                      <div className="gme-field">
                        <label>Question</label>
                        <textarea
                          value={q.question}
                          onChange={e => updateQuestion(idx, 'question', e.target.value)}
                          rows={2}
                        />
                      </div>
                      <div className="gme-options">
                        {q.options.map((opt, oi) => (
                          <div key={oi} className={`gme-option ${q.correct_index === oi ? 'correct' : ''}`}>
                            <span className="gme-option-label">{String.fromCharCode(65 + oi)}</span>
                            <input
                              type="text"
                              value={opt}
                              onChange={e => updateOption(idx, oi, e.target.value)}
                            />
                            <button
                              type="button"
                              className={`gme-correct-btn ${q.correct_index === oi ? 'selected' : ''}`}
                              onClick={() => updateQuestion(idx, 'correct_index', oi)}
                              title="Mark as correct"
                            >
                              {q.correct_index === oi ? '✓' : 'Mark correct'}
                            </button>
                          </div>
                        ))}
                      </div>
                      <div className="gme-field">
                        <label>Explanation</label>
                        <textarea
                          value={q.explanation || ''}
                          onChange={e => updateQuestion(idx, 'explanation', e.target.value)}
                          rows={2}
                        />
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {saveError && <p className="gme-error">{saveError}</p>}

            <div className="gme-actions">
              <button
                className="gme-btn-secondary"
                onClick={() => setPreview(null)}
                disabled={saving}
              >
                Regenerate
              </button>
              <button
                className="gme-btn-primary"
                onClick={handleSave}
                disabled={saving || !title.trim()}
              >
                {saving ? 'Saving…' : 'Save & Assign'}
              </button>
            </div>
          </div>
        )}

        {showAssign && (
          <div className="gme-assign">
            {assignSuccess ? (
              <div className="gme-assign-success">
                <div className="gme-success-icon">&#10003;</div>
                <p className="gme-success-text">{assignSuccess}</p>
                <p className="gme-success-sub">
                  Exam "{savedExam?.title}" has been saved and assigned.
                </p>
                <button className="gme-btn-primary" onClick={onClose}>Done</button>
              </div>
            ) : (
              <>
                <h3 className="gme-assign-heading">Assign to Students</h3>
                <p className="gme-assign-sub">
                  Exam: <strong>{savedExam?.title}</strong>
                </p>

                <div className="gme-field">
                  <label>
                    <input
                      type="checkbox"
                      checked={assignAll}
                      onChange={e => setAssignAll(e.target.checked)}
                    />
                    {' '}Assign to all enrolled students
                  </label>
                </div>

                {!assignAll && (
                  <div className="gme-students-list">
                    {loadingStudents ? (
                      <p className="gme-loading">Loading students…</p>
                    ) : students.length === 0 ? (
                      <p className="gme-empty">No students found for this course.</p>
                    ) : (
                      students.map(s => (
                        <label key={s.id} className="gme-student-item">
                          <input
                            type="checkbox"
                            checked={selectedStudentIds.has(s.id)}
                            onChange={() => toggleStudent(s.id)}
                          />
                          {' '}{s.name}
                        </label>
                      ))
                    )}
                  </div>
                )}

                <div className="gme-field">
                  <label htmlFor="gme-duedate">Due Date (optional)</label>
                  <input
                    id="gme-duedate"
                    type="date"
                    value={dueDate}
                    onChange={e => setDueDate(e.target.value)}
                  />
                </div>

                {assignError && <p className="gme-error">{assignError}</p>}

                <div className="gme-actions">
                  <button
                    className="gme-btn-secondary"
                    onClick={onClose}
                    disabled={assigning}
                  >
                    Skip (Save only)
                  </button>
                  <button
                    className="gme-btn-primary"
                    onClick={handleAssign}
                    disabled={assigning || (!assignAll && selectedStudentIds.size === 0)}
                  >
                    {assigning ? 'Assigning…' : 'Assign Now'}
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default GenerateMockExamModal;
