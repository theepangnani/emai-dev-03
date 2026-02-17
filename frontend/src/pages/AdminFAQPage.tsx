import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { ListSkeleton } from '../components/Skeleton';
import { faqApi, type FAQQuestionItem, type FAQAnswerItem } from '../api/client';
import './AdminFAQPage.css';

const CATEGORIES = [
  { value: 'getting-started', label: 'Getting Started' },
  { value: 'google-classroom', label: 'Google Classroom' },
  { value: 'study-tools', label: 'Study Tools' },
  { value: 'account', label: 'Account' },
  { value: 'courses', label: 'Courses' },
  { value: 'messaging', label: 'Messaging' },
  { value: 'tasks', label: 'Tasks' },
  { value: 'other', label: 'Other' },
];

type Tab = 'pending' | 'all' | 'create';

export function AdminFAQPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>('pending');

  // Pending answers
  const [pending, setPending] = useState<FAQAnswerItem[]>([]);
  const [pendingLoading, setPendingLoading] = useState(false);

  // All questions
  const [questions, setQuestions] = useState<FAQQuestionItem[]>([]);
  const [questionsLoading, setQuestionsLoading] = useState(false);

  // Create official FAQ form
  const [formTitle, setFormTitle] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formCat, setFormCat] = useState('other');
  const [formAnswer, setFormAnswer] = useState('');
  const [formOfficial, setFormOfficial] = useState(true);
  const [creating, setCreating] = useState(false);
  const [createResult, setCreateResult] = useState('');

  // Action loading
  const [actionLoading, setActionLoading] = useState<Record<number, boolean>>({});

  const loadPending = useCallback(async () => {
    setPendingLoading(true);
    try {
      const data = await faqApi.listPendingAnswers();
      setPending(data);
    } finally {
      setPendingLoading(false);
    }
  }, []);

  const loadQuestions = useCallback(async () => {
    setQuestionsLoading(true);
    try {
      const data = await faqApi.listQuestions({ limit: 100 });
      setQuestions(data);
    } finally {
      setQuestionsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tab === 'pending') loadPending();
    if (tab === 'all') loadQuestions();
  }, [tab, loadPending, loadQuestions]);

  const handleApprove = async (answerId: number) => {
    setActionLoading((prev) => ({ ...prev, [answerId]: true }));
    try {
      await faqApi.approveAnswer(answerId);
      loadPending();
    } finally {
      setActionLoading((prev) => ({ ...prev, [answerId]: false }));
    }
  };

  const handleReject = async (answerId: number) => {
    setActionLoading((prev) => ({ ...prev, [answerId]: true }));
    try {
      await faqApi.rejectAnswer(answerId);
      loadPending();
    } finally {
      setActionLoading((prev) => ({ ...prev, [answerId]: false }));
    }
  };

  const handleTogglePin = async (q: FAQQuestionItem) => {
    setActionLoading((prev) => ({ ...prev, [q.id]: true }));
    try {
      await faqApi.pinQuestion(q.id, !q.is_pinned);
      loadQuestions();
    } finally {
      setActionLoading((prev) => ({ ...prev, [q.id]: false }));
    }
  };

  const handleDeleteQuestion = async (q: FAQQuestionItem) => {
    if (!confirm(`Delete "${q.title}"?`)) return;
    setActionLoading((prev) => ({ ...prev, [q.id]: true }));
    try {
      await faqApi.deleteQuestion(q.id);
      loadQuestions();
    } finally {
      setActionLoading((prev) => ({ ...prev, [q.id]: false }));
    }
  };

  const handleCreateOfficial = async () => {
    if (!formTitle.trim() || !formAnswer.trim()) return;
    setCreating(true);
    setCreateResult('');
    try {
      await faqApi.createOfficialQuestion({
        title: formTitle.trim(),
        description: formDesc.trim() || undefined,
        category: formCat,
        answer_content: formAnswer.trim(),
        is_official: formOfficial,
      });
      setCreateResult('Official FAQ created successfully!');
      setFormTitle('');
      setFormDesc('');
      setFormCat('other');
      setFormAnswer('');
      setFormOfficial(true);
    } catch {
      setCreateResult('Failed to create FAQ.');
    } finally {
      setCreating(false);
    }
  };

  return (
    <DashboardLayout welcomeSubtitle="Manage FAQ & Knowledge Base">
      <div className="admin-faq-page">
        <div className="admin-faq-header">
          <h1>Manage FAQ</h1>
          <button className="btn btn-secondary" onClick={() => navigate('/faq')}>
            View Public FAQ
          </button>
        </div>

        <div className="admin-faq-tabs">
          <button
            className={`admin-faq-tab${tab === 'pending' ? ' active' : ''}`}
            onClick={() => setTab('pending')}
          >
            Pending Answers
            {pending.length > 0 && tab !== 'pending' && (
              <span className="admin-faq-tab-count">{pending.length}</span>
            )}
          </button>
          <button
            className={`admin-faq-tab${tab === 'all' ? ' active' : ''}`}
            onClick={() => setTab('all')}
          >
            All Questions
          </button>
          <button
            className={`admin-faq-tab${tab === 'create' ? ' active' : ''}`}
            onClick={() => setTab('create')}
          >
            Create Official FAQ
          </button>
        </div>

        {/* Pending Answers Tab */}
        {tab === 'pending' && (
          <div className="admin-faq-section">
            {pendingLoading ? (
              <ListSkeleton rows={4} />
            ) : pending.length === 0 ? (
              <div className="admin-faq-empty">No pending answers to review.</div>
            ) : (
              <div className="admin-faq-list">
                {pending.map((answer) => (
                  <div key={answer.id} className="admin-faq-pending-card">
                    <div className="admin-faq-pending-meta">
                      <span>Answer by <strong>{answer.creator_name}</strong></span>
                      <span>Question #{answer.question_id}</span>
                      <span>{new Date(answer.created_at).toLocaleDateString()}</span>
                    </div>
                    <div className="admin-faq-pending-content">{answer.content}</div>
                    <div className="admin-faq-pending-actions">
                      <button
                        className="btn btn-sm btn-success"
                        onClick={() => handleApprove(answer.id)}
                        disabled={actionLoading[answer.id]}
                      >
                        Approve
                      </button>
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={() => handleReject(answer.id)}
                        disabled={actionLoading[answer.id]}
                      >
                        Reject
                      </button>
                      <button
                        className="btn btn-sm btn-secondary"
                        onClick={() => navigate(`/faq/${answer.question_id}`)}
                      >
                        View Question
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* All Questions Tab */}
        {tab === 'all' && (
          <div className="admin-faq-section">
            {questionsLoading ? (
              <ListSkeleton rows={6} />
            ) : questions.length === 0 ? (
              <div className="admin-faq-empty">No questions yet.</div>
            ) : (
              <table className="admin-faq-table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Category</th>
                    <th>Status</th>
                    <th>Answers</th>
                    <th>Views</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {questions.map((q) => (
                    <tr key={q.id} className={q.is_pinned ? 'pinned-row' : ''}>
                      <td>
                        <button
                          className="admin-faq-title-link"
                          onClick={() => navigate(`/faq/${q.id}`)}
                        >
                          {q.is_pinned && <span title="Pinned">&#128204; </span>}
                          {q.title}
                        </button>
                      </td>
                      <td>
                        <span className={`faq-badge cat-${q.category}`}>
                          {q.category.replace(/-/g, ' ')}
                        </span>
                      </td>
                      <td>
                        <span className={`faq-badge ${q.status}`}>{q.status}</span>
                      </td>
                      <td>{q.approved_answer_count}</td>
                      <td>{q.view_count}</td>
                      <td>
                        <div className="admin-faq-row-actions">
                          <button
                            className="btn btn-sm btn-secondary"
                            onClick={() => handleTogglePin(q)}
                            disabled={actionLoading[q.id]}
                          >
                            {q.is_pinned ? 'Unpin' : 'Pin'}
                          </button>
                          <button
                            className="btn btn-sm btn-danger"
                            onClick={() => handleDeleteQuestion(q)}
                            disabled={actionLoading[q.id]}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Create Official FAQ Tab */}
        {tab === 'create' && (
          <div className="admin-faq-section">
            <div className="admin-faq-create-form">
              <div className="form-group">
                <label>Question Title</label>
                <input
                  type="text"
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  placeholder="How do I...?"
                />
              </div>
              <div className="form-group">
                <label>Description (optional)</label>
                <textarea
                  value={formDesc}
                  onChange={(e) => setFormDesc(e.target.value)}
                  placeholder="Additional context..."
                  rows={2}
                />
              </div>
              <div className="form-group">
                <label>Category</label>
                <select value={formCat} onChange={(e) => setFormCat(e.target.value)}>
                  {CATEGORIES.map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Answer</label>
                <textarea
                  value={formAnswer}
                  onChange={(e) => setFormAnswer(e.target.value)}
                  placeholder="Write the official answer..."
                  rows={5}
                />
              </div>
              <div className="form-group">
                <label className="admin-faq-checkbox-label">
                  <input
                    type="checkbox"
                    checked={formOfficial}
                    onChange={(e) => setFormOfficial(e.target.checked)}
                  />
                  Mark as Official Answer
                </label>
              </div>
              {createResult && (
                <p className={`admin-faq-create-result${createResult.includes('Failed') ? ' error' : ''}`}>
                  {createResult}
                </p>
              )}
              <div className="admin-faq-create-actions">
                <button
                  className="btn btn-primary"
                  onClick={handleCreateOfficial}
                  disabled={creating || !formTitle.trim() || !formAnswer.trim()}
                >
                  {creating ? 'Creating...' : 'Create FAQ'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
