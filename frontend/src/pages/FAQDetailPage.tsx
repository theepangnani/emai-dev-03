import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { ListSkeleton } from '../components/Skeleton';
import { useAuth } from '../context/AuthContext';
import { faqApi, type FAQQuestionDetail, type FAQAnswerItem } from '../api/client';
import './FAQDetailPage.css';

export function FAQDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [question, setQuestion] = useState<FAQQuestionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [answerText, setAnswerText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [actionLoading, setActionLoading] = useState<Record<number, boolean>>({});

  const loadQuestion = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await faqApi.getQuestion(Number(id));
      setQuestion(data);
    } catch {
      navigate('/faq');
    } finally {
      setLoading(false);
    }
  }, [id, navigate]);

  useEffect(() => {
    loadQuestion();
  }, [loadQuestion]);

  const handleSubmitAnswer = async () => {
    if (!id || answerText.trim().length < 10) return;
    setSubmitting(true);
    try {
      await faqApi.submitAnswer(Number(id), { content: answerText.trim() });
      setAnswerText('');
      loadQuestion();
    } finally {
      setSubmitting(false);
    }
  };

  const handleApprove = async (answerId: number) => {
    setActionLoading((prev) => ({ ...prev, [answerId]: true }));
    try {
      await faqApi.approveAnswer(answerId);
      loadQuestion();
    } finally {
      setActionLoading((prev) => ({ ...prev, [answerId]: false }));
    }
  };

  const handleReject = async (answerId: number) => {
    setActionLoading((prev) => ({ ...prev, [answerId]: true }));
    try {
      await faqApi.rejectAnswer(answerId);
      loadQuestion();
    } finally {
      setActionLoading((prev) => ({ ...prev, [answerId]: false }));
    }
  };

  const handleMarkOfficial = async (answerId: number) => {
    setActionLoading((prev) => ({ ...prev, [answerId]: true }));
    try {
      await faqApi.markOfficial(answerId);
      loadQuestion();
    } finally {
      setActionLoading((prev) => ({ ...prev, [answerId]: false }));
    }
  };

  const handleTogglePin = async () => {
    if (!question) return;
    try {
      await faqApi.pinQuestion(question.id, !question.is_pinned);
      loadQuestion();
    } catch {
      // silently fail
    }
  };

  const handleDeleteAnswer = async (answerId: number) => {
    if (!confirm('Delete this answer?')) return;
    setActionLoading((prev) => ({ ...prev, [answerId]: true }));
    try {
      await faqApi.deleteAnswer(answerId);
      loadQuestion();
    } finally {
      setActionLoading((prev) => ({ ...prev, [answerId]: false }));
    }
  };

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Loading question...">
        <div className="faq-detail">
          <ListSkeleton rows={4} />
        </div>
      </DashboardLayout>
    );
  }

  if (!question) return null;

  const approvedAnswers = question.answers.filter((a) => a.status === 'approved');
  const pendingAnswers = question.answers.filter((a) => a.status === 'pending');
  const rejectedAnswers = question.answers.filter((a) => a.status === 'rejected');

  // Sort: official first, then by date
  const sortedApproved = [...approvedAnswers].sort((a, b) => {
    if (a.is_official !== b.is_official) return a.is_official ? -1 : 1;
    return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
  });

  return (
    <DashboardLayout welcomeSubtitle="FAQ">
      <div className="faq-detail">
        <button className="faq-back-btn" onClick={() => navigate('/faq')}>
          &larr; Back to FAQ
        </button>

        {/* Question card */}
        <div className="faq-question-card">
          <div className="faq-question-badges">
            {question.is_pinned && <span className="faq-badge pinned">Pinned</span>}
            <span className={`faq-badge cat-${question.category}`}>
              {question.category.replace(/-/g, ' ')}
            </span>
            {question.status === 'answered' && (
              <span className="faq-badge answered">Answered</span>
            )}
            {question.status === 'closed' && (
              <span className="faq-badge closed">Closed</span>
            )}
          </div>
          <h2 className="faq-question-title">{question.title}</h2>
          {question.description && (
            <p className="faq-question-desc">{question.description}</p>
          )}
          <div className="faq-question-meta">
            <span>Asked by {question.creator_name}</span>
            <span>{new Date(question.created_at).toLocaleDateString()}</span>
            <span>{question.view_count} views</span>
          </div>
          {isAdmin && (
            <div className="faq-admin-controls">
              <button className="btn btn-sm btn-secondary" onClick={handleTogglePin}>
                {question.is_pinned ? 'Unpin' : 'Pin'}
              </button>
            </div>
          )}
        </div>

        {/* Approved answers */}
        <h3 className="faq-answers-heading">
          {approvedAnswers.length} Answer{approvedAnswers.length !== 1 ? 's' : ''}
        </h3>

        {sortedApproved.length === 0 && (
          <p className="faq-no-answers">No answers yet. Be the first to help!</p>
        )}

        {sortedApproved.map((answer) => (
          <AnswerCard
            key={answer.id}
            answer={answer}
            isAdmin={isAdmin}
            actionLoading={actionLoading[answer.id]}
            onMarkOfficial={() => handleMarkOfficial(answer.id)}
            onDelete={() => handleDeleteAnswer(answer.id)}
          />
        ))}

        {/* Pending answers (admin only) */}
        {isAdmin && pendingAnswers.length > 0 && (
          <>
            <h3 className="faq-answers-heading pending-heading">
              {pendingAnswers.length} Pending Answer{pendingAnswers.length !== 1 ? 's' : ''}
            </h3>
            {pendingAnswers.map((answer) => (
              <AnswerCard
                key={answer.id}
                answer={answer}
                isAdmin={isAdmin}
                isPending
                actionLoading={actionLoading[answer.id]}
                onApprove={() => handleApprove(answer.id)}
                onReject={() => handleReject(answer.id)}
                onDelete={() => handleDeleteAnswer(answer.id)}
              />
            ))}
          </>
        )}

        {/* Rejected answers (admin only) */}
        {isAdmin && rejectedAnswers.length > 0 && (
          <>
            <h3 className="faq-answers-heading rejected-heading">
              {rejectedAnswers.length} Rejected
            </h3>
            {rejectedAnswers.map((answer) => (
              <AnswerCard
                key={answer.id}
                answer={answer}
                isAdmin={isAdmin}
                isRejected
                actionLoading={actionLoading[answer.id]}
                onApprove={() => handleApprove(answer.id)}
                onDelete={() => handleDeleteAnswer(answer.id)}
              />
            ))}
          </>
        )}

        {/* Submit answer form */}
        {question.status !== 'closed' && (
          <div className="faq-answer-form">
            <h3>Your Answer</h3>
            <textarea
              value={answerText}
              onChange={(e) => setAnswerText(e.target.value)}
              placeholder="Write your answer (minimum 10 characters)..."
              rows={4}
            />
            <div className="faq-answer-form-actions">
              <span className="faq-char-count">
                {answerText.length < 10 ? `${10 - answerText.length} more characters needed` : ''}
              </span>
              <button
                className="btn btn-primary"
                onClick={handleSubmitAnswer}
                disabled={submitting || answerText.trim().length < 10}
              >
                {submitting ? 'Submitting...' : 'Submit Answer'}
              </button>
            </div>
            {!isAdmin && (
              <p className="faq-answer-note">Your answer will be reviewed before being published.</p>
            )}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

/* ── Answer Card component ── */

interface AnswerCardProps {
  answer: FAQAnswerItem;
  isAdmin: boolean;
  isPending?: boolean;
  isRejected?: boolean;
  actionLoading?: boolean;
  onApprove?: () => void;
  onReject?: () => void;
  onMarkOfficial?: () => void;
  onDelete?: () => void;
}

function AnswerCard({
  answer,
  isAdmin,
  isPending,
  isRejected,
  actionLoading,
  onApprove,
  onReject,
  onMarkOfficial,
  onDelete,
}: AnswerCardProps) {
  return (
    <div
      className={`faq-answer-card${answer.is_official ? ' official' : ''}${isPending ? ' pending' : ''}${isRejected ? ' rejected' : ''}`}
    >
      {answer.is_official && <div className="faq-official-badge">Official Answer</div>}
      {isPending && <div className="faq-pending-badge">Pending Review</div>}
      {isRejected && <div className="faq-rejected-badge">Rejected</div>}

      <div className="faq-answer-content">{answer.content}</div>

      <div className="faq-answer-meta">
        <span>By {answer.creator_name}</span>
        <span>{new Date(answer.created_at).toLocaleDateString()}</span>
        {answer.reviewer_name && (
          <span>Reviewed by {answer.reviewer_name}</span>
        )}
      </div>

      {isAdmin && (
        <div className="faq-answer-actions">
          {isPending && onApprove && (
            <button
              className="btn btn-sm btn-success"
              onClick={onApprove}
              disabled={actionLoading}
            >
              Approve
            </button>
          )}
          {isPending && onReject && (
            <button
              className="btn btn-sm btn-danger"
              onClick={onReject}
              disabled={actionLoading}
            >
              Reject
            </button>
          )}
          {isRejected && onApprove && (
            <button
              className="btn btn-sm btn-success"
              onClick={onApprove}
              disabled={actionLoading}
            >
              Approve
            </button>
          )}
          {!isPending && !isRejected && onMarkOfficial && (
            <button
              className="btn btn-sm btn-secondary"
              onClick={onMarkOfficial}
              disabled={actionLoading}
            >
              {answer.is_official ? 'Remove Official' : 'Mark Official'}
            </button>
          )}
          {onDelete && (
            <button
              className="btn btn-sm btn-danger"
              onClick={onDelete}
              disabled={actionLoading}
            >
              Delete
            </button>
          )}
        </div>
      )}
    </div>
  );
}
