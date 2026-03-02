import { useState, useEffect } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { GenerateMockExamModal } from '../components/GenerateMockExamModal';
import { mockExamsApi } from '../api/mockExams';
import type { MockExam } from '../api/mockExams';
import { coursesApi } from '../api/client';
import './TeacherExamsPage.css';

interface Course {
  id: number;
  name: string;
  student_count?: number;
}

export function TeacherExamsPage() {
  const [exams, setExams] = useState<MockExam[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    Promise.all([
      mockExamsApi.list().then(data => setExams(data as MockExam[])),
      coursesApi.teachingList().then(data => setCourses(data)),
    ]).finally(() => setLoading(false));
  }, []);

  const handleDelete = async (examId: number) => {
    if (!window.confirm('Delete this exam and all its assignments?')) return;
    setDeletingId(examId);
    try {
      await mockExamsApi.deleteExam(examId);
      setExams(prev => prev.filter(e => e.id !== examId));
    } catch {
      // Silent
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <DashboardLayout>
      <div className="tep-page">
        <div className="tep-header">
          <div>
            <h1 className="tep-title">Mock Exams</h1>
            <p className="tep-subtitle">Generate and manage AI-powered mock exams for your students.</p>
          </div>
          <button
            className="tep-generate-btn"
            onClick={() => setShowGenerateModal(true)}
            type="button"
          >
            + Generate Exam
          </button>
        </div>

        {loading ? (
          <div className="tep-loading">Loading exams…</div>
        ) : exams.length === 0 ? (
          <div className="tep-empty">
            <div className="tep-empty-icon">&#128221;</div>
            <h3>No exams yet</h3>
            <p>Click "Generate Exam" to create your first AI-powered mock exam.</p>
            <button
              className="tep-generate-btn"
              onClick={() => setShowGenerateModal(true)}
              type="button"
            >
              + Generate Exam
            </button>
          </div>
        ) : (
          <div className="tep-exams-list">
            {exams.map(exam => (
              <div key={exam.id} className="tep-exam-card">
                <div className="tep-exam-card-main">
                  <div className="tep-exam-info">
                    <h3 className="tep-exam-title">{exam.title}</h3>
                    <p className="tep-exam-meta">
                      {exam.course_name} &middot; {exam.num_questions} questions &middot; {exam.time_limit_minutes} min
                      {exam.description && ` · ${exam.description}`}
                    </p>
                    <p className="tep-exam-created">
                      Created {exam.created_at ? new Date(exam.created_at).toLocaleDateString() : 'recently'}
                    </p>
                  </div>
                  <div className="tep-exam-stats">
                    <div className="tep-stat">
                      <span className="tep-stat-value">{exam.assignment_count}</span>
                      <span className="tep-stat-label">Assigned</span>
                    </div>
                    <div className="tep-stat">
                      <span className="tep-stat-value tep-green">{exam.completed_count}</span>
                      <span className="tep-stat-label">Completed</span>
                    </div>
                  </div>
                </div>

                <div className="tep-exam-actions">
                  <button
                    className="tep-action-btn"
                    type="button"
                    onClick={() => setExpandedId(expandedId === exam.id ? null : exam.id)}
                  >
                    {expandedId === exam.id ? 'Hide Questions' : 'Preview Questions'}
                  </button>
                  <button
                    className="tep-action-btn tep-danger"
                    type="button"
                    onClick={() => handleDelete(exam.id)}
                    disabled={deletingId === exam.id}
                  >
                    {deletingId === exam.id ? 'Deleting…' : 'Delete'}
                  </button>
                </div>

                {expandedId === exam.id && (
                  <div className="tep-questions-preview">
                    {(exam.questions ?? []).map((q, i) => (
                      <div key={i} className="tep-q-row">
                        <span className="tep-q-num">Q{i + 1}</span>
                        <div className="tep-q-content">
                          <p className="tep-q-text">{q.question}</p>
                          <div className="tep-q-options">
                            {q.options?.map((opt, oi) => (
                              <span
                                key={oi}
                                className={`tep-q-opt ${oi === q.correct_index ? 'correct' : ''}`}
                              >
                                {String.fromCharCode(65 + oi)}: {opt}
                                {oi === q.correct_index && ' ✓'}
                              </span>
                            ))}
                          </div>
                          {q.explanation && (
                            <p className="tep-q-explanation">{q.explanation}</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {showGenerateModal && (
          <GenerateMockExamModal
            courses={courses}
            onClose={() => setShowGenerateModal(false)}
            onExamSaved={(exam) => {
              setExams(prev => [exam, ...prev]);
            }}
          />
        )}
      </div>
    </DashboardLayout>
  );
}

export default TeacherExamsPage;
