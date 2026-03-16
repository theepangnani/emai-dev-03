import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { courseContentsApi, studyApi, parentApi, type CourseContentItem, type StudyGuide, type CourseContentUpdateResponse, type ResolvedStudent, type LinkedCourseChild, type BriefingNote } from '../api/client';
import { tasksApi, type TaskItem } from '../api/tasks';
import { resourceLinksApi, type ResourceLinkGroup } from '../api/resourceLinks';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { CreateTaskModal } from '../components/CreateTaskModal';
import { useConfirm } from '../components/ConfirmModal';
import { DetailSkeleton } from '../components/Skeleton';
import { FAQErrorHint } from '../components/FAQErrorHint';
import { extractFaqCode } from '../utils/faqUtils';
import { extractQuestionCount, extractCardCount } from '../utils/studyUtils';
import { PageNav } from '../components/PageNav';
import { DocumentTab } from './course-material/DocumentTab';
import { StudyGuideTab } from './course-material/StudyGuideTab';
import { QuizTab } from './course-material/QuizTab';
import { FlashcardsTab } from './course-material/FlashcardsTab';
import { MindMapTab } from './course-material/MindMapTab';
import { VideosLinksTab } from './course-material/VideosLinksTab';
import { BriefingTab } from './course-material/BriefingTab';
import { ReplaceDocumentModal } from './course-material/ReplaceDocumentModal';
import { EditMaterialModal } from '../components/EditMaterialModal';
import { AIWarningBanner } from '../components/AICreditsDisplay';
import { AILimitRequestModal } from '../components/AILimitRequestModal';
import type { StudyFormat } from '../components/study/FormatSelector';
import { NotesPanel } from '../components/NotesPanel';
import { useRegisterNotesFAB } from '../context/FABContext';
import { SelectionTooltip } from '../components/SelectionTooltip';
import { useTextSelection } from '../hooks/useTextSelection';
import { useHighlightRenderer } from '../hooks/useHighlightRenderer';
import '../components/HighlightOverlay.css';
import { useAIUsage } from '../hooks/useAIUsage';
import { HelpStudyMenu } from '../components/study/HelpStudyMenu';
import { LinkedMaterialsPanel } from '../components/LinkedMaterialsPanel';
import { useLinkedMaterials } from '../hooks/useLinkedMaterials';
import './CourseMaterialDetailPage.css';

type TabKey = 'document' | 'guide' | 'quiz' | 'flashcards' | 'mindmap' | 'videos' | 'briefing';
const VALID_TABS: TabKey[] = ['document', 'guide', 'quiz', 'flashcards', 'mindmap', 'videos', 'briefing'];

/* ── Tab icon components ──────────────────────── */
function DocIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M4 1h5.5L13 4.5V13a2 2 0 01-2 2H5a2 2 0 01-2-2V3a2 2 0 012-2z" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M9 1v4h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
      <path d="M5.5 8h5M5.5 10.5h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  );
}

function GuideIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M2 3a1 1 0 011-1h4l1 1h5a1 1 0 011 1v8a1 1 0 01-1 1H3a1 1 0 01-1-1V3z" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M5 7h6M5 9.5h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  );
}

function QuizIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M6 6.2a2.2 2.2 0 114 1.3c0 .8-.8 1-1.2 1.3-.2.2-.3.4-.3.7" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      <circle cx="8.5" cy="11.2" r="0.6" fill="currentColor"/>
    </svg>
  );
}

function FlashcardIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="1.5" y="3" width="10" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
      <rect x="4.5" y="5" width="10" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.3" fill="var(--color-surface, #fff)"/>
      <path d="M7 8.5h5M7 10.5h3" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/>
    </svg>
  );
}

function MindMapIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="3" cy="3.5" r="1.5" stroke="currentColor" strokeWidth="1.1"/>
      <circle cx="13" cy="3.5" r="1.5" stroke="currentColor" strokeWidth="1.1"/>
      <circle cx="3" cy="12.5" r="1.5" stroke="currentColor" strokeWidth="1.1"/>
      <circle cx="13" cy="12.5" r="1.5" stroke="currentColor" strokeWidth="1.1"/>
      <path d="M6.2 6.2L4.2 4.5M9.8 6.2L11.8 4.5M6.2 9.8L4.2 11.5M9.8 9.8L11.8 11.5" stroke="currentColor" strokeWidth="1" strokeLinecap="round"/>
    </svg>
  );
}

function VideosIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="1.5" y="3" width="13" height="10" rx="2" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M6.5 6v4l3.5-2-3.5-2z" fill="currentColor"/>
    </svg>
  );
}

function BriefingTabIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M11 1H5a2 2 0 00-2 2v10a2 2 0 002 2h6a2 2 0 002-2V3a2 2 0 00-2-2z" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M6 5h4M6 7.5h4M6 10h2.5" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/>
    </svg>
  );
}

/* ── Header toolbar icons ─────────────────────── */
function TaskIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <rect x="3" y="2" width="14" height="16" rx="2" stroke="currentColor" strokeWidth="1.6"/>
      <path d="M7 7h6M7 10.5h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
      <circle cx="14.5" cy="14.5" r="4.5" fill="var(--color-accent-strong, #2a9fa8)"/>
      <path d="M14.5 12.5v4M12.5 14.5h4" stroke="#fff" strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  );
}

function NoteIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path d="M4 2h12a2 2 0 012 2v12a2 2 0 01-2 2H4a2 2 0 01-2-2V4a2 2 0 012-2z" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M6 7h8M6 10h8M6 13h5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

function EditIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M11.5 1.5l3 3L5 14H2v-3L11.5 1.5z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
    </svg>
  );
}

function ArchiveIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="1" y="2" width="14" height="3" rx="1" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M2.5 5v8a1.5 1.5 0 001.5 1.5h8a1.5 1.5 0 001.5-1.5V5" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M6 8.5h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

function CalendarIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="1.5" y="2.5" width="13" height="12" rx="2" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M1.5 6.5h13" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M5 1v3M11 1v3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

export function CourseMaterialDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { confirm, confirmModal } = useConfirm();
  const { user } = useAuth();
  const isParent = user?.role === 'parent' || (user?.roles ?? []).includes('parent');
  const { remaining, atLimit, invalidate: refreshAIUsage } = useAIUsage();
  const [showLimitModal, setShowLimitModal] = useState(false);

  const [content, setContent] = useState<CourseContentItem | null>(null);
  const [guides, setGuides] = useState<StudyGuide[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [faqCode, setFaqCode] = useState<string | null>(null);
  const urlTab = searchParams.get('tab') as TabKey | null;
  const [activeTab, setActiveTabState] = useState<TabKey>(
    urlTab && VALID_TABS.includes(urlTab) ? urlTab : 'guide'
  );

  const setActiveTab = useCallback((tab: TabKey) => {
    setActiveTabState(tab);
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      next.set('tab', tab);
      return next;
    }, { replace: true });
  }, [setSearchParams]);
  const [generating, setGenerating] = useState<string | null>(null);

  const [showTaskModal, setShowTaskModal] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [showReplaceModal, setShowReplaceModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showNotesPanel, setShowNotesPanel] = useState(false);
  const [showScrollTop, setShowScrollTop] = useState(false);
  const [showHelpStudyMenu, setShowHelpStudyMenu] = useState(false);
  const [appendText, setAppendText] = useState<string | null>(null);
  const [highlights, setHighlights] = useState<{text: string}[]>([]);
  const [addHighlight, setAddHighlight] = useState<{text: string} | null>(null);
  const [removeHighlightText, setRemoveHighlightText] = useState<string | null>(null);
  const contentAreaRef = useRef<HTMLDivElement>(null);
  const { selection, clearSelection } = useTextSelection(contentAreaRef);
  const handleHighlightClick = useCallback((text: string) => {
    // Immediately update visual highlights for instant feedback
    setHighlights(prev => prev.filter(h => h.text !== text));
    // Tell NotesPanel to persist the removal
    setRemoveHighlightText(text);
  }, []);
  useHighlightRenderer(contentAreaRef, highlights, handleHighlightClick);

  const handleAddToNotes = useCallback(() => {
    if (!selection) return;
    setAppendText(selection.text);
    setAddHighlight({ text: selection.text });
    setShowNotesPanel(true);
    clearSelection();
    window.getSelection()?.removeAllRanges();
  }, [selection, clearSelection]);
  const [resolvedStudent, setResolvedStudent] = useState<ResolvedStudent | null>(null);
  const [guideFocusPrompt, setGuideFocusPrompt] = useState('');
  const [quizFocusPrompt, setQuizFocusPrompt] = useState('');
  const [flashcardsFocusPrompt, setFlashcardsFocusPrompt] = useState('');
  const [mindmapFocusPrompt, setMindmapFocusPrompt] = useState('');

  const [toast, setToast] = useState<string | null>(null);
  const [showRegenPrompt, setShowRegenPrompt] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<'uploading' | 'success' | 'error' | null>(null);
  const [linkedTasks, setLinkedTasks] = useState<Record<number, TaskItem[]>>({});

  // Parent briefing notes
  const [briefingNote, setBriefingNote] = useState<BriefingNote | undefined>(undefined);
  const [generatingBriefing, setGeneratingBriefing] = useState(false);

  // Unlinked material state (#623)
  const [isUnlinked, setIsUnlinked] = useState(false);
  const [linkedChildren, setLinkedChildren] = useState<LinkedCourseChild[]>([]);

  // Linked materials for hierarchy (#1740)
  const { data: linkedMaterials = [], isLoading: linkedLoading, refetch: refetchLinkedMaterials } = useLinkedMaterials(
    content?.id,
    content?.material_group_id
  );

  const contentId = parseInt(id || '0');

  const toggleNotes = useCallback(() => setShowNotesPanel(v => !v), []);
  useRegisterNotesFAB(contentId ? { courseContentId: contentId, isOpen: showNotesPanel, onToggle: toggleNotes } : null);

  useEffect(() => {
    const onScroll = () => {
      const y = window.scrollY ?? document.documentElement.scrollTop ?? 0;
      setShowScrollTop(y > 200);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll(); // sync initial state
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleScrollTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Fetch resource links count for tab badge
  const { data: resourceLinkGroups = [] } = useQuery<ResourceLinkGroup[]>({
    queryKey: ['resource-links', contentId],
    queryFn: () => resourceLinksApi.list(contentId),
    enabled: contentId > 0,
  });
  const resourceLinkCount = resourceLinkGroups.reduce((sum, g) => sum + g.links.length, 0);

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

  // Auto-open notes panel if ?notes=open is in URL (#1087)
  useEffect(() => {
    if (searchParams.get('notes') === 'open') {
      setShowNotesPanel(true);
    }
  }, [searchParams]);

  // Pre-populate focus prompts from saved history on first load
  useEffect(() => {
    if (guides.length === 0) return;
    const sg = guides.find(g => g.guide_type === 'study_guide');
    const qz = guides.find(g => g.guide_type === 'quiz');
    const fc = guides.find(g => g.guide_type === 'flashcards');
    const mm = guides.find(g => g.guide_type === 'mind_map');
    if (sg?.focus_prompt) setGuideFocusPrompt(prev => prev || sg.focus_prompt!);
    if (qz?.focus_prompt) setQuizFocusPrompt(prev => prev || qz.focus_prompt!);
    if (fc?.focus_prompt) setFlashcardsFocusPrompt(prev => prev || fc.focus_prompt!);
    if (mm?.focus_prompt) setMindmapFocusPrompt(prev => prev || mm.focus_prompt!);
  }, [guides]);

  useEffect(() => {
    if (!isParent || !content?.course_id) return;
    studyApi.resolveStudent({ course_id: content.course_id })
      .then(setResolvedStudent)
      .catch(() => {});
    // Check if material is unlinked (#623)
    courseContentsApi.getLinkedCourseIds()
      .then(data => {
        setIsUnlinked(!data.linked_course_ids.includes(content.course_id));
        setLinkedChildren(data.children);
      })
      .catch(() => {});
  }, [isParent, content?.course_id]);

  // Load parent briefing note
  useEffect(() => {
    if (!isParent || !contentId) return;
    parentApi.listBriefingNotes().then(notes => {
      const match = notes.find(n => n.course_content_id === contentId);
      setBriefingNote(match);
    }).catch(() => {});
  }, [isParent, contentId]);

  const studyGuide = guides.find(g => g.guide_type === 'study_guide');
  const quiz = guides.find(g => g.guide_type === 'quiz');
  const flashcardSet = guides.find(g => g.guide_type === 'flashcards');
  const mindMapGuide = guides.find(g => g.guide_type === 'mind_map');

  const hasSourceContent = !!(content?.text_content || content?.description);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  const handleGenerate = async (type: 'study_guide' | 'quiz' | 'flashcards' | 'mind_map', difficulty?: string) => {
    if (!content) return;
    if (atLimit) {
      setShowLimitModal(true);
      return;
    }
    const labels = { study_guide: 'Study Guide', quiz: 'Practice Quiz', flashcards: 'Flashcards', mind_map: 'Mind Map' };
    const ok = await confirm({
      title: `Generate ${labels[type]}`,
      message: `Generate a ${labels[type].toLowerCase()} from "${content.title}"? This will use 1 AI credit. You have ${remaining} remaining.`,
      confirmLabel: 'Generate',
      ...(remaining <= 0 ? {
        disableConfirm: true,
        extraActionLabel: 'Request More Credits',
        onExtraAction: () => setShowLimitModal(true),
      } : {}),
    });
    if (!ok) return;

    setGenerating(type);
    const tabMap: Record<string, TabKey> = { study_guide: 'guide', quiz: 'quiz', flashcards: 'flashcards', mind_map: 'mindmap' };
    setActiveTab(tabMap[type] || 'guide');
    try {
      const promptMap = { study_guide: guideFocusPrompt, quiz: quizFocusPrompt, flashcards: flashcardsFocusPrompt, mind_map: mindmapFocusPrompt };
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
          num_questions: extractQuestionCount(fp),
          focus_prompt: fp,
          difficulty,
        });
      } else if (type === 'flashcards') {
        await studyApi.generateFlashcards({
          course_content_id: contentId,
          course_id: content.course_id,
          topic: content.title,
          content: content.text_content || content.description || '',
          num_cards: extractCardCount(fp),
          focus_prompt: fp,
        });
      } else if (type === 'mind_map') {
        await studyApi.generateMindMap({
          course_content_id: contentId,
          course_id: content.course_id,
          topic: content.title,
          content: content.text_content || content.description || '',
          focus_prompt: fp,
        });
      }
      await loadData();
      refreshAIUsage();
      setActiveTab(tabMap[type] || 'guide');
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
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 404) {
        showToast('Original file is no longer available');
        setContent(prev => prev ? { ...prev, has_file: false } : prev);
      } else {
        showToast('Failed to download document');
      }
    } finally {
      setDownloading(false);
    }
  };

  const handleContentUpdated = (result: CourseContentUpdateResponse) => {
    setContent(result);
  };

  // Assign material's course to a child (#623)
  const handleAssignToChild = async (childStudentId: number) => {
    if (!content) return;
    try {
      await parentApi.assignCoursesToChild(childStudentId, [content.course_id]);
      showToast(`Assigned "${content.course_name || 'class'}" to child`);
      setIsUnlinked(false);
    } catch {
      showToast('Failed to assign class to child');
    }
  };

  const handleRegenerate = async (type: 'study_guide' | 'quiz' | 'flashcards' | 'mind_map') => {
    setShowRegenPrompt(false);
    await handleGenerate(type);
  };

  const handleGenerateBriefing = async () => {
    if (!content || !resolvedStudent) return;
    if (atLimit) { setShowLimitModal(true); return; }
    setGeneratingBriefing(true);
    setActiveTab('briefing');
    try {
      const note = await parentApi.generateBriefingNote(contentId, resolvedStudent.student_user_id);
      setBriefingNote(note);
      refreshAIUsage();
    } catch (err) {
      setError('Failed to generate parent briefing');
      setFaqCode(extractFaqCode(err));
    } finally {
      setGeneratingBriefing(false);
    }
  };

  const handleDeleteBriefing = async (note: BriefingNote) => {
    const ok = await confirm({
      title: 'Delete Parent Briefing',
      message: `Delete "${note.title}"?`,
      confirmLabel: 'Delete',
    });
    if (!ok) return;
    try {
      await parentApi.deleteBriefingNote(note.id);
      setBriefingNote(undefined);
      showToast('Parent briefing deleted');
    } catch {
      showToast('Failed to delete parent briefing');
    }
  };

  const handleFormatSelect = useCallback((format: StudyFormat) => {
    const formatToTab: Record<StudyFormat, TabKey | null> = {
      study_guide: 'guide',
      quiz: 'quiz',
      flashcards: 'flashcards',
      mind_map: null, // coming soon — no action
    };
    const tab = formatToTab[format];
    if (tab) {
      setActiveTab(tab);
    }
  }, [setActiveTab]);

  if (loading) return <DashboardLayout showBackButton headerSlot={() => null}><DetailSkeleton /></DashboardLayout>;
  if (error || !content) return (
    <DashboardLayout showBackButton headerSlot={() => null}>
      <div className="cm-error">
        <p>{error || 'Content not found'}</p>
        <FAQErrorHint faqCode={faqCode} />
        <Link to="/course-materials" className="cm-back-link">Back to Class Materials</Link>
      </div>
    </DashboardLayout>
  );

  const tabs: { key: TabKey; label: string; shortLabel: string; hasContent: boolean; icon: React.ReactNode; badge?: number }[] = [
    { key: 'guide', label: 'Study Guide', shortLabel: 'Guide', hasContent: !!studyGuide, icon: <GuideIcon /> },
    { key: 'quiz', label: 'Quiz', shortLabel: 'Quiz', hasContent: !!quiz, icon: <QuizIcon /> },
    { key: 'flashcards', label: 'Flashcards', shortLabel: 'Cards', hasContent: !!flashcardSet, icon: <FlashcardIcon /> },
    { key: 'mindmap' as TabKey, label: 'Mind Map', shortLabel: 'Map', hasContent: !!mindMapGuide, icon: <MindMapIcon /> },
    ...(resourceLinkCount > 0 ? [{ key: 'videos' as TabKey, label: `Videos & Links (${resourceLinkCount})`, shortLabel: 'Links', hasContent: true, icon: <VideosIcon />, badge: resourceLinkCount }] : []),
    ...(isParent ? [{ key: 'briefing' as TabKey, label: 'Parent Briefing', shortLabel: 'Briefing', hasContent: !!briefingNote, icon: <BriefingTabIcon /> }] : []),
    { key: 'document', label: 'Source Document', shortLabel: 'Source', hasContent: !!(content.text_content || content.description || content.has_file), icon: <DocIcon /> },
  ];

  return (
    <DashboardLayout showBackButton headerSlot={() => null}>
      <div className="cm-detail-page">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Class Materials', to: '/course-materials' },
          { label: content?.title || 'Material' },
        ]} />

        {/* ── Header card ──────────────────────────── */}
        <div className="cm-detail-header">
          <div className="cm-header-main">
            <div className="cm-header-info">
              <div className="cm-detail-title-row">
                <h2>{content.title}</h2>
                <button
                  className="cm-title-edit-btn"
                  title="Edit material"
                  aria-label="Edit material"
                  onClick={() => setShowEditModal(true)}
                >
                  <EditIcon />
                </button>
              </div>
              <div className="cm-detail-meta">
                {content.course_name && <span className="cm-type-badge">{content.course_name}</span>}
                <span className="cm-meta-date">
                  <CalendarIcon />
                  {new Date(content.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                </span>
              </div>
            </div>
          </div>

          <div className="cm-header-toolbar">
            {isParent && resolvedStudent && (
              <button className="cm-toolbar-btn" title="Help Study" aria-label="Help Study menu" onClick={() => setShowHelpStudyMenu(true)}>
                <svg width="15" height="15" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.6"/>
                  <path d="M7 7.5a3 3 0 015.2 1.5c0 2-3 2-3 4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
                  <circle cx="10" cy="15" r="0.8" fill="currentColor"/>
                </svg>
                <span className="cm-toolbar-btn-label">Help Study</span>
              </button>
            )}
            <button className={`cm-toolbar-btn${showNotesPanel ? ' active' : ''}`} title="Notes" aria-label="Toggle notes" onClick={() => setShowNotesPanel(v => !v)}>
              <NoteIcon />
              <span className="cm-toolbar-btn-label">Notes</span>
            </button>
            <button className="cm-toolbar-btn" title="Create Task" aria-label="Create task" onClick={() => setShowTaskModal(true)}>
              <TaskIcon />
              <span className="cm-toolbar-btn-label">Create Task</span>
            </button>
            <button className="cm-toolbar-btn" title="Edit" aria-label="Edit material" onClick={() => setShowEditModal(true)}>
              <EditIcon />
              <span className="cm-toolbar-btn-label">Edit</span>
            </button>
            <span className="cm-toolbar-sep" />
            <button className="cm-toolbar-btn danger" title="Archive" aria-label="Archive material" onClick={handleArchiveContent}>
              <ArchiveIcon />
              <span className="cm-toolbar-btn-label">Archive</span>
            </button>
          </div>
        </div>

        {/* Unlinked banner with assign action (#623) */}
        {isParent && isUnlinked && linkedChildren.length > 0 && (
          <div className="cm-unlinked-banner">
            <span className="cm-unlinked-badge">Not assigned</span>
            <span className="cm-unlinked-text">This material is not assigned to any of your children.</span>
            <div className="cm-unlinked-actions">
              {linkedChildren.map(child => (
                <button
                  key={child.student_id}
                  className="cm-unlinked-assign-btn"
                  onClick={() => handleAssignToChild(child.student_id)}
                >
                  Assign to {child.full_name}
                </button>
              ))}
            </div>
          </div>
        )}

        <AIWarningBanner />

        {/* ── Tab navigation ───────────────────────── */}
        <div className="cm-tabs" role="tablist">
          {tabs.map(tab => (
            <button
              key={tab.key}
              className={`cm-tab${activeTab === tab.key ? ' active' : ''}${!tab.hasContent ? ' empty' : ' has-content'}${tab.key === 'document' ? ' source-doc' : ''}`}
              onClick={() => setActiveTab(tab.key)}
              role="tab"
              aria-selected={activeTab === tab.key}
            >
              <span className="cm-tab-icon">{tab.icon}</span>
              <span className="cm-tab-label">{tab.label}</span>
              <span className="cm-tab-label-short">{tab.shortLabel}</span>
              {!tab.hasContent && tab.key !== 'document' && (
                <span className="cm-tab-empty-dot" />
              )}
            </button>
          ))}
        </div>

        {/* ── Tab content ──────────────────────────── */}
        <div className="cm-tab-content" role="tabpanel" ref={contentAreaRef}>
          {/* Linked Materials Panel (#1740) */}
          {content && content.material_group_id && (
            <LinkedMaterialsPanel
              materials={linkedMaterials}
              currentMaterialId={content.id}
              isCurrentMaster={content.is_master === 'true'}
              loading={linkedLoading}
              masterId={content.is_master === 'true' ? content.id : (content.parent_content_id ?? undefined)}
              onReorder={async (subIds) => {
                const mid = content.is_master === 'true' ? content.id : content.parent_content_id;
                if (!mid) return;
                await courseContentsApi.reorderSubMaterials(mid, subIds);
                refetchLinkedMaterials();
              }}
            />
          )}

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
              atLimit={atLimit}
              courseContentId={contentId}
              onFormatSelect={handleFormatSelect}
              onViewDocument={() => setActiveTab('document')}
              onContinue={loadData}
            />
          )}

          {activeTab === 'quiz' && (
            <QuizTab
              quiz={quiz}
              generating={generating}
              focusPrompt={quizFocusPrompt}
              onFocusPromptChange={setQuizFocusPrompt}
              onGenerate={(diff) => handleGenerate('quiz', diff)}
              onDelete={handleDeleteGuide}
              hasSourceContent={hasSourceContent}
              isParent={isParent}
              resolvedStudent={resolvedStudent}
              linkedTasks={linkedTasks[quiz?.id ?? 0] ?? []}
              atLimit={atLimit}
              onFormatSelect={handleFormatSelect}
              onViewDocument={() => setActiveTab('document')}
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
              atLimit={atLimit}
              onFormatSelect={handleFormatSelect}
              onViewDocument={() => setActiveTab('document')}
            />
          )}

          {activeTab === 'mindmap' && (
            <MindMapTab
              mindMap={mindMapGuide}
              generating={generating}
              focusPrompt={mindmapFocusPrompt}
              onFocusPromptChange={setMindmapFocusPrompt}
              onGenerate={() => handleGenerate('mind_map')}
              onDelete={handleDeleteGuide}
              hasSourceContent={hasSourceContent}
              linkedTasks={linkedTasks[mindMapGuide?.id ?? 0] ?? []}
              atLimit={atLimit}
            />
          )}

          {activeTab === 'videos' && (
            <VideosLinksTab courseContentId={contentId} />
          )}

          {activeTab === 'briefing' && isParent && (
            <BriefingTab
              briefingNote={briefingNote}
              generating={generatingBriefing}
              onGenerate={handleGenerateBriefing}
              onDelete={handleDeleteBriefing}
              hasSourceContent={hasSourceContent}
              atLimit={atLimit}
              studentName={resolvedStudent?.student_name}
              courseContentId={contentId}
            />
          )}

        </div>

        <NotesPanel
          courseContentId={contentId}
          isOpen={showNotesPanel}
          onClose={() => setShowNotesPanel(false)}
          appendText={appendText}
          onAppendConsumed={() => setAppendText(null)}
          addHighlight={addHighlight}
          onHighlightConsumed={() => setAddHighlight(null)}
          onHighlightsChange={setHighlights}
          removeHighlightText={removeHighlightText}
          onRemoveHighlightConsumed={() => setRemoveHighlightText(null)}
          readOnly={isParent && !!resolvedStudent}
          childStudentId={isParent ? resolvedStudent?.student_user_id : undefined}
          childName={isParent ? resolvedStudent?.student_name : undefined}
        />

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
      <AILimitRequestModal open={showLimitModal} onClose={() => setShowLimitModal(false)} />
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
            <button className="cm-action-btn" onClick={() => handleRegenerate('mind_map')}>{'\u2728'} Mind Map</button>
            <button className="cm-action-btn" onClick={() => setShowRegenPrompt(false)}>Dismiss</button>
          </div>
        </div>
      )}

      {/* Contextual notes: selection tooltip + FAB */}
      {selection && (
        <SelectionTooltip rect={selection.rect} visible onAddToNotes={handleAddToNotes} />
      )}
      {showHelpStudyMenu && resolvedStudent && (
        <HelpStudyMenu
          studentId={resolvedStudent.student_user_id}
          courseId={content?.course_id}
          courseContentId={contentId}
          onClose={() => setShowHelpStudyMenu(false)}
          onGenerate={(type) => {
            const tabMap = { study_guide: 'guide' as TabKey, quiz: 'quiz' as TabKey, flashcards: 'flashcards' as TabKey };
            setActiveTab(tabMap[type]);
            handleGenerate(type);
          }}
        />
      )}
      {showScrollTop && (
        <button
          className="cm-scroll-top-btn"
          onClick={handleScrollTop}
          aria-label="Scroll to top"
          title="Scroll to top"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
            <path d="M9 14V4M4 9l5-5 5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      )}
    </DashboardLayout>
  );
}
