import { useState, useEffect, Suspense } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { studyApi } from '../api/client';
import type { StudyGuide } from '../api/client';
import { CourseAssignSelect } from '../components/CourseAssignSelect';
import { CreateTaskModal } from '../components/CreateTaskModal';
import { ContentCard, MarkdownBody } from '../components/ContentCard';
import { useConfirm } from '../components/ConfirmModal';
import { FAQErrorHint } from '../components/FAQErrorHint';
import { extractFaqCode } from '../utils/faqUtils';
import { PageNav } from '../components/PageNav';
import './StudyGuidePage.css';

const GUIDE_TYPE_LABELS: Record<string, string> = {
  study_guide: 'Study Guide',
  quiz: 'Quiz',
  flashcards: 'Flashcards',
};

export function StudyGuidePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [guide, setGuide] = useState<StudyGuide | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [faqCode, setFaqCode] = useState<string | null>(null);
  const [showTaskModal, setShowTaskModal] = useState(false);
  const [showTaskPrompt, setShowTaskPrompt] = useState(false);
  const { confirm, confirmModal } = useConfirm();

  // Detect first-time guide view from navigation state
  const isNewGuide = !!(location.state as any)?.newGuide;

  useEffect(() => {
    const fetchGuide = async () => {
      if (!id) return;
      try {
        const data = await studyApi.getGuide(parseInt(id));
        setGuide(data);
        // Show task prompt for new/regenerated guides
        if (isNewGuide) {
          setShowTaskPrompt(true);
        }
      } catch (err: unknown) {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 404) {
          setError('This study guide no longer exists. It may have been deleted or archived.');
        } else {
          setError('Failed to load study guide. Please try again.');
        }
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchGuide();
  }, [id]);

  const handleDelete = async () => {
    if (!guide) return;
    const ok = await confirm({ title: 'Delete Study Guide', message: 'Are you sure you want to delete this study guide? This cannot be undone.', confirmLabel: 'Delete', variant: 'danger' });
    if (!ok) return;
    try {
      await studyApi.deleteGuide(guide.id);
      navigate('/dashboard');
    } catch {
      setError('Failed to delete study guide');
    }
  };

  const handleRegenerate = async () => {
    if (!guide) return;
    try {
      const result = await studyApi.generateGuide({
        title: guide.title.replace(/^Study Guide: /, ''),
        content: guide.content,
        regenerate_from_id: guide.id,
      });
      navigate(`/study/guide/${result.id}`, { state: { newGuide: true } });
    } catch (err) {
      setError('Failed to regenerate');
      setFaqCode(extractFaqCode(err));
    }
  };

  if (loading) {
    return (
      <div className="study-guide-page">
        <div className="loading">Loading study guide...</div>
      </div>
    );
  }

  if (error || !guide) {
    return (
      <div className="study-guide-page">
        <div className="error">{error || 'Study guide not found'}</div>
        <FAQErrorHint faqCode={faqCode} />
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginTop: '1rem' }}>
          <Link to="/course-materials" className="back-link">View All Study Materials</Link>
          <Link to="/dashboard" className="back-link">Back to Dashboard</Link>
        </div>
      </div>
    );
  }

  const guideTypeLabel = GUIDE_TYPE_LABELS[guide.guide_type] || guide.guide_type;

  return (
    <div className="study-guide-page">
      <PageNav items={[
        { label: 'Home', to: '/dashboard' },
        { label: 'Course Materials', to: '/course-materials' },
        ...(guide?.course_content_id
          ? [{ label: guide.title.replace(/^Study Guide:\s*/i, ''), to: `/course-materials/${guide.course_content_id}` }]
          : []),
        { label: 'Study Guide' },
      ]} />

      {/* Header card */}
      <div className="sg-detail-header">
        <div className="sg-title-row">
          <h2>{guide.title}</h2>
          <CourseAssignSelect
            guideId={guide.id}
            currentCourseId={guide.course_id}
            onCourseChanged={(courseId) => setGuide({ ...guide, course_id: courseId })}
          />
        </div>
        <div className="sg-meta-row">
          <span className="sg-type-badge">{guideTypeLabel}</span>
          {guide.version > 1 && <span className="sg-version-badge">v{guide.version}</span>}
          {guide.source_guide_id != null && (
            <span
              className="sg-shared-content-badge"
              title="Generated from shared content pool — no AI cost"
            >
              <svg width="13" height="13" viewBox="0 0 20 20" fill="none" aria-hidden="true" style={{ marginRight: '4px', verticalAlign: 'middle' }}>
                <path d="M10 2.5a7.5 7.5 0 1 0 7.5 7.5A7.51 7.51 0 0 0 10 2.5zm0 13.33a5.83 5.83 0 1 1 5.83-5.83A5.84 5.84 0 0 1 10 15.83z" fill="currentColor"/>
                <path d="M7 10l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Shared Content
            </span>
          )}
          <span className="sg-date">{new Date(guide.created_at).toLocaleDateString()}</span>
          <div className="sg-icon-actions">
            <button className="sg-icon-btn" title="Create Task" aria-label="Create task" onClick={() => setShowTaskModal(true)}>
              <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <rect x="3" y="2" width="14" height="16" rx="2" stroke="currentColor" strokeWidth="1.6"/>
                <path d="M7 7h6M7 10.5h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
                <circle cx="14.5" cy="14.5" r="4.5" fill="var(--color-accent-strong, #2a9fa8)"/>
                <path d="M14.5 12.5v4M12.5 14.5h4" stroke="#fff" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
            </button>
            <button className="sg-icon-btn" title="Regenerate" aria-label="Regenerate study guide" onClick={handleRegenerate}>&#8635;</button>
            <button className="sg-icon-btn" title="Print" aria-label="Print study guide" onClick={() => window.print()}>&#128424;</button>
            <button className="sg-icon-btn sg-icon-btn-danger" title="Delete" aria-label="Delete study guide" onClick={handleDelete}>&#128465;</button>
          </div>
        </div>
      </div>

      {showTaskPrompt && (
        <div className="task-prompt-banner">
          <span>Want to create a study task for this guide?</span>
          <button onClick={() => { setShowTaskModal(true); setShowTaskPrompt(false); }}>
            Create Task
          </button>
          <button className="skip-btn" onClick={() => setShowTaskPrompt(false)}>
            Skip
          </button>
        </div>
      )}

      <ContentCard>
        <Suspense fallback={<div className="content-card-render-loading">Formatting study guide...</div>}>
          <MarkdownBody content={guide.content} />
        </Suspense>
      </ContentCard>
      <CreateTaskModal
        open={showTaskModal}
        onClose={() => setShowTaskModal(false)}
        prefillTitle={`Review: ${guide.title}`}
        studyGuideId={guide.id}
        courseId={guide.course_id ?? undefined}
        linkedEntityLabel={`Study Guide: ${guide.title}`}
      />
      {confirmModal}
    </div>
  );
}
