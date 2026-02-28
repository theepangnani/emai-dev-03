import { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { courseContentsApi, studyApi, type CourseContentItem, type StudyGuide, type CourseContentUpdateResponse, type ResolvedStudent } from '../api/client';
import { tasksApi, type TaskItem } from '../api/tasks';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { CreateTaskModal } from '../components/CreateTaskModal';
import { useConfirm } from '../components/ConfirmModal';
import { DetailSkeleton } from '../components/Skeleton';
import { FAQErrorHint } from '../components/FAQErrorHint';
import { extractFaqCode } from '../utils/faqUtils';
import { PageNav } from '../components/PageNav';
import { DocumentTab } from './course-material/DocumentTab';
import { StudyGuideTab } from './course-material/StudyGuideTab';
import { QuizTab } from './course-material/QuizTab';
import { FlashcardsTab } from './course-material/FlashcardsTab';
import { ReplaceDocumentModal } from './course-material/ReplaceDocumentModal';
import { EditMaterialModal } from '../components/EditMaterialModal';
import './CourseMaterialDetailPage.css';

type TabKey = 'document' | 'guide' | 'quiz' | 'flashcards';

export function CourseMaterialDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { confirm, confirmModal } = useConfirm();
  const { user } = useAuth();
  const isParent = user?.role === 'parent' || (user?.roles ?? []).includes('parent');

  const [content, setContent] = useState<CourseContentItem | null>(null);
  const [guides, setGuides] = useState<StudyGuide[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [faqCode, setFaqCode] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>('document');
  const [generating, setGenerating] = useState<string | null>(null);

  const [showTaskModal, setShowTaskModal] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [showReplaceModal, setShowReplaceModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [resolvedStudent, setResolvedStudent] = useState<ResolvedStudent | null>(null);
  const [focusPrompt, setFocusPrompt] = useState('');

  const [toast, setToast] = useState<string | null>(null);
  const [showRegenPrompt, setShowRegenPrompt] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<'uploading' | 'success' | 'error' | null>(null);
  const [linkedTasks, setLinkedTasks] = useState<Record<number, TaskItem[]>>({});

  const contentId = parseInt(id || '0');

  const loadData = useCallback(async () => {
    if (!contentId) return;
    try {
      setError(null);
      const [cc, allGuides] = await Promise.all([
        courseContentsApi.get(contentId),
        studyApi.listGuides({ course_content_id: contentId }),
      ]);
      setContent(cc);
      setGuides(allGuides);
      // Fetch linked tasks for each guide
      const taskMap: Record<number, TaskItem[]> = {};
      await Promise.all(
        allGuides.map(async (g) => {
          try {
            taskMap[g.id] = await tasksApi.list({ study_guide_id: g.id });
          } catch { /* ignore */ }
        })
      );
      setLinkedTasks(taskMap);
    } catch {
      setError('Failed to load class material');
    } finally {
      setLoading(false);
    }
  }, [contentId]);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    if (!isParent || !content?.course_id) return;
    studyApi.resolveStudent({ course_id: content.course_id })
      .then(setResolvedStudent)
      .catch(() => {});
  }, [isParent, content?.course_id]);

  const studyGuide = guides.find(g => g.guide_type === 'study_guide');
  const quiz = guides.find(g => g.guide_type === 'quiz');
  const flashcardSet = guides.find(g => g.guide_type === 'flashcards');

  const hasSourceContent = !!(content?.text_content || content?.description);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  const handleGenerate = async (type: 'study_guide' | 'quiz' | 'flashcards') => {
    if (!content) return;
    const labels = { study_guide: 'Study Guide', quiz: 'Practice Quiz', flashcards: 'Flashcards' };
    const ok = await confirm({
      title: `Generate ${labels[type]}`,
      message: `Generate a ${labels[type].toLowerCase()} from "${content.title}"? This will use AI credits.`,
      confirmLabel: 'Generate',
    });
    if (!ok) return;

    setGenerating(type);
    setActiveTab(type === 'study_guide' ? 'guide' : type);
    try {
      const fp = focusPrompt.trim() || undefined;
      if (type === 'study_guide') {
        await studyApi.generateGuide({
          course_content_id: contentId,
          course_id: content.course_id,
          title: content.title,
          content: content.text_content || content.description || '',
          focus_prompt: fp,
        });
      } else if (type === 'quiz') {
        await studyApi.generateQuiz({
          course_content_id: contentId,
          course_id: content.course_id,
          topic: content.title,
          content: content.text_content || content.description || '',
          num_questions: 5,
          focus_prompt: fp,
        });
      } else {
        await studyApi.generateFlashcards({
          course_content_id: contentId,
          course_id: content.course_id,
          topic: content.title,
          content: content.text_content || content.description || '',
          num_cards: 10,
          focus_prompt: fp,
        });
      }
      await loadData();
      setActiveTab(type === 'study_guide' ? 'guide' : type);
      // Show toast if tasks were auto-created
      const updatedGuides = await studyApi.listGuides({ course_content_id: contentId });
      const newGuide = updatedGuides.find(g => g.guide_type === type);
      if (newGuide) {
        const tasks = await tasksApi.list({ study_guide_id: newGuide.id }).catch(() => []);
        if (tasks.length > 0) {
          const t = tasks[0];
          const dueStr = t.due_date ? ` (due ${new Date(t.due_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })})` : '';
          showToast(`Task created: ${t.title}${dueStr}`);
        }
      }
    } catch (err) {
      setError(`Failed to generate ${labels[type].toLowerCase()}`);
      setFaqCode(extractFaqCode(err));
    } finally {
      setGenerating(null);
    }
  };

  const handleDeleteGuide = async (guide: StudyGuide) => {
    const ok = await confirm({
      title: 'Archive Study Material',
      message: `Archive "${guide.title}"? You can restore it later from the archive.`,
      confirmLabel: 'Archive',
    });
    if (!ok) return;
    try {
      await studyApi.deleteGuide(guide.id);
      await loadData();
      showToast('Study material archived');
    } catch {
      showToast('Failed to archive study material');
    }
  };

  const handleArchiveContent = async () => {
    if (!content) return;
    const ok = await confirm({
      title: 'Archive Material',
      message: `Archive "${content.title}"? You can restore it later from the archive.`,
      confirmLabel: 'Archive',
    });
    if (!ok) return;
    try {
      await courseContentsApi.delete(content.id);
      navigate('/course-materials');
    } catch {
      setError('Failed to archive material');
    }
  };

  const handleDownload = async () => {
    if (!content) return;
    setDownloading(true);
    try {
      await courseContentsApi.download(content.id, content.original_filename || undefined);
    } catch {
      setError('Failed to download document');
    } finally {
      setDownloading(false);
    }
  };

  const handleContentUpdated = (result: CourseContentUpdateResponse) => {
    setContent(result);
  };

  const handleRegenerate = async (type: 'study_guide' | 'quiz' | 'flashcards') => {
    setShowRegenPrompt(false);
    await handleGenerate(type);
  };

  if (loading) return <DashboardLayout showBackButton><DetailSkeleton /></DashboardLayout>;
  if (error || !content) return (
    <DashboardLayout showBackButton>
      <div className="cm-error">
        <p>{error || 'Content not found'}</p>
        <FAQErrorHint faqCode={faqCode} />
        <Link to="/course-materials" className="cm-back-link">Back to Class Materials</Link>
      </div>
    </DashboardLayout>
  );

  const tabs: { key: TabKey; label: string; hasContent: boolean }[] = [
    { key: 'document', label: 'Original Document', hasContent: !!(content.text_content || content.description || content.has_file) },
    { key: 'guide', label: 'Study Guide', hasContent: !!studyGuide },
    { key: 'quiz', label: 'Quiz', hasContent: !!quiz },
    { key: 'flashcards', label: 'Flashcards', hasContent: !!flashcardSet },
  ];

  return (
    <DashboardLayout showBackButton>
      <div className="cm-detail-page">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Course Materials', to: '/course-materials' },
          { label: content?.title || 'Material' },
        ]} />
        <div className="cm-detail-header">
          <div className="cm-detail-title-row">
            <h2>{content.title}</h2>
            {content.course_name && (
              <span className="cm-course-badge">{content.course_name}</span>
            )}
          </div>
          <div className="cm-detail-meta">
            {content.course_name && <span className="cm-type-badge">{content.course_name}</span>}
            <span>{new Date(content.created_at).toLocaleDateString()}</span>
            <div className="cm-header-icon-actions">
              <button className="cm-icon-btn cm-icon-btn-task" title="Create Task" aria-label="Create task" onClick={() => setShowTaskModal(true)}>
                <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <rect x="3" y="2" width="14" height="16" rx="2" stroke="currentColor" strokeWidth="1.6"/>
                  <path d="M7 7h6M7 10.5h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
                  <circle cx="14.5" cy="14.5" r="4.5" fill="var(--color-accent-strong, #2a9fa8)"/>
                  <path d="M14.5 12.5v4M12.5 14.5h4" stroke="#fff" strokeWidth="1.4" strokeLinecap="round"/>
                </svg>
              </button>
              <button className="cm-icon-btn" title="Edit" aria-label="Edit material" onClick={() => setShowEditModal(true)}>&#9998;</button>
              <button className="cm-icon-btn" title="Archive" aria-label="Archive material" onClick={handleArchiveContent}>&#128465;</button>
            </div>
          </div>
        </div>

        <div className="cm-tabs" role="tablist">
          {tabs.map(tab => (
            <button
              key={tab.key}
              className={`cm-tab${activeTab === tab.key ? ' active' : ''}${!tab.hasContent ? ' empty' : ''}`}
              onClick={() => setActiveTab(tab.key)}
              role="tab"
              aria-selected={activeTab === tab.key}
            >
              {tab.label}
              {!tab.hasContent && tab.key !== 'document' && (
                <span className="cm-tab-empty-dot" />
              )}
            </button>
          ))}
        </div>

        <div className="cm-tab-content" role="tabpanel">
          {activeTab === 'document' && (
            <DocumentTab
              content={content}
              downloading={downloading}
              onDownload={handleDownload}
              onShowReplaceModal={() => setShowReplaceModal(true)}
              onContentUpdated={handleContentUpdated}
              showToast={showToast}
              onShowRegenPrompt={() => setShowRegenPrompt(true)}
              onReloadData={loadData}
            />
          )}

          {activeTab === 'guide' && (
            <StudyGuideTab
              studyGuide={studyGuide}
              generating={generating}
              focusPrompt={focusPrompt}
              onFocusPromptChange={setFocusPrompt}
              onGenerate={() => handleGenerate('study_guide')}
              onDelete={handleDeleteGuide}
              hasSourceContent={hasSourceContent}
              linkedTasks={linkedTasks[studyGuide?.id ?? 0] ?? []}
            />
          )}

          {activeTab === 'quiz' && (
            <QuizTab
              quiz={quiz}
              generating={generating}
              focusPrompt={focusPrompt}
              onFocusPromptChange={setFocusPrompt}
              onGenerate={() => handleGenerate('quiz')}
              onDelete={handleDeleteGuide}
              hasSourceContent={hasSourceContent}
              isParent={isParent}
              resolvedStudent={resolvedStudent}
              linkedTasks={linkedTasks[quiz?.id ?? 0] ?? []}
            />
          )}

          {activeTab === 'flashcards' && (
            <FlashcardsTab
              flashcardSet={flashcardSet}
              generating={generating}
              focusPrompt={focusPrompt}
              onFocusPromptChange={setFocusPrompt}
              onGenerate={() => handleGenerate('flashcards')}
              onDelete={handleDeleteGuide}
              hasSourceContent={hasSourceContent}
              isActiveTab={activeTab === 'flashcards'}
              linkedTasks={linkedTasks[flashcardSet?.id ?? 0] ?? []}
            />
          )}
        </div>

      </div>
      <CreateTaskModal
        open={showTaskModal}
        onClose={() => setShowTaskModal(false)}
        prefillTitle={`Review: ${content.title}`}
        courseId={content.course_id}
        courseContentId={content.id}
        linkedEntityLabel={`${content.title}${content.course_name ? ` (${content.course_name})` : ''}`}
      />
      {showEditModal && content && (
        <EditMaterialModal
          material={content}
          onClose={() => setShowEditModal(false)}
          onSaved={(updated) => { setContent(updated); setShowEditModal(false); showToast('Material updated'); }}
        />
      )}
      {confirmModal}
      {toast && <div className="toast-notification">{toast}</div>}
      {uploadStatus === 'uploading' && (
        <div className="cm-upload-status">
          <span className="cm-upload-spinner" />
          Uploading &amp; extracting text...
        </div>
      )}
      {uploadStatus === 'error' && (
        <div className="cm-upload-status error">
          Upload failed
        </div>
      )}
      {showReplaceModal && (
        <ReplaceDocumentModal
          content={content}
          guides={guides}
          onClose={() => setShowReplaceModal(false)}
          onContentUpdated={handleContentUpdated}
          showToast={showToast}
          onShowRegenPrompt={() => setShowRegenPrompt(true)}
          onReloadData={loadData}
          onUploadStatusChange={setUploadStatus}
        />
      )}
      {showRegenPrompt && (
        <div className="cm-regen-prompt">
          <p>Source content was modified. Regenerate study materials?</p>
          <div className="cm-regen-buttons">
            <button className="cm-action-btn" onClick={() => handleRegenerate('study_guide')}>{'\u2728'} Study Guide</button>
            <button className="cm-action-btn" onClick={() => handleRegenerate('quiz')}>{'\u2728'} Quiz</button>
            <button className="cm-action-btn" onClick={() => handleRegenerate('flashcards')}>{'\u2728'} Flashcards</button>
            <button className="cm-action-btn" onClick={() => setShowRegenPrompt(false)}>Dismiss</button>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
