import { useState, useEffect, useRef, Suspense } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { studyApi } from '../api/client';
import type { StudyGuide } from '../api/client';
import { CreateTaskModal } from '../components/CreateTaskModal';
import { MaterialContextMenu } from '../components/MaterialContextMenu';
import { EditStudyGuideModal } from '../components/EditStudyGuideModal';
import { ContentCard, MarkdownBody } from '../components/ContentCard';
import { useConfirm } from '../components/ConfirmModal';
import { FAQErrorHint } from '../components/FAQErrorHint';
import { extractFaqCode } from '../utils/faqUtils';
import { downloadAsPdf } from '../utils/exportUtils';
import { PageNav } from '../components/PageNav';
import { useAIUsage } from '../hooks/useAIUsage';
import { AILimitRequestModal } from '../components/AILimitRequestModal';
import { NotesFAB } from '../components/NotesFAB';
import { NotesPanel } from '../components/NotesPanel';
import { SelectionTooltip } from '../components/SelectionTooltip';
import { useTextSelection } from '../hooks/useTextSelection';
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
  const [showEditModal, setShowEditModal] = useState(false);
  const [showTaskPrompt, setShowTaskPrompt] = useState(false);
  const [exporting, setExporting] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const { confirm, confirmModal } = useConfirm();
  const { atLimit, remaining, invalidate: refreshAIUsage } = useAIUsage();
  const [showLimitModal, setShowLimitModal] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);
  const [appendText, setAppendText] = useState<string | null>(null);
  const { selection, clearSelection } = useTextSelection(contentRef);

  const handleAddToNotes = () => {
    if (!selection) return;
    setAppendText(selection.text);
    setNotesOpen(true);
    clearSelection();
    window.getSelection()?.removeAllRanges();
  };

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
    if (atLimit) {
      setShowLimitModal(true);
      return;
    }
    const ok = await confirm({
      title: 'Regenerate Study Guide',
      message: `This will use 1 AI credit. You have ${remaining} remaining. Continue?`,
      confirmLabel: 'Regenerate',
    });
    if (!ok) return;
    try {
      const result = await studyApi.generateGuide({
        title: guide.title.replace(/^Study Guide: /, ''),
        content: guide.content,
        regenerate_from_id: guide.id,
      });
      refreshAIUsage();
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
        { label: 'Class Materials', to: '/course-materials' },
        ...(guide?.course_content_id
          ? [{ label: guide.title.replace(/^Study Guide:\s*/i, ''), to: `/course-materials/${guide.course_content_id}` }]
          : []),
        { label: 'Study Guide' },
      ]} />

      {/* Header card */}
      <div className="sg-detail-header">
        <div className="sg-title-row">
          <h2>{guide.title}</h2>
          <MaterialContextMenu items={[
            { label: 'Create Task', icon: <svg width="16" height="16" viewBox="0 0 20 20" fill="none"><rect x="3" y="2" width="14" height="16" rx="2" stroke="currentColor" strokeWidth="1.6"/><path d="M7 7h6M7 10.5h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/><circle cx="14.5" cy="14.5" r="4.5" fill="var(--color-accent-strong, #2a9fa8)"/><path d="M14.5 12.5v4M12.5 14.5h4" stroke="#fff" strokeWidth="1.4" strokeLinecap="round"/></svg>, onClick: () => setShowTaskModal(true) },
            { label: 'Edit Class Material', icon: <svg width="16" height="16" viewBox="0 0 20 20" fill="none"><path d="M13.586 3.586a2 2 0 112.828 2.828l-9.5 9.5L3 17l1.086-3.914 9.5-9.5z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>, onClick: () => setShowEditModal(true) },
          ]} />
        </div>
        <div className="sg-meta-row">
          <span className="sg-type-badge">{guideTypeLabel}</span>
          {guide.version > 1 && <span className="sg-version-badge">v{guide.version}</span>}
          <span className="sg-date">{new Date(guide.created_at).toLocaleDateString()}</span>
          <div className="sg-icon-actions">
            {/* Notes FAB at bottom-right replaces inline toggle */}
            <button className="sg-icon-btn" title="Regenerate" aria-label="Regenerate study guide" onClick={handleRegenerate}>&#8635;</button>
            <button className="sg-icon-btn" title="Print" aria-label="Print study guide" onClick={() => window.print()}>&#128424;</button>
            <button className="sg-icon-btn" title="Download PDF" aria-label="Download PDF" disabled={exporting} onClick={async () => { if (!contentRef.current) return; setExporting(true); try { await downloadAsPdf(contentRef.current, guide.title || 'study-guide'); } finally { setExporting(false); } }}>{exporting ? '\u23F3' : '\u{1F4E5}'}</button>
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

      <div ref={contentRef}>
        <ContentCard>
          <Suspense fallback={<div className="content-card-render-loading">Formatting study guide...</div>}>
            <MarkdownBody content={guide.content} />
          </Suspense>
        </ContentCard>
      </div>
      <CreateTaskModal
        open={showTaskModal}
        onClose={() => setShowTaskModal(false)}
        prefillTitle={`Review: ${guide.title}`}
        studyGuideId={guide.id}
        courseId={guide.course_id ?? undefined}
        linkedEntityLabel={`Study Guide: ${guide.title}`}
      />
      {showEditModal && (
        <EditStudyGuideModal
          guide={guide}
          onClose={() => setShowEditModal(false)}
          onSaved={(updated) => { setGuide(updated); setShowEditModal(false); }}
        />
      )}
      {confirmModal}
      <AILimitRequestModal open={showLimitModal} onClose={() => setShowLimitModal(false)} />

      {/* Contextual notes: selection tooltip + FAB + panel */}
      {selection && !notesOpen && (
        <SelectionTooltip rect={selection.rect} visible onAddToNotes={handleAddToNotes} />
      )}
      {guide.course_content_id && (
        <>
          <NotesFAB courseContentId={guide.course_content_id} isOpen={notesOpen} onToggle={() => setNotesOpen(!notesOpen)} />
          <NotesPanel
            courseContentId={guide.course_content_id}
            isOpen={notesOpen}
            onClose={() => setNotesOpen(false)}
            appendText={appendText}
            onAppendConsumed={() => setAppendText(null)}
          />
        </>
      )}
    </div>
  );
}
