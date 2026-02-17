import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { ListSkeleton } from '../components/Skeleton';
import { faqApi, type FAQQuestionItem } from '../api/client';
import './FAQPage.css';

const CATEGORIES = [
  { value: '', label: 'All' },
  { value: 'getting-started', label: 'Getting Started' },
  { value: 'google-classroom', label: 'Google Classroom' },
  { value: 'study-tools', label: 'Study Tools' },
  { value: 'account', label: 'Account' },
  { value: 'courses', label: 'Courses' },
  { value: 'messaging', label: 'Messaging' },
  { value: 'tasks', label: 'Tasks' },
  { value: 'other', label: 'Other' },
];

export function FAQPage() {
  const navigate = useNavigate();
  const [questions, setQuestions] = useState<FAQQuestionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState('');
  const [search, setSearch] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [formTitle, setFormTitle] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formCat, setFormCat] = useState('other');
  const [saving, setSaving] = useState(false);

  const loadQuestions = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | boolean> = {};
      if (category) params.category = category;
      if (search.trim()) params.search = search.trim();
      const data = await faqApi.listQuestions(params);
      setQuestions(data);
    } finally {
      setLoading(false);
    }
  }, [category, search]);

  useEffect(() => {
    const timer = setTimeout(() => loadQuestions(), search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [loadQuestions, search]);

  const handleAsk = async () => {
    if (!formTitle.trim()) return;
    setSaving(true);
    try {
      await faqApi.createQuestion({
        title: formTitle.trim(),
        description: formDesc.trim() || undefined,
        category: formCat,
      });
      setShowModal(false);
      setFormTitle('');
      setFormDesc('');
      setFormCat('other');
      loadQuestions();
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout welcomeSubtitle="Find answers and ask questions">
      <div className="faq-page">
        <div className="faq-header">
          <h1>FAQ / Knowledge Base</h1>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>
            Ask a Question
          </button>
        </div>

        <div className="faq-filters">
          <input
            type="text"
            className="faq-search"
            placeholder="Search questions..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="faq-categories">
            {CATEGORIES.map((c) => (
              <button
                key={c.value}
                className={`faq-cat-pill${category === c.value ? ' active' : ''}`}
                onClick={() => setCategory(c.value)}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <ListSkeleton rows={6} />
        ) : questions.length === 0 ? (
          <div className="faq-empty">
            No questions found. Be the first to ask!
          </div>
        ) : (
          <div className="faq-list">
            {questions.map((q) => (
              <button
                key={q.id}
                className="faq-card"
                onClick={() => navigate(`/faq/${q.id}`)}
              >
                <div className="faq-card-header">
                  {q.is_pinned && <span className="faq-badge pinned">Pinned</span>}
                  <span className={`faq-badge cat-${q.category}`}>
                    {q.category.replace(/-/g, ' ')}
                  </span>
                  {q.status === 'answered' && (
                    <span className="faq-badge answered">Answered</span>
                  )}
                </div>
                <h3 className="faq-card-title">{q.title}</h3>
                {q.description && (
                  <p className="faq-card-desc">{q.description.slice(0, 120)}{q.description.length > 120 ? '...' : ''}</p>
                )}
                <div className="faq-card-meta">
                  <span>{q.approved_answer_count} answer{q.approved_answer_count !== 1 ? 's' : ''}</span>
                  <span>{q.view_count} view{q.view_count !== 1 ? 's' : ''}</span>
                  <span>by {q.creator_name}</span>
                </div>
              </button>
            ))}
          </div>
        )}

        {showModal && (
          <div className="modal-overlay" onClick={() => setShowModal(false)}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h2>Ask a Question</h2>
                <button className="modal-close" onClick={() => setShowModal(false)}>&times;</button>
              </div>
              <div className="form-group">
                <label>Question</label>
                <input
                  type="text"
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  placeholder="What would you like to know?"
                  autoFocus
                />
              </div>
              <div className="form-group">
                <label>Details (optional)</label>
                <textarea
                  value={formDesc}
                  onChange={(e) => setFormDesc(e.target.value)}
                  placeholder="Add more context..."
                  rows={3}
                />
              </div>
              <div className="form-group">
                <label>Category</label>
                <select value={formCat} onChange={(e) => setFormCat(e.target.value)}>
                  {CATEGORIES.filter((c) => c.value).map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>
              <div className="modal-actions">
                <button className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                <button className="btn btn-primary" onClick={handleAsk} disabled={saving || !formTitle.trim()}>
                  {saving ? 'Submitting...' : 'Submit Question'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
