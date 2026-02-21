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
import { Breadcrumb } from '../components/Breadcrumb';
import './StudyGuidePage.css';

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

  return (
    <div className="study-guide-page">
      <div className="study-guide-header">
        <Breadcrumb items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Materials', to: '/course-materials' },
          { label: guide?.title || 'Study Guide' },
        ]} />
        <div className="header-actions">
          <CourseAssignSelect
            guideId={guide.id}
            currentCourseId={guide.course_id}
            onCourseChanged={(courseId) => setGuide({ ...guide, course_id: courseId })}
          />
          <button className="print-btn" onClick={() => window.print()}>Print</button>
          <button
            className="print-btn"
            onClick={async () => {
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
            }}
          >
            Regenerate
          </button>
          <button className="delete-btn" onClick={handleDelete}>Delete</button>
          <button className="print-btn" onClick={() => setShowTaskModal(true)} title="Create task">&#128203; + Task</button>
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
        <h1>{guide.title}</h1>
        <p className="guide-meta">
          {guide.version > 1 && <span style={{ background: '#e3f2fd', color: '#1565c0', padding: '1px 6px', borderRadius: '8px', fontSize: '0.85rem', marginRight: '0.5rem' }}>v{guide.version}</span>}
          Created: {new Date(guide.created_at).toLocaleDateString()}
        </p>
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
