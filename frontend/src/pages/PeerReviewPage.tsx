import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import { useAuth } from '../context/AuthContext';
import {
  createPeerReviewAssignment,
  listPeerReviewAssignments,
  submitWork,
  allocateReviewers,
  getMyReviewsToDo,
  submitPeerReview,
  getSubmissionReviews,
  releaseReviews,
  getAssignmentSummary,
  type PeerReviewAssignment,
  type RubricCriterion,
  type ReviewTodoItem,
  type PeerReview,
  type PeerReviewSummary,
} from '../api/peerReview';
import './PeerReviewPage.css';

// ---------------------------------------------------------------------------
// Teacher view
// ---------------------------------------------------------------------------

function TeacherView() {
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [summaryId, setSummaryId] = useState<number | null>(null);
  const [reviewsSubmissionId, setReviewsSubmissionId] = useState<number | null>(null);

  // Form state
  const [form, setForm] = useState({
    title: '',
    instructions: '',
    due_date: '',
    is_anonymous: true,
    max_reviewers_per_student: 2,
    course_id: '',
  });
  const [rubric, setRubric] = useState<RubricCriterion[]>([
    { criterion: '', max_points: 10, description: '' },
  ]);

  const { data: assignments = [] } = useQuery({
    queryKey: ['peer-review-assignments'],
    queryFn: listPeerReviewAssignments,
  });

  const { data: summary = [] } = useQuery({
    queryKey: ['peer-review-summary', summaryId],
    queryFn: () => getAssignmentSummary(summaryId!),
    enabled: summaryId !== null,
  });

  const { data: submissionReviews = [] } = useQuery({
    queryKey: ['peer-review-submission-reviews', reviewsSubmissionId],
    queryFn: () => getSubmissionReviews(reviewsSubmissionId!),
    enabled: reviewsSubmissionId !== null,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createPeerReviewAssignment({
        title: form.title,
        instructions: form.instructions || undefined,
        due_date: form.due_date || undefined,
        is_anonymous: form.is_anonymous,
        max_reviewers_per_student: form.max_reviewers_per_student,
        course_id: form.course_id ? parseInt(form.course_id) : undefined,
        rubric: rubric.filter((r) => r.criterion.trim()),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['peer-review-assignments'] });
      setCreating(false);
      setForm({ title: '', instructions: '', due_date: '', is_anonymous: true, max_reviewers_per_student: 2, course_id: '' });
      setRubric([{ criterion: '', max_points: 10, description: '' }]);
    },
  });

  const allocateMutation = useMutation({
    mutationFn: (id: number) => allocateReviewers(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['peer-review-assignments'] }),
  });

  const releaseMutation = useMutation({
    mutationFn: (id: number) => releaseReviews(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['peer-review-assignments'] }),
  });

  const addRubricRow = () =>
    setRubric([...rubric, { criterion: '', max_points: 10, description: '' }]);

  const removeRubricRow = (idx: number) =>
    setRubric(rubric.filter((_, i) => i !== idx));

  const updateRubricRow = (idx: number, field: keyof RubricCriterion, value: string | number) =>
    setRubric(rubric.map((r, i) => (i === idx ? { ...r, [field]: value } : r)));

  return (
    <div className="peer-review-page">
      <div className="peer-review-header">
        <h2>Peer Review Assignments</h2>
        <button className="btn-primary" onClick={() => setCreating(!creating)}>
          {creating ? 'Cancel' : '+ New Assignment'}
        </button>
      </div>

      {creating && (
        <div className="peer-review-card">
          <h3>Create Peer Review Assignment</h3>
          <div className="form-group">
            <label>Title *</label>
            <input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="Assignment title"
            />
          </div>
          <div className="form-group">
            <label>Instructions</label>
            <textarea
              value={form.instructions}
              onChange={(e) => setForm({ ...form, instructions: e.target.value })}
              placeholder="What should students write about?"
              rows={4}
            />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Due Date</label>
              <input
                type="datetime-local"
                value={form.due_date}
                onChange={(e) => setForm({ ...form, due_date: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Reviewers per Student</label>
              <input
                type="number"
                min={1}
                max={10}
                value={form.max_reviewers_per_student}
                onChange={(e) =>
                  setForm({ ...form, max_reviewers_per_student: parseInt(e.target.value) || 2 })
                }
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Course ID (optional)</label>
              <input
                value={form.course_id}
                onChange={(e) => setForm({ ...form, course_id: e.target.value })}
                placeholder="e.g. 42"
              />
            </div>
            <div className="form-group form-group-checkbox">
              <label>
                <input
                  type="checkbox"
                  checked={form.is_anonymous}
                  onChange={(e) => setForm({ ...form, is_anonymous: e.target.checked })}
                />
                Anonymous reviews
              </label>
            </div>
          </div>

          {/* Rubric builder */}
          <div className="rubric-section">
            <div className="rubric-section-header">
              <h4>Rubric Criteria</h4>
              <button className="btn-secondary btn-sm" onClick={addRubricRow}>
                + Add Criterion
              </button>
            </div>
            <table className="rubric-table">
              <thead>
                <tr>
                  <th>Criterion</th>
                  <th>Max Points</th>
                  <th>Description</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rubric.map((row, idx) => (
                  <tr key={idx}>
                    <td>
                      <input
                        value={row.criterion}
                        onChange={(e) => updateRubricRow(idx, 'criterion', e.target.value)}
                        placeholder="e.g. Clarity"
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        min={1}
                        value={row.max_points}
                        onChange={(e) =>
                          updateRubricRow(idx, 'max_points', parseInt(e.target.value) || 10)
                        }
                      />
                    </td>
                    <td>
                      <input
                        value={row.description}
                        onChange={(e) => updateRubricRow(idx, 'description', e.target.value)}
                        placeholder="Optional description"
                      />
                    </td>
                    <td>
                      <button
                        className="btn-icon btn-danger-sm"
                        onClick={() => removeRubricRow(idx)}
                        title="Remove criterion"
                      >
                        &times;
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="form-actions">
            <button
              className="btn-primary"
              onClick={() => createMutation.mutate()}
              disabled={!form.title.trim() || createMutation.isPending}
            >
              {createMutation.isPending ? 'Creating...' : 'Create Assignment'}
            </button>
          </div>
          {createMutation.isError && (
            <p className="error-text">Failed to create assignment. Please try again.</p>
          )}
        </div>
      )}

      {/* Assignment list */}
      {assignments.map((a) => (
        <div key={a.id} className="peer-review-card assignment-card">
          <div className="assignment-card-header">
            <div>
              <h3>{a.title}</h3>
              <span className="badge">{a.reviews_released ? 'Released' : 'In Progress'}</span>
              {a.is_anonymous && <span className="badge badge-secondary">Anonymous</span>}
            </div>
            <div className="assignment-actions">
              <button
                className="btn-secondary btn-sm"
                onClick={() => allocateMutation.mutate(a.id)}
                disabled={allocateMutation.isPending}
              >
                Allocate Reviewers
              </button>
              {!a.reviews_released && (
                <button
                  className="btn-primary btn-sm"
                  onClick={() => releaseMutation.mutate(a.id)}
                  disabled={releaseMutation.isPending}
                >
                  Release Reviews
                </button>
              )}
              <button
                className="btn-outline btn-sm"
                onClick={() => setSummaryId(summaryId === a.id ? null : a.id)}
              >
                {summaryId === a.id ? 'Hide Summary' : 'View Summary'}
              </button>
            </div>
          </div>

          {a.instructions && <p className="assignment-instructions">{a.instructions}</p>}
          {a.due_date && (
            <p className="assignment-meta">Due: {new Date(a.due_date).toLocaleString()}</p>
          )}

          {/* Rubric display */}
          {a.rubric && a.rubric.length > 0 && (
            <details className="rubric-details">
              <summary>Rubric ({a.rubric.length} criteria)</summary>
              <table className="rubric-table">
                <thead>
                  <tr>
                    <th>Criterion</th>
                    <th>Max Points</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {a.rubric.map((r, i) => (
                    <tr key={i}>
                      <td>{r.criterion}</td>
                      <td>{r.max_points}</td>
                      <td>{r.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          )}

          {/* Summary table */}
          {summaryId === a.id && summary.length > 0 && (
            <SummaryTable summary={summary} rubric={a.rubric} onViewReviews={setReviewsSubmissionId} />
          )}
          {summaryId === a.id && summary.length === 0 && (
            <p className="empty-state">No submissions yet.</p>
          )}
        </div>
      ))}

      {assignments.length === 0 && !creating && (
        <div className="empty-state-box">
          <p>No peer review assignments yet. Click "New Assignment" to get started.</p>
        </div>
      )}

      {/* Submission reviews modal */}
      {reviewsSubmissionId !== null && (
        <ReviewsModal
          submissionId={reviewsSubmissionId}
          reviews={submissionReviews}
          onClose={() => setReviewsSubmissionId(null)}
        />
      )}
    </div>
  );
}

function SummaryTable({
  summary,
  rubric,
  onViewReviews,
}: {
  summary: PeerReviewSummary[];
  rubric: RubricCriterion[];
  onViewReviews: (submissionId: number) => void;
}) {
  const criteria = rubric.map((r) => r.criterion);

  return (
    <div className="summary-section">
      <h4>Score Summary</h4>
      <div className="summary-table-wrapper">
        <table className="summary-table">
          <thead>
            <tr>
              <th>Student</th>
              <th>Reviews</th>
              {criteria.map((c) => (
                <th key={c}>{c}</th>
              ))}
              <th>Overall %</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {summary.map((row) => (
              <tr key={row.submission_id}>
                <td>{row.author_name}</td>
                <td>{row.review_count}</td>
                {criteria.map((c) => (
                  <td key={c}>{row.criteria_averages[c]?.toFixed(1) ?? '—'}</td>
                ))}
                <td>{row.avg_score !== null ? `${row.avg_score}%` : '—'}</td>
                <td>
                  <button
                    className="btn-outline btn-xs"
                    onClick={() => onViewReviews(row.submission_id)}
                  >
                    Reviews
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ReviewsModal({
  submissionId,
  reviews,
  onClose,
}: {
  submissionId: number;
  reviews: PeerReview[];
  onClose: () => void;
}) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Reviews for Submission #{submissionId}</h3>
          <button className="btn-icon" onClick={onClose}>
            &times;
          </button>
        </div>
        {reviews.length === 0 ? (
          <p className="empty-state">No submitted reviews yet.</p>
        ) : (
          reviews.map((review) => (
            <div key={review.id} className="review-card">
              <div className="review-meta">
                {review.is_anonymous ? (
                  <span className="anon-badge">Anonymous Reviewer</span>
                ) : (
                  <span>Reviewer #{review.reviewer_id}</span>
                )}
                <span className="review-score">
                  Overall: {review.overall_score !== null ? `${review.overall_score}%` : 'N/A'}
                </span>
              </div>
              {review.scores && (
                <div className="criteria-scores">
                  {Object.entries(review.scores).map(([criterion, score]) => (
                    <div key={criterion} className="criterion-score-row">
                      <span className="criterion-name">{criterion}</span>
                      <div className="criterion-bar-container">
                        <div
                          className="criterion-bar"
                          style={{ width: `${Math.min(100, (score / 10) * 100)}%` }}
                        />
                      </div>
                      <span className="criterion-value">{score}</span>
                    </div>
                  ))}
                </div>
              )}
              {review.written_feedback && (
                <div className="written-feedback">
                  <strong>Feedback:</strong>
                  <p>{review.written_feedback}</p>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Student view
// ---------------------------------------------------------------------------

function StudentView() {
  const qc = useQueryClient();
  const [selectedAssignment, setSelectedAssignment] = useState<PeerReviewAssignment | null>(null);
  const [activeTab, setActiveTab] = useState<'submit' | 'review' | 'feedback'>('submit');
  const [submitForm, setSubmitForm] = useState({ title: '', content: '' });
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [reviewTodos, setReviewTodos] = useState<ReviewTodoItem[]>([]);
  const [activeReview, setActiveReview] = useState<ReviewTodoItem | null>(null);
  const [reviewScores, setReviewScores] = useState<Record<string, number>>({});
  const [reviewFeedback, setReviewFeedback] = useState('');
  const [mySubmissionId, setMySubmissionId] = useState<number | null>(null);

  const { data: assignments = [] } = useQuery({
    queryKey: ['peer-review-assignments'],
    queryFn: listPeerReviewAssignments,
  });

  const { data: receivedReviews = [] } = useQuery({
    queryKey: ['peer-review-submission-reviews', mySubmissionId],
    queryFn: () => getSubmissionReviews(mySubmissionId!),
    enabled: mySubmissionId !== null && activeTab === 'feedback',
  });

  const submitWorkMutation = useMutation({
    mutationFn: () =>
      submitWork(selectedAssignment!.id, {
        title: submitForm.title,
        content: submitForm.content,
      }),
    onSuccess: (sub) => {
      setMySubmissionId(sub.id);
      setSubmitSuccess(true);
      qc.invalidateQueries({ queryKey: ['peer-review-assignments'] });
    },
  });

  const submitReviewMutation = useMutation({
    mutationFn: () =>
      submitPeerReview({
        allocation_id: activeReview!.allocation_id,
        scores: reviewScores,
        written_feedback: reviewFeedback || undefined,
      }),
    onSuccess: () => {
      setActiveReview(null);
      setReviewScores({});
      setReviewFeedback('');
      // Refresh the review list
      if (selectedAssignment) {
        getMyReviewsToDo(selectedAssignment.id).then(setReviewTodos);
      }
    },
  });

  const handleSelectAssignment = async (a: PeerReviewAssignment) => {
    setSelectedAssignment(a);
    setActiveTab('submit');
    setSubmitSuccess(false);
    setActiveReview(null);
    try {
      const todos = await getMyReviewsToDo(a.id);
      setReviewTodos(todos);
    } catch {
      setReviewTodos([]);
    }
  };

  const handleStartReview = (item: ReviewTodoItem) => {
    setActiveReview(item);
    // Initialize scores to 0 for each criterion
    if (selectedAssignment?.rubric) {
      const initial: Record<string, number> = {};
      for (const r of selectedAssignment.rubric) {
        initial[r.criterion] = 0;
      }
      setReviewScores(initial);
    }
    setReviewFeedback('');
  };

  return (
    <div className="peer-review-page">
      <h2>Peer Reviews</h2>

      {!selectedAssignment ? (
        <div className="assignment-list">
          {assignments.length === 0 && (
            <div className="empty-state-box">
              <p>No peer review assignments available yet.</p>
            </div>
          )}
          {assignments.map((a) => (
            <div
              key={a.id}
              className="peer-review-card assignment-card clickable"
              onClick={() => handleSelectAssignment(a)}
            >
              <h3>{a.title}</h3>
              {a.instructions && (
                <p className="assignment-instructions">{a.instructions}</p>
              )}
              {a.due_date && (
                <p className="assignment-meta">Due: {new Date(a.due_date).toLocaleString()}</p>
              )}
              <div className="badge-row">
                {a.is_anonymous && <span className="badge badge-secondary">Anonymous</span>}
                {a.reviews_released && <span className="badge badge-success">Feedback Available</span>}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div>
          <button className="btn-back" onClick={() => setSelectedAssignment(null)}>
            &larr; Back to assignments
          </button>
          <h3 className="assignment-title">{selectedAssignment.title}</h3>
          {selectedAssignment.instructions && (
            <p className="assignment-instructions">{selectedAssignment.instructions}</p>
          )}

          {/* Tabs */}
          <div className="tab-bar">
            <button
              className={`tab-btn${activeTab === 'submit' ? ' active' : ''}`}
              onClick={() => setActiveTab('submit')}
            >
              Submit My Work
            </button>
            <button
              className={`tab-btn${activeTab === 'review' ? ' active' : ''}`}
              onClick={() => setActiveTab('review')}
            >
              Review Peers ({reviewTodos.length})
            </button>
            {selectedAssignment.reviews_released && (
              <button
                className={`tab-btn${activeTab === 'feedback' ? ' active' : ''}`}
                onClick={() => setActiveTab('feedback')}
              >
                My Feedback
              </button>
            )}
          </div>

          {/* Submit tab */}
          {activeTab === 'submit' && (
            <div className="peer-review-card">
              {submitSuccess ? (
                <div className="success-box">
                  <p>Your work has been submitted successfully!</p>
                  <button
                    className="btn-secondary"
                    onClick={() => setSubmitSuccess(false)}
                  >
                    Edit submission
                  </button>
                </div>
              ) : (
                <>
                  <div className="form-group">
                    <label>Submission Title *</label>
                    <input
                      value={submitForm.title}
                      onChange={(e) =>
                        setSubmitForm({ ...submitForm, title: e.target.value })
                      }
                      placeholder="Title for your work"
                    />
                  </div>
                  <div className="form-group">
                    <label>Content *</label>
                    <textarea
                      value={submitForm.content}
                      onChange={(e) =>
                        setSubmitForm({ ...submitForm, content: e.target.value })
                      }
                      rows={10}
                      placeholder="Write your response here..."
                    />
                  </div>
                  <div className="form-actions">
                    <button
                      className="btn-primary"
                      onClick={() => submitWorkMutation.mutate()}
                      disabled={
                        !submitForm.title.trim() ||
                        !submitForm.content.trim() ||
                        submitWorkMutation.isPending
                      }
                    >
                      {submitWorkMutation.isPending ? 'Submitting...' : 'Submit Work'}
                    </button>
                  </div>
                  {submitWorkMutation.isError && (
                    <p className="error-text">Submission failed. Please try again.</p>
                  )}
                </>
              )}
            </div>
          )}

          {/* Review tab */}
          {activeTab === 'review' && (
            <div>
              {activeReview ? (
                <ReviewForm
                  item={activeReview}
                  rubric={selectedAssignment.rubric}
                  scores={reviewScores}
                  feedback={reviewFeedback}
                  onScoreChange={(criterion, score) =>
                    setReviewScores({ ...reviewScores, [criterion]: score })
                  }
                  onFeedbackChange={setReviewFeedback}
                  onSubmit={() => submitReviewMutation.mutate()}
                  onCancel={() => setActiveReview(null)}
                  isSubmitting={submitReviewMutation.isPending}
                  isError={submitReviewMutation.isError}
                />
              ) : (
                <div>
                  {reviewTodos.length === 0 ? (
                    <div className="empty-state-box">
                      <p>
                        No reviews assigned yet. The teacher needs to allocate reviewers
                        after submissions close.
                      </p>
                    </div>
                  ) : (
                    reviewTodos.map((item) => (
                      <div key={item.allocation_id} className="peer-review-card review-todo-card">
                        <div className="review-todo-header">
                          <h4>{item.submission_title}</h4>
                          <span
                            className={`badge ${
                              item.review_status === 'submitted'
                                ? 'badge-success'
                                : 'badge-warning'
                            }`}
                          >
                            {item.review_status === 'submitted' ? 'Reviewed' : 'Pending'}
                          </span>
                        </div>
                        <p className="submission-preview">
                          {item.submission_content.slice(0, 200)}
                          {item.submission_content.length > 200 && '...'}
                        </p>
                        <button
                          className="btn-primary btn-sm"
                          onClick={() => handleStartReview(item)}
                        >
                          {item.review_status === 'submitted' ? 'Edit Review' : 'Write Review'}
                        </button>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          )}

          {/* Feedback tab */}
          {activeTab === 'feedback' && (
            <div>
              {receivedReviews.length === 0 ? (
                <div className="empty-state-box">
                  <p>No reviews available yet.</p>
                </div>
              ) : (
                receivedReviews.map((review) => (
                  <div key={review.id} className="peer-review-card review-card">
                    <div className="review-meta">
                      {review.is_anonymous ? (
                        <div className="anon-avatar">A</div>
                      ) : (
                        <span>Reviewer #{review.reviewer_id}</span>
                      )}
                      <span className="review-score">
                        Overall: {review.overall_score !== null ? `${review.overall_score}%` : 'N/A'}
                      </span>
                    </div>
                    {review.scores && (
                      <div className="criteria-scores">
                        {Object.entries(review.scores).map(([criterion, score]) => {
                          const maxPts =
                            selectedAssignment.rubric.find((r) => r.criterion === criterion)
                              ?.max_points ?? 10;
                          return (
                            <div key={criterion} className="criterion-score-row">
                              <span className="criterion-name">{criterion}</span>
                              <div className="criterion-bar-container">
                                <div
                                  className="criterion-bar"
                                  style={{
                                    width: `${Math.min(100, (score / maxPts) * 100)}%`,
                                  }}
                                />
                              </div>
                              <span className="criterion-value">
                                {score}/{maxPts}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                    {review.written_feedback && (
                      <div className="written-feedback">
                        <strong>Feedback:</strong>
                        <p>{review.written_feedback}</p>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ReviewForm({
  item,
  rubric,
  scores,
  feedback,
  onScoreChange,
  onFeedbackChange,
  onSubmit,
  onCancel,
  isSubmitting,
  isError,
}: {
  item: ReviewTodoItem;
  rubric: RubricCriterion[];
  scores: Record<string, number>;
  feedback: string;
  onScoreChange: (criterion: string, score: number) => void;
  onFeedbackChange: (v: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
  isSubmitting: boolean;
  isError: boolean;
}) {
  return (
    <div className="peer-review-card">
      <div className="review-form-header">
        <h4>Reviewing: {item.submission_title}</h4>
        <button className="btn-back btn-sm" onClick={onCancel}>
          &larr; Back
        </button>
      </div>
      <div className="submission-full-text">
        <h5>Submission Content</h5>
        <p>{item.submission_content}</p>
      </div>

      <div className="rubric-scoring">
        <h5>Rubric Scores</h5>
        {rubric.map((criterion) => (
          <div key={criterion.criterion} className="rubric-score-row">
            <div className="rubric-score-info">
              <span className="criterion-name">{criterion.criterion}</span>
              {criterion.description && (
                <span className="criterion-desc">{criterion.description}</span>
              )}
              <span className="criterion-max">Max: {criterion.max_points} pts</span>
            </div>
            <input
              type="number"
              min={0}
              max={criterion.max_points}
              value={scores[criterion.criterion] ?? 0}
              onChange={(e) =>
                onScoreChange(
                  criterion.criterion,
                  Math.min(criterion.max_points, Math.max(0, parseInt(e.target.value) || 0)),
                )
              }
              className="score-input"
            />
          </div>
        ))}
      </div>

      <div className="form-group">
        <label>Written Feedback (optional)</label>
        <textarea
          value={feedback}
          onChange={(e) => onFeedbackChange(e.target.value)}
          rows={5}
          placeholder="Provide constructive feedback on the work..."
        />
      </div>

      <div className="form-actions">
        <button className="btn-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button
          className="btn-primary"
          onClick={onSubmit}
          disabled={isSubmitting || rubric.some((r) => (scores[r.criterion] ?? -1) < 0)}
        >
          {isSubmitting ? 'Submitting...' : 'Submit Review'}
        </button>
      </div>
      {isError && <p className="error-text">Failed to submit review. Please try again.</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page entry point
// ---------------------------------------------------------------------------

export function PeerReviewPage() {
  const { user } = useAuth();
  const isTeacher = user?.role === 'teacher' || user?.role === 'admin';

  return (
    <DashboardLayout welcomeSubtitle="Peer Review Assignments">
      {isTeacher ? <TeacherView /> : <StudentView />}
    </DashboardLayout>
  );
}

export default PeerReviewPage;
