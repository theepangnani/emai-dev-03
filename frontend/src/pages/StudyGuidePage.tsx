import { useState, useEffect } from 'react';
import type { ReactElement } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import type { Components } from 'react-markdown';
import type { PluggableList } from 'unified';
import { studyApi } from '../api/client';
import type { StudyGuide } from '../api/client';
import { CourseAssignSelect } from '../components/CourseAssignSelect';
import { CreateTaskModal } from '../components/CreateTaskModal';
import './StudyGuidePage.css';

function normalizeGuideContent(content: string) {
  return content
    .replace(/\r\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

type MarkdownRenderer = (props: {
  children: string;
  remarkPlugins?: PluggableList;
  components?: Components;
}) => ReactElement;

function MarkdownGuideBody({ content }: { content: string }) {
  const [Renderer, setRenderer] = useState<MarkdownRenderer | null>(null);
  const [gfmPlugin, setGfmPlugin] = useState<PluggableList | null>(null);

  useEffect(() => {
    let isMounted = true;

    const loadMarkdown = async () => {
      const [{ default: ReactMarkdown }, { default: remarkGfm }] = await Promise.all([
        import('react-markdown'),
        import('remark-gfm'),
      ]);

      if (!isMounted) return;

      setRenderer(() => ReactMarkdown as MarkdownRenderer);
      setGfmPlugin([remarkGfm] as PluggableList);
    };

    loadMarkdown().catch((err) => {
      console.error('Failed to load markdown renderer', err);
    });

    return () => {
      isMounted = false;
    };
  }, []);

  const normalized = normalizeGuideContent(content);

  if (!Renderer || !gfmPlugin) {
    return <div className="guide-render-loading">Formatting study guide...</div>;
  }

  return <Renderer remarkPlugins={gfmPlugin}>{normalized}</Renderer>;
}

export function StudyGuidePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [guide, setGuide] = useState<StudyGuide | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showTaskModal, setShowTaskModal] = useState(false);

  useEffect(() => {
    const fetchGuide = async () => {
      if (!id) return;
      try {
        const data = await studyApi.getGuide(parseInt(id));
        setGuide(data);
      } catch (err) {
        setError('Failed to load study guide');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchGuide();
  }, [id]);

  const handleDelete = async () => {
    if (!guide || !confirm('Are you sure you want to delete this study guide?')) return;
    try {
      await studyApi.deleteGuide(guide.id);
      navigate('/dashboard');
    } catch (err) {
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
        <Link to="/dashboard" className="back-link">Back to Dashboard</Link>
      </div>
    );
  }

  return (
    <div className="study-guide-page">
      <div className="study-guide-header">
        <Link to="/dashboard" className="back-link">&larr; Back to Dashboard</Link>
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
                navigate(`/study/guide/${result.id}`);
              } catch {
                setError('Failed to regenerate');
              }
            }}
          >
            Regenerate
          </button>
          <button className="delete-btn" onClick={handleDelete}>Delete</button>
          <button className="print-btn" onClick={() => setShowTaskModal(true)} title="Create task">&#128203; + Task</button>
        </div>
      </div>

      <div className="study-guide-content">
        <h1>{guide.title}</h1>
        <p className="guide-meta">
          {guide.version > 1 && <span style={{ background: '#e3f2fd', color: '#1565c0', padding: '1px 6px', borderRadius: '8px', fontSize: '0.85rem', marginRight: '0.5rem' }}>v{guide.version}</span>}
          Created: {new Date(guide.created_at).toLocaleDateString()}
        </p>
        <div className="guide-body">
          <MarkdownGuideBody content={guide.content} />
        </div>
      </div>
      <CreateTaskModal
        open={showTaskModal}
        onClose={() => setShowTaskModal(false)}
        prefillTitle={`Review: ${guide.title}`}
        studyGuideId={guide.id}
        courseId={guide.course_id ?? undefined}
        linkedEntityLabel={`Study Guide: ${guide.title}`}
      />
    </div>
  );
}
