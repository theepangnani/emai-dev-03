import { useState, useEffect, useRef } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { sampleExamsApi } from '../api/sampleExams';
import type { SampleExam, ExamAssessment, PracticeMode } from '../api/sampleExams';
import { api } from '../api/client';
import './SampleExamsPage.css';

interface Course {
  id: number;
  name: string;
}

// ---------------------------------------------------------------------------
// Score colour helper
// ---------------------------------------------------------------------------
function scoreClass(score: number): string {
  if (score >= 80) return 'sep-score-green';
  if (score >= 60) return 'sep-score-amber';
  return 'sep-score-red';
}

// ---------------------------------------------------------------------------
// Upload Modal
// ---------------------------------------------------------------------------
interface UploadModalProps {
  courses: Course[];
  onClose: () => void;
  onUploaded: (exam: SampleExam) => void;
}

function UploadModal({ courses, onClose, onUploaded }: UploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [courseId, setCourseId] = useState<string>('');
  const [examType, setExamType] = useState<'sample' | 'practice' | 'past'>('sample');
  const [assessOnUpload, setAssessOnUpload] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File) => {
    setFile(f);
    if (!title) setTitle(f.name.replace(/\.[^.]+$/, ''));
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFile(dropped);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) { setError('Please select a file.'); return; }
    if (!title.trim()) { setError('Title is required.'); return; }
    setError('');
    setUploading(true);
    try {
      const exam = await sampleExamsApi.upload({
        file,
        title: title.trim(),
        description: description.trim() || undefined,
        course_id: courseId ? Number(courseId) : null,
        exam_type: examType,
        assess_on_upload: assessOnUpload,
      });
      onUploaded(exam);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed. Please try again.';
      setError(msg);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="sep-modal-overlay" role="dialog" aria-modal="true" aria-label="Upload exam">
      <div className="sep-modal sep-upload-modal">
        <div className="sep-modal-header">
          <h2>Upload Sample Exam</h2>
          <button className="sep-modal-close" onClick={onClose} aria-label="Close" type="button">
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit} className="sep-upload-form">
          {/* Drop zone */}
          <div
            className={`sep-dropzone${dragOver ? ' sep-dropzone-active' : ''}${file ? ' sep-dropzone-filled' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click(); }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.gif,.bmp,.tiff,.webp"
              style={{ display: 'none' }}
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
            />
            {file ? (
              <div className="sep-dropzone-file">
                <span className="sep-dropzone-icon">&#128196;</span>
                <span className="sep-dropzone-filename">{file.name}</span>
                <span className="sep-dropzone-size">({(file.size / 1024 / 1024).toFixed(2)} MB)</span>
              </div>
            ) : (
              <div className="sep-dropzone-prompt">
                <span className="sep-dropzone-icon">&#128196;</span>
                <p>Drag and drop a file here, or click to select</p>
                <small>PDF, DOC, DOCX, or image files</small>
              </div>
            )}
          </div>

          <div className="sep-form-group">
            <label htmlFor="sep-title">Title <span className="sep-required">*</span></label>
            <input
              id="sep-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Grade 10 Math Midterm 2024"
              required
              maxLength={500}
            />
          </div>

          <div className="sep-form-group">
            <label htmlFor="sep-description">Description (optional)</label>
            <textarea
              id="sep-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief notes about this exam..."
              rows={3}
              maxLength={2000}
            />
          </div>

          <div className="sep-form-row">
            <div className="sep-form-group">
              <label htmlFor="sep-course">Course (optional)</label>
              <select
                id="sep-course"
                value={courseId}
                onChange={(e) => setCourseId(e.target.value)}
              >
                <option value="">-- No course --</option>
                {courses.map((c) => (
                  <option key={c.id} value={String(c.id)}>{c.name}</option>
                ))}
              </select>
            </div>

            <div className="sep-form-group">
              <label htmlFor="sep-type">Exam Type</label>
              <select
                id="sep-type"
                value={examType}
                onChange={(e) => setExamType(e.target.value as 'sample' | 'practice' | 'past')}
              >
                <option value="sample">Sample</option>
                <option value="practice">Practice</option>
                <option value="past">Past</option>
              </select>
            </div>
          </div>

          <label className="sep-checkbox-label">
            <input
              type="checkbox"
              checked={assessOnUpload}
              onChange={(e) => setAssessOnUpload(e.target.checked)}
            />
            Assess with AI after upload
          </label>

          {error && <p className="sep-form-error">{error}</p>}

          <div className="sep-modal-footer">
            <button type="button" className="sep-btn sep-btn-secondary" onClick={onClose} disabled={uploading}>
              Cancel
            </button>
            <button type="submit" className="sep-btn sep-btn-primary" disabled={uploading}>
              {uploading ? 'Uploading...' : 'Upload & Assess'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Assessment Modal
// ---------------------------------------------------------------------------
interface AssessmentModalProps {
  exam: SampleExam;
  assessment: ExamAssessment;
  onClose: () => void;
  onReassess: () => Promise<void>;
}

function AssessmentModal({ exam, assessment, onClose, onReassess }: AssessmentModalProps) {
  const [reassessing, setReassessing] = useState(false);
  const score = assessment.overall_score ?? 0;
  const dist = assessment.difficulty_analysis?.distribution ?? { easy: 0, medium: 0, hard: 0 };

  const handleReassess = async () => {
    setReassessing(true);
    try { await onReassess(); } finally { setReassessing(false); }
  };

  return (
    <div className="sep-modal-overlay" role="dialog" aria-modal="true" aria-label="AI Assessment">
      <div className="sep-modal sep-assessment-modal">
        <div className="sep-modal-header">
          <h2>AI Assessment: {exam.title}</h2>
          <button className="sep-modal-close" onClick={onClose} aria-label="Close" type="button">
            &times;
          </button>
        </div>

        <div className="sep-assessment-body">
          {/* Overall score circle */}
          <div className="sep-score-section">
            <div className={`sep-score-circle ${scoreClass(score)}`}>
              <span className="sep-score-number">{score}</span>
              <span className="sep-score-label">/ 100</span>
            </div>
            <p className="sep-summary">{assessment.summary}</p>
          </div>

          {/* Strengths + Weaknesses */}
          <div className="sep-sw-row">
            <div className="sep-strengths-box">
              <h4>Strengths</h4>
              <ul>
                {(assessment.strengths ?? []).map((s, i) => (
                  <li key={i} className="sep-strength-item">
                    <span className="sep-check">&#10003;</span> {s}
                  </li>
                ))}
                {(assessment.strengths ?? []).length === 0 && <li className="sep-muted">None identified</li>}
              </ul>
            </div>
            <div className="sep-weaknesses-box">
              <h4>Weaknesses</h4>
              <ul>
                {(assessment.weaknesses ?? []).map((w, i) => (
                  <li key={i} className="sep-weakness-item">
                    <span className="sep-warn">&#9888;</span> {w}
                  </li>
                ))}
                {(assessment.weaknesses ?? []).length === 0 && <li className="sep-muted">None identified</li>}
              </ul>
            </div>
          </div>

          {/* Difficulty Distribution */}
          <div className="sep-section">
            <h4>Difficulty Distribution</h4>
            <div className="sep-difficulty-chart">
              <div className="sep-diff-bar-row">
                <span className="sep-diff-label">Easy</span>
                <div className="sep-diff-bar-track">
                  <div className="sep-diff-bar sep-diff-easy" style={{ width: `${dist.easy}%` }} />
                </div>
                <span className="sep-diff-pct">{dist.easy}%</span>
              </div>
              <div className="sep-diff-bar-row">
                <span className="sep-diff-label">Medium</span>
                <div className="sep-diff-bar-track">
                  <div className="sep-diff-bar sep-diff-medium" style={{ width: `${dist.medium}%` }} />
                </div>
                <span className="sep-diff-pct">{dist.medium}%</span>
              </div>
              <div className="sep-diff-bar-row">
                <span className="sep-diff-label">Hard</span>
                <div className="sep-diff-bar-track">
                  <div className="sep-diff-bar sep-diff-hard" style={{ width: `${dist.hard}%` }} />
                </div>
                <span className="sep-diff-pct">{dist.hard}%</span>
              </div>
            </div>
            {assessment.difficulty_analysis?.suggestions?.length ? (
              <ul className="sep-suggestion-list">
                {assessment.difficulty_analysis.suggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            ) : null}
          </div>

          {/* Curriculum Coverage */}
          <div className="sep-section">
            <h4>Curriculum Coverage</h4>
            <div className="sep-coverage-badges">
              <span className={`sep-badge sep-badge-${assessment.curriculum_coverage?.breadth ?? 'poor'}`}>
                Breadth: {assessment.curriculum_coverage?.breadth ?? '—'}
              </span>
              <span className={`sep-badge sep-badge-${assessment.curriculum_coverage?.depth ?? 'poor'}`}>
                Depth: {assessment.curriculum_coverage?.depth ?? '—'}
              </span>
            </div>
            {(assessment.curriculum_coverage?.gaps ?? []).length > 0 && (
              <div className="sep-coverage-list">
                <strong>Gaps:</strong>
                <ul>{assessment.curriculum_coverage.gaps.map((g, i) => <li key={i}>{g}</li>)}</ul>
              </div>
            )}
            {(assessment.curriculum_coverage?.overlap ?? []).length > 0 && (
              <div className="sep-coverage-list">
                <strong>Overlap:</strong>
                <ul>{assessment.curriculum_coverage.overlap.map((o, i) => <li key={i}>{o}</li>)}</ul>
              </div>
            )}
          </div>

          {/* Question Quality */}
          <div className="sep-section">
            <h4>Question Quality</h4>
            <div className="sep-qq-summary">
              <span>{assessment.question_quality?.total_questions ?? 0} total</span>
              <span>{assessment.question_quality?.clear_questions ?? 0} clear</span>
              <span>{(assessment.question_quality?.ambiguous_questions ?? []).length} ambiguous</span>
            </div>
            {(assessment.question_quality?.improvement_suggestions ?? []).length > 0 && (
              <table className="sep-qq-table">
                <thead>
                  <tr>
                    <th>Q#</th>
                    <th>Issue</th>
                    <th>Suggestion</th>
                  </tr>
                </thead>
                <tbody>
                  {assessment.question_quality.improvement_suggestions.map((s, i) => (
                    <tr key={i}>
                      <td>{s.question_number}</td>
                      <td>{s.issue}</td>
                      <td>{s.suggestion}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Recommendations */}
          <div className="sep-section">
            <h4>Recommendations</h4>
            <ol className="sep-recommendation-list">
              {(assessment.recommendations ?? []).map((r, i) => (
                <li key={i}>{r}</li>
              ))}
              {(assessment.recommendations ?? []).length === 0 && (
                <li className="sep-muted">No recommendations</li>
              )}
            </ol>
          </div>
        </div>

        <div className="sep-modal-footer">
          <button
            type="button"
            className="sep-btn sep-btn-secondary"
            onClick={handleReassess}
            disabled={reassessing}
          >
            {reassessing ? 'Re-assessing...' : 'Re-run Assessment'}
          </button>
          <button type="button" className="sep-btn sep-btn-ghost" disabled title="Coming soon">
            Download Report
          </button>
          <button type="button" className="sep-btn sep-btn-primary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Practice Mode Modal
// ---------------------------------------------------------------------------
interface PracticeModalProps {
  exam: SampleExam;
  practice: PracticeMode;
  onClose: () => void;
}

function PracticeModal({ exam, practice, onClose }: PracticeModalProps) {
  const [answers, setAnswers] = useState<string[]>(Array(practice.questions.length).fill(''));
  const [submitted, setSubmitted] = useState(false);

  const allAnswered = answers.every((a) => a.trim() !== '');

  return (
    <div className="sep-modal-overlay" role="dialog" aria-modal="true" aria-label="Practice Mode">
      <div className="sep-modal sep-practice-modal">
        <div className="sep-modal-header">
          <h2>Practice: {exam.title}</h2>
          <button className="sep-modal-close" onClick={onClose} aria-label="Close" type="button">
            &times;
          </button>
        </div>

        <div className="sep-practice-body">
          {submitted ? (
            <div className="sep-practice-done">
              <div className="sep-practice-done-icon">&#10003;</div>
              <h3>Great work!</h3>
              <p>You answered all {practice.question_count} questions.</p>
              <p className="sep-muted sep-ai-note">AI-powered grading coming soon.</p>
              <button type="button" className="sep-btn sep-btn-primary" onClick={onClose}>
                Close
              </button>
            </div>
          ) : (
            <>
              {practice.questions.length === 0 ? (
                <p className="sep-muted">
                  No questions could be extracted from this exam automatically. The exam may be
                  image-based or use a non-standard format.
                </p>
              ) : (
                <div className="sep-practice-questions">
                  {practice.questions.map((q, i) => (
                    <div key={i} className="sep-practice-q">
                      <p className="sep-practice-q-text">{q}</p>
                      <textarea
                        className="sep-practice-answer"
                        placeholder="Your answer..."
                        rows={3}
                        value={answers[i]}
                        onChange={(e) => {
                          const next = [...answers];
                          next[i] = e.target.value;
                          setAnswers(next);
                        }}
                      />
                    </div>
                  ))}
                </div>
              )}

              <p className="sep-ai-note">
                Note: AI-powered grading coming soon. This is a self-practice interface.
              </p>

              <div className="sep-modal-footer">
                <button type="button" className="sep-btn sep-btn-secondary" onClick={onClose}>
                  Cancel
                </button>
                {practice.questions.length > 0 && (
                  <button
                    type="button"
                    className="sep-btn sep-btn-primary"
                    onClick={() => setSubmitted(true)}
                    disabled={!allAnswered}
                  >
                    Submit
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function SampleExamsPage() {
  const [exams, setExams] = useState<SampleExam[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [selectedAssessmentExam, setSelectedAssessmentExam] = useState<SampleExam | null>(null);
  const [practiceData, setPracticeData] = useState<PracticeMode | null>(null);
  const [practiceExam, setPracticeExam] = useState<SampleExam | null>(null);
  const [loadingPractice, setLoadingPractice] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [filterCourseId, setFilterCourseId] = useState('');
  const [filterExamType, setFilterExamType] = useState('');
  const [filterPublicOnly, setFilterPublicOnly] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      sampleExamsApi.list({ limit: 100 }),
      api.get('/api/courses/').catch(() => ({ data: [] as Course[] })),
    ])
      .then(([listRes, coursesRes]) => {
        setExams(listRes.items);
        const courseData = Array.isArray(coursesRes.data)
          ? coursesRes.data
          : (coursesRes.data as { items?: Course[] })?.items ?? [];
        setCourses(courseData);
      })
      .catch((err) => {
        console.error('Failed to load sample exams:', err);
        setError('Failed to load exams. Please refresh.');
      })
      .finally(() => setLoading(false));
  }, []);

  const handleUploaded = (exam: SampleExam) => {
    setExams((prev) => [exam, ...prev]);
    setShowUploadModal(false);
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Delete this sample exam? This cannot be undone.')) return;
    setDeletingId(id);
    try {
      await sampleExamsApi.delete(id);
      setExams((prev) => prev.filter((e) => e.id !== id));
    } catch {
      setError('Failed to delete exam.');
    } finally {
      setDeletingId(null);
    }
  };

  const handleTogglePublish = async (exam: SampleExam) => {
    try {
      const result = await sampleExamsApi.togglePublish(exam.id);
      setExams((prev) =>
        prev.map((e) => (e.id === exam.id ? { ...e, is_public: result.is_public } : e))
      );
    } catch {
      setError('Failed to update visibility.');
    }
  };

  const handleViewAssessment = (exam: SampleExam) => {
    setSelectedAssessmentExam(exam);
  };

  const handleReassess = async () => {
    if (!selectedAssessmentExam) return;
    const updated = await sampleExamsApi.reassess(selectedAssessmentExam.id);
    setSelectedAssessmentExam(updated);
    setExams((prev) => prev.map((e) => (e.id === updated.id ? updated : e)));
  };

  const handlePracticeMode = async (exam: SampleExam) => {
    setLoadingPractice(exam.id);
    try {
      const data = await sampleExamsApi.getPractice(exam.id);
      setPracticeData(data);
      setPracticeExam(exam);
    } catch {
      setError('Failed to load practice mode.');
    } finally {
      setLoadingPractice(null);
    }
  };

  // Apply filters client-side (server filtering also available but cards are already loaded)
  const visibleExams = exams.filter((e) => {
    if (filterCourseId && String(e.course_id) !== filterCourseId) return false;
    if (filterExamType && e.exam_type !== filterExamType) return false;
    if (filterPublicOnly && !e.is_public) return false;
    return true;
  });

  return (
    <DashboardLayout>
      <div className="sep-page">
        {/* Header */}
        <div className="sep-header">
          <div>
            <h1 className="sep-title">Sample Exams</h1>
            <p className="sep-subtitle">
              Upload exam files for AI quality assessment. Share with students for practice.
            </p>
          </div>
          <button
            type="button"
            className="sep-btn sep-btn-primary"
            onClick={() => setShowUploadModal(true)}
          >
            + Upload New Exam
          </button>
        </div>

        {/* Filter bar */}
        <div className="sep-filters">
          <select
            value={filterCourseId}
            onChange={(e) => setFilterCourseId(e.target.value)}
            className="sep-filter-select"
          >
            <option value="">All Courses</option>
            {courses.map((c) => (
              <option key={c.id} value={String(c.id)}>{c.name}</option>
            ))}
          </select>

          <select
            value={filterExamType}
            onChange={(e) => setFilterExamType(e.target.value)}
            className="sep-filter-select"
          >
            <option value="">All Types</option>
            <option value="sample">Sample</option>
            <option value="practice">Practice</option>
            <option value="past">Past</option>
          </select>

          <label className="sep-filter-toggle">
            <input
              type="checkbox"
              checked={filterPublicOnly}
              onChange={(e) => setFilterPublicOnly(e.target.checked)}
            />
            Student-visible only
          </label>
        </div>

        {error && (
          <div className="sep-error-banner">
            {error}
            <button type="button" onClick={() => setError('')} className="sep-error-dismiss">
              &times;
            </button>
          </div>
        )}

        {/* Card grid */}
        {loading ? (
          <div className="sep-loading">Loading exams...</div>
        ) : visibleExams.length === 0 ? (
          <div className="sep-empty">
            <div className="sep-empty-icon">&#128196;</div>
            <h3>No exams yet</h3>
            <p>Upload your first exam to get an AI quality assessment.</p>
            <button
              type="button"
              className="sep-btn sep-btn-primary"
              onClick={() => setShowUploadModal(true)}
            >
              + Upload New Exam
            </button>
          </div>
        ) : (
          <div className="sep-card-grid">
            {visibleExams.map((exam) => {
              const score = exam.assessment?.overall_score;
              return (
                <div key={exam.id} className="sep-card">
                  <div className="sep-card-body">
                    <div className="sep-card-top">
                      <h3 className="sep-card-title">{exam.title}</h3>
                      <div className="sep-card-badges">
                        {exam.course_name && (
                          <span className="sep-badge sep-badge-course">{exam.course_name}</span>
                        )}
                        <span className="sep-badge sep-badge-type">{exam.exam_type}</span>
                      </div>
                    </div>

                    {exam.description && (
                      <p className="sep-card-description">{exam.description}</p>
                    )}

                    <div className="sep-card-meta">
                      {exam.file_name && (
                        <span className="sep-card-file">&#128196; {exam.file_name}</span>
                      )}
                      <span className="sep-card-date">
                        {exam.created_at
                          ? new Date(exam.created_at).toLocaleDateString()
                          : 'Recently'}
                      </span>
                    </div>

                    {/* AI score badge */}
                    <div className="sep-card-score-row">
                      {score != null ? (
                        <span className={`sep-score-badge ${scoreClass(score)}`}>
                          AI Score: {score}/100
                        </span>
                      ) : (
                        <span className="sep-score-badge sep-score-none">No assessment yet</span>
                      )}

                      {/* Visibility toggle */}
                      <label className="sep-public-toggle" title="Toggle student visibility">
                        <input
                          type="checkbox"
                          checked={exam.is_public}
                          onChange={() => handleTogglePublish(exam)}
                        />
                        <span>{exam.is_public ? 'Public' : 'Private'}</span>
                      </label>
                    </div>
                  </div>

                  {/* Card footer actions */}
                  <div className="sep-card-footer">
                    <button
                      type="button"
                      className="sep-btn sep-btn-sm sep-btn-secondary"
                      onClick={() => handleViewAssessment(exam)}
                      disabled={!exam.assessment}
                      title={exam.assessment ? 'View AI assessment' : 'No assessment available'}
                    >
                      View Assessment
                    </button>
                    <button
                      type="button"
                      className="sep-btn sep-btn-sm sep-btn-secondary"
                      onClick={() => handlePracticeMode(exam)}
                      disabled={loadingPractice === exam.id}
                    >
                      {loadingPractice === exam.id ? 'Loading...' : 'Practice Mode'}
                    </button>
                    <button
                      type="button"
                      className="sep-btn sep-btn-sm sep-btn-danger"
                      onClick={() => handleDelete(exam.id)}
                      disabled={deletingId === exam.id}
                      aria-label={`Delete ${exam.title}`}
                    >
                      {deletingId === exam.id ? '...' : '&#128465;'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Modals */}
      {showUploadModal && (
        <UploadModal
          courses={courses}
          onClose={() => setShowUploadModal(false)}
          onUploaded={handleUploaded}
        />
      )}

      {selectedAssessmentExam?.assessment && (
        <AssessmentModal
          exam={selectedAssessmentExam}
          assessment={selectedAssessmentExam.assessment}
          onClose={() => setSelectedAssessmentExam(null)}
          onReassess={handleReassess}
        />
      )}

      {practiceData && practiceExam && (
        <PracticeModal
          exam={practiceExam}
          practice={practiceData}
          onClose={() => { setPracticeData(null); setPracticeExam(null); }}
        />
      )}
    </DashboardLayout>
  );
}
