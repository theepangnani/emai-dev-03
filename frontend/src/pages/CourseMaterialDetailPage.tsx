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
import { MaterialHeader } from './course-material/MaterialHeader';
import { TabNavigation, type TabKey } from './course-material/TabNavigation';
import { DocumentTab } from './course-material/DocumentTab';
import { StudyGuideTab } from './course-material/StudyGuideTab';
import { QuizTab } from './course-material/QuizTab';
import { FlashcardsTab } from './course-material/FlashcardsTab';
import { ReplaceDocumentModal } from './course-material/ReplaceDocumentModal';
import { RegenPromptBanner } from './course-material/RegenPromptBanner';
import { UploadStatusIndicator } from './course-material/UploadStatusIndicator';
import { ToastNotification } from './course-material/ToastNotification';
import { EditMaterialModal } from '../components/EditMaterialModal';
import './CourseMaterialDetailPage.css';

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
  const [guideFocusPrompt, setGuideFocusPrompt] = useState('');
  const [quizFocusPrompt, setQuizFocusPrompt] = useState('');
  const [flashcardsFocusPrompt, setFlashcardsFocusPrompt] = useState('');

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
      const promptMap = { study_guide: guideFocusPrompt, quiz: quizFocusPrompt, flashcards: flashcardsFocusPrompt };
      const fp = promptMap[type].trim() || undefined;
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
          const dueStr = t.due_date ? ` (due ${new Date(t.due_date.includes('T') ? t.due_date : t.due_date + 'T00:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })})` : '';
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

  const tabs = [
    { key: 'document' as TabKey, label: 'Original Document', hasContent: !!(content.text_content || content.description || content.has_file) },
    { key: 'guide' as TabKey, label: 'Study Guide', hasContent: !!studyGuide },
    { key: 'quiz' as TabKey, label: 'Quiz', hasContent: !!quiz },
    { key: 'flashcards' as TabKey, label: 'Flashcards', hasContent: !!flashcardSet },
  ];

  return (
    <DashboardLayout showBackButton>
      <div className="cm-detail-page">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Course Materials', to: '/course-materials' },
          { label: content?.title || 'Material' },
        ]} />

        <MaterialHeader
          content={content}
          onCreateTask={() => setShowTaskModal(true)}
          onEdit={() => setShowEditModal(true)}
          onArchive={handleArchiveContent}
        />

        <TabNavigation
          tabs={tabs}
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />

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
              focusPrompt={guideFocusPrompt}
              onFocusPromptChange={setGuideFocusPrompt}
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
              focusPrompt={quizFocusPrompt}
              onFocusPromptChange={setQuizFocusPrompt}
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
              focusPrompt={flashcardsFocusPrompt}
              onFocusPromptChange={setFlashcardsFocusPrompt}
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
      <ToastNotification message={toast} />
      <UploadStatusIndicator status={uploadStatus} />
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
        <RegenPromptBanner
          onRegenerate={handleRegenerate}
          onDismiss={() => setShowRegenPrompt(false)}
        />
      )}
    </DashboardLayout>
  );
}
