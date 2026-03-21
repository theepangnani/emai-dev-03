import { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { studyApi, parentApi, courseContentsApi, coursesApi, tasksApi } from '../api/client';
import type { StudyGuide, DuplicateCheckResponse, ChildSummary, CourseContentItem, AutoCreatedTask, LinkedCourseChild, SharedWithMeGuide, SharedGuideStatus } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { CreateTaskModal } from '../components/CreateTaskModal';
import { useConfirm } from '../components/ConfirmModal';
import { useFocusTrap } from '../hooks/useFocusTrap';
import { PageSkeleton } from '../components/Skeleton';
import { LottieLoader } from '../components/LottieLoader';
import { PageNav } from '../components/PageNav';
import { CHILD_COLORS } from '../components/parent/useParentDashboard';
import UploadMaterialWizard, { type StudyMaterialGenerateParams } from '../components/UploadMaterialWizard';
import { EditMaterialModal } from '../components/EditMaterialModal';
import EmptyState from '../components/EmptyState';
import { AIWarningBanner } from '../components/AICreditsDisplay';
import { AILimitRequestModal } from '../components/AILimitRequestModal';
import { useAIUsage } from '../hooks/useAIUsage';
import '../components/AddActionButton.css';
import './StudyGuidesPage.css';

// Cross-page generation queue (ParentDashboard -> StudyGuidesPage)
interface PendingGeneration {
  title: string;
  content: string;
  type: 'study_guide' | 'quiz' | 'flashcards';
  focusPrompt?: string;
  mode: 'text' | 'file';
  file?: File;
  files?: File[];  // multi-file: text extraction happens inside startGeneration background task
  pastedImages?: File[];
  regenerateId?: number;
  courseId?: number;
  courseContentId?: number;
  documentType?: string;
  studyGoal?: string;
  studyGoalText?: string;
}

let _pendingGenerations: PendingGeneration[] = [];

// eslint-disable-next-line react-refresh/only-export-components
export function queueStudyGeneration(params: PendingGeneration) {
  _pendingGenerations.push(params);
}

// In-progress generation placeholder
interface GeneratingItem {
  tempId: string;
  title: string;
  guideType: string;
  status: 'uploading' | 'generating' | 'error';
  error?: string;
}

interface CourseOption {
  id: number;
  name: string;
}

export function StudyGuidesPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const isParent = user?.role === 'parent';
  const { confirm, confirmModal } = useConfirm();
  const { atLimit, invalidate: refreshAIUsage } = useAIUsage();
  const [showLimitModal, setShowLimitModal] = useState(false);

  // Course content items (primary list)
  const [contentItems, setContentItems] = useState<CourseContentItem[]>([]);
  // Legacy study guides without course_content_id
  const [legacyGuides, setLegacyGuides] = useState<StudyGuide[]>([]);
  // Map of course_content_id -> guide_types for filtering
  const [contentGuideMap, setContentGuideMap] = useState<Record<number, string[]>>({});
  const [hasSubGuides, setHasSubGuides] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  // Filters — initialize child from navigation state if parent dashboard passed it
  const [filterChild, setFilterChild] = useState<number | ''>(() => {
    const navState = location.state as { selectedChild?: number | null } | null;
    if (navState?.selectedChild) return navState.selectedChild;
    const stored = sessionStorage.getItem('selectedChildId');
    return stored ? Number(stored) : '';
  });
  const [filterCourse, setFilterCourse] = useState<number | ''>(() => {
    const course = searchParams.get('course');
    return course ? Number(course) : '';
  });
  const [filterType, setFilterType] = useState<string>(() => searchParams.get('type') || 'all');
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [courses, setCourses] = useState<CourseOption[]>([]);

  // Wizard-local child selection (does not mutate page filter) (#1994)
  const [wizardChildId, setWizardChildId] = useState<number | ''>('');

  // Study tools modal
  const [showModal, setShowModal] = useState(false);
  const [modalCourseId, setModalCourseId] = useState<number | ''>('');
  const [modalMaterials, setModalMaterials] = useState<CourseContentItem[]>([]);
  const [modalMaterialId, setModalMaterialId] = useState<number | ''>('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [duplicateCheck, setDuplicateCheck] = useState<DuplicateCheckResponse | null>(null);
  const generatingRef = useRef(false);
  const lastGenerateParamsRef = useRef<StudyMaterialGenerateParams | null>(null);

  // In-progress generation placeholders
  const [generatingItems, setGeneratingItems] = useState<GeneratingItem[]>([]);

  // Parent-Child Study Link (#1414)
  const isStudent = user?.role === 'student';
  const [sharedWithMe, setSharedWithMe] = useState<SharedWithMeGuide[]>([]);
  const [sharedStatus, setSharedStatus] = useState<Map<number, SharedGuideStatus>>(new Map());
  const [sharingGuideId, setSharingGuideId] = useState<number | null>(null);

  // Create task from guide
  const [taskModalGuide, setTaskModalGuide] = useState<StudyGuide | null>(null);

  // Date prompt for auto-created tasks
  const [datePromptTasks, setDatePromptTasks] = useState<AutoCreatedTask[]>([]);
  const [datePromptValues, setDatePromptValues] = useState<Record<number, string>>({});

  // Collapsible sections
  const [materialsExpanded, setMaterialsExpanded] = useState(true);

  // Archive section
  const [showArchived, setShowArchived] = useState(false);
  const [archivedContents, setArchivedContents] = useState<CourseContentItem[]>([]);
  const [archivedGuides, setArchivedGuides] = useState<StudyGuide[]>([]);

  // Course search
  const [courseSearchQuery, setCourseSearchQuery] = useState('');
  const [courseSearchOpen, setCourseSearchOpen] = useState(false);
  const courseSearchRef = useRef<HTMLDivElement>(null);

  // Toast notification
  const [toast, setToast] = useState<string | null>(null);

  // Categorize ungrouped guide
  const [categorizeGuide, setCategorizeGuide] = useState<StudyGuide | null>(null);
  const [categorizeCourseId, setCategorizeCourseId] = useState<number | ''>('');
  const [categorizeSearch, setCategorizeSearch] = useState('');
  const [categorizeNewName, setCategorizeNewName] = useState('');
  const [categorizeCreating, setCategorizeCreating] = useState(false);

  // Reassign course content to different course
  const [reassignContent, setReassignContent] = useState<CourseContentItem | null>(null);

  // Edit material modal
  const [editContent, setEditContent] = useState<CourseContentItem | null>(null);

  // Linked course tracking for unlinked material tagging (#623)
  const [linkedCourseIds, setLinkedCourseIds] = useState<Set<number>>(new Set());
  const [courseStudentMap, setCourseStudentMap] = useState<Record<number, number[]>>({});
  const [linkedChildren, setLinkedChildren] = useState<LinkedCourseChild[]>([]);
  const [assignFilter, setAssignFilter] = useState<'all' | 'unlinked' | 'assigned'>('all');

  // Batch selection for assigning unlinked materials (#623)
  const [selectedContentIds, setSelectedContentIds] = useState<Set<number>>(new Set());
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [assignTargetChildren, setAssignTargetChildren] = useState<Set<number>>(new Set());
  const [assigning, setAssigning] = useState(false);
  const assignModalRef = useFocusTrap<HTMLDivElement>(showAssignModal, () => setShowAssignModal(false));

  // Category grouping (#992)
  const [categories, setCategories] = useState<string[]>([]);
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(new Set());
  const [moveToCategoryContentId, setMoveToCategoryContentId] = useState<number | null>(null);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [moveCategoryTarget, setMoveCategoryTarget] = useState('');
  const [bulkCategorizing, setBulkCategorizing] = useState(false);
  const [bulkArchiving, setBulkArchiving] = useState(false);

  // Create Course from child-selector "+" menu
  const [showChildAddMenu, setShowChildAddMenu] = useState(false);
  const [showCreateCourseModal, setShowCreateCourseModal] = useState(false);
  const [newCourseName, setNewCourseName] = useState('');
  const [newCourseSubject, setNewCourseSubject] = useState('');
  const [newCourseDescription, setNewCourseDescription] = useState('');
  const [newCourseTeacherEmail, setNewCourseTeacherEmail] = useState('');
  const [createCourseLoading, setCreateCourseLoading] = useState(false);
  const [createCourseError, setCreateCourseError] = useState('');
  const childAddMenuRef = useRef<HTMLDivElement>(null);

  // Focus traps for modals
  const categorizeModalRef = useFocusTrap<HTMLDivElement>(!!categorizeGuide, () => setCategorizeGuide(null));
  const reassignModalRef = useFocusTrap<HTMLDivElement>(!!reassignContent, () => setReassignContent(null));
  const datePromptModalRef = useFocusTrap<HTMLDivElement>(datePromptTasks.length > 0);
  const createCourseModalRef = useFocusTrap<HTMLDivElement>(showCreateCourseModal, () => setShowCreateCourseModal(false));

  useEffect(() => {
    loadData();
    if (_pendingGenerations.length > 0) {
      const pending = [..._pendingGenerations];
      _pendingGenerations = [];
      pending.forEach(p => startGeneration(p));
    }
    // Safety timeout: if loading takes too long, show error state
    const timeout = setTimeout(() => {
      setLoading(prev => {
        if (prev) setLoadError(true);
        return false;
      });
    }, 30000);
    return () => clearTimeout(timeout);
  }, []);

  // Reset course filter when child changes (filter cascade fix)
  const prevFilterChild = useRef(filterChild);
  useEffect(() => {
    if (prevFilterChild.current !== filterChild) {
      prevFilterChild.current = filterChild;
      setFilterCourse('');
      searchParams.delete('course');
      setSearchParams(searchParams, { replace: true });
    }
  }, [filterChild]);

  // Courses filtered by selected child for the upload wizard (#1923)
  // Use wizardChildId when set, otherwise fall back to filterChild (#1994)
  const wizardCourses = useMemo(() => {
    const effectiveChild = wizardChildId || filterChild;
    if (!effectiveChild || Object.keys(courseStudentMap).length === 0) return courses;
    // effectiveChild is user_id; courseStudentMap maps course_id -> student_id[]
    const child = children.find(c => c.user_id === effectiveChild || c.student_id === effectiveChild);
    if (!child) return courses;
    return courses.filter(c => {
      const students = courseStudentMap[c.id];
      return students && students.includes(child.student_id);
    });
  }, [wizardChildId, filterChild, courseStudentMap, courses, children]);

  // Reload content when filters change
  useEffect(() => {
    loadContentItems();
  }, [filterChild, filterCourse]);

  // Sync course search query with selected course name
  useEffect(() => {
    if (filterCourse && courses.length > 0) {
      const selected = courses.find(c => c.id === filterCourse);
      if (selected) setCourseSearchQuery(selected.name);
    }
  }, [courses, filterCourse]);

  // Load materials for modal course selection
  useEffect(() => {
    if (modalCourseId) {
      courseContentsApi.list(modalCourseId as number).then(setModalMaterials).catch(() => setModalMaterials([]));
    } else {
      setModalMaterials([]);
    }
    setModalMaterialId('');
  }, [modalCourseId]);

  // Close child-add menu on outside click
  useEffect(() => {
    if (!showChildAddMenu) return;
    const handler = (e: MouseEvent) => {
      if (childAddMenuRef.current && !childAddMenuRef.current.contains(e.target as Node)) {
        setShowChildAddMenu(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showChildAddMenu]);

  // Create course handler
  const handleCreateCourse = async () => {
    if (!newCourseName.trim()) return;
    setCreateCourseError('');
    setCreateCourseLoading(true);
    try {
      const newCourse = await coursesApi.create({
        name: newCourseName.trim(),
        subject: newCourseSubject.trim() || undefined,
        description: newCourseDescription.trim() || undefined,
        teacher_email: newCourseTeacherEmail.trim() || undefined,
      });
      setShowCreateCourseModal(false);
      setNewCourseName('');
      setNewCourseSubject('');
      setNewCourseDescription('');
      setNewCourseTeacherEmail('');
      setCreateCourseError('');
      navigate(`/courses/${newCourse.id}`);
    } catch (err: any) {
      setCreateCourseError(err.response?.data?.detail || 'Failed to create class');
    } finally {
      setCreateCourseLoading(false);
    }
  };

  const loadData = async () => {
    setLoadError(false);
    try {
      const contentParams: Record<string, any> = {};
      if (filterChild) contentParams.student_user_id = filterChild;
      const [contents, allGuides, courseList, cats] = await Promise.all([
        courseContentsApi.listAll(contentParams),
        studyApi.listGuides(),
        coursesApi.list(),
        courseContentsApi.listCategories().catch(() => [] as string[]),
      ]);
      setContentItems(contents);
      setCategories(cats);
      setCourses(courseList.map((c: any) => ({ id: c.id, name: c.name })));

      // Legacy guides: those without course_content_id
      setLegacyGuides(allGuides.filter((g: StudyGuide) => !g.course_content_id));

      // Build guide type map for content filtering
      const guideMap: Record<number, string[]> = {};
      allGuides.forEach((g: StudyGuide) => {
        if (g.course_content_id) {
          if (!guideMap[g.course_content_id]) guideMap[g.course_content_id] = [];
          if (!guideMap[g.course_content_id].includes(g.guide_type)) {
            guideMap[g.course_content_id].push(g.guide_type);
          }
        }
      });
      setContentGuideMap(guideMap);

      // Build set of content IDs that have sub-guides
      const subGuideContentIds = new Set<number>();
      allGuides.forEach((g: StudyGuide) => {
        if (g.course_content_id && g.parent_guide_id && (!g.relationship_type || g.relationship_type === 'sub_guide')) {
          subGuideContentIds.add(g.course_content_id);
        }
      });
      setHasSubGuides(subGuideContentIds);

      if (isParent) {
        try {
          const [childrenData, linkedData, statusData] = await Promise.all([
            parentApi.getChildren(),
            courseContentsApi.getLinkedCourseIds(),
            studyApi.getSharedStatus(),
          ]);
          setChildren(childrenData);
          setLinkedCourseIds(new Set(linkedData.linked_course_ids));
          setCourseStudentMap(linkedData.course_student_map);
          setLinkedChildren(linkedData.children);
          setSharedStatus(new Map(statusData.map(s => [s.id, s])));
        } catch (err) {
          console.error('[CourseMaterials] Failed to load parent-specific data:', err);
        }
      }

      // Student: load guides shared by parent (#1414)
      if (isStudent) {
        try {
          const shared = await studyApi.getSharedWithMe();
          setSharedWithMe(shared);
        } catch (err) {
          console.error('[CourseMaterials] Failed to load shared guides:', err);
        }
      }
    } catch (err) {
      console.error('[CourseMaterials] Failed to load course materials:', err);
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  };

  const loadContentItems = async () => {
    try {
      const params: Record<string, any> = {};
      if (filterChild) params.student_user_id = filterChild;
      const items = await courseContentsApi.listAll(params);
      setContentItems(items);
    } catch { /* ignore */ }
  };

  const loadArchived = async () => {
    try {
      const archiveParams: Record<string, any> = { include_archived: true };
      if (filterChild) archiveParams.student_user_id = filterChild;
      const [allContents, allGuides] = await Promise.all([
        courseContentsApi.listAll(archiveParams),
        studyApi.listGuides({ include_archived: true }),
      ]);
      setArchivedContents(allContents.filter(c => c.archived_at));
      setArchivedGuides(allGuides.filter(g => g.archived_at));
    } catch { /* ignore */ }
  };

  useEffect(() => {
    loadArchived();
  }, [filterChild]);

  // Share a study guide with a child (#1414)
  const handleShareGuide = async (guideId: number, studentId: number) => {
    try {
      setSharingGuideId(guideId);
      await studyApi.shareGuide(guideId, studentId);
      const statusData = await studyApi.getSharedStatus();
      setSharedStatus(new Map(statusData.map(s => [s.id, s])));
    } catch (err: any) {
      console.error('Failed to share guide', err);
    } finally {
      setSharingGuideId(null);
    }
  };

  // Close course search dropdown on outside click
  useEffect(() => {
    if (!courseSearchOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (courseSearchRef.current && !courseSearchRef.current.contains(e.target as Node)) {
        setCourseSearchOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [courseSearchOpen]);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  // Category operations (#992)
  const handleMoveToCategory = async (contentId: number, category: string) => {
    try {
      await courseContentsApi.update(contentId, { category: category || undefined });
      setContentItems(prev => prev.map(c => c.id === contentId ? { ...c, category: category || null } : c));
      if (category && !categories.includes(category)) {
        setCategories(prev => [...prev, category].sort());
      }
      setMoveToCategoryContentId(null);
      setNewCategoryName('');
      setMoveCategoryTarget('');
      showToast(category ? `Moved to "${category}"` : 'Moved to Uncategorized');
    } catch { showToast('Failed to update category'); }
  };

  const handleBulkCategorize = async (category: string) => {
    if (selectedContentIds.size === 0) return;
    setBulkCategorizing(true);
    try {
      await courseContentsApi.bulkCategorize([...selectedContentIds], category);
      setContentItems(prev => prev.map(c =>
        selectedContentIds.has(c.id) ? { ...c, category } : c
      ));
      if (!categories.includes(category)) {
        setCategories(prev => [...prev, category].sort());
      }
      setSelectedContentIds(new Set());
      showToast(`Moved ${selectedContentIds.size} items to "${category}"`);
    } catch { showToast('Failed to categorize'); }
    setBulkCategorizing(false);
  };

  const handleBulkArchive = async () => {
    if (selectedContentIds.size === 0) return;
    const ok = await confirm({
      title: 'Archive Selected',
      message: `This will archive ${selectedContentIds.size} class material(s). You can restore them later from the archive.`,
      confirmLabel: 'Archive',
    });
    if (!ok) return;
    setBulkArchiving(true);
    try {
      const result = await courseContentsApi.bulkArchive([...selectedContentIds]);
      setContentItems(prev => prev.filter(c => !selectedContentIds.has(c.id)));
      setSelectedContentIds(new Set());
      showToast(`${result.archived} material(s) archived`);
      if (showArchived) loadArchived();
    } catch { /* ignore */ } finally {
      setBulkArchiving(false);
    }
  };

  const toggleCategoryCollapse = (cat: string) => {
    setCollapsedCategories(prev => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  const handleArchiveContent = async (id: number) => {
    const ok = await confirm({ title: 'Archive Material', message: 'This will archive the class material. You can restore it later from the archive.', confirmLabel: 'Archive' });
    if (!ok) return;
    try {
      await courseContentsApi.delete(id);
      setContentItems(prev => prev.filter(c => c.id !== id));
      showToast('Material archived');
      if (showArchived) loadArchived();
    } catch { /* ignore */ }
  };

  const handleRestoreContent = async (id: number) => {
    try {
      await courseContentsApi.restore(id);
      showToast('Material restored');
      loadData();
      loadArchived();
    } catch { /* ignore */ }
  };

  const handlePermanentDeleteContent = async (id: number) => {
    const ok = await confirm({ title: 'Permanently Delete', message: 'This will permanently delete this material and all linked study guides. This cannot be undone.', confirmLabel: 'Delete Forever', variant: 'danger' });
    if (!ok) return;
    try {
      await courseContentsApi.permanentDelete(id);
      showToast('Material permanently deleted');
      loadArchived();
    } catch { /* ignore */ }
  };

  const handleRestoreGuide = async (id: number) => {
    try {
      await studyApi.restoreGuide(id);
      showToast('Study guide restored');
      loadData();
      loadArchived();
    } catch { /* ignore */ }
  };

  const handlePermanentDeleteGuide = async (id: number) => {
    const ok = await confirm({ title: 'Permanently Delete', message: 'This will permanently delete this study guide. This cannot be undone.', confirmLabel: 'Delete Forever', variant: 'danger' });
    if (!ok) return;
    try {
      await studyApi.permanentDeleteGuide(id);
      showToast('Study guide permanently deleted');
      loadArchived();
    } catch { /* ignore */ }
  };

  const navigateToContent = (item: CourseContentItem) => {
    navigate(`/course-materials/${item.id}`);
  };

  const navigateToLegacyGuide = (guide: StudyGuide) => {
    if (guide.course_content_id) {
      const tabMap: Record<string, string> = { quiz: 'quiz', flashcards: 'flashcards', study_guide: 'guide', mind_map: 'mindmap' };
      navigate(`/course-materials/${guide.course_content_id}?tab=${tabMap[guide.guide_type] || 'guide'}`);
    } else if (guide.guide_type === 'quiz') navigate(`/study/quiz/${guide.id}`);
    else if (guide.guide_type === 'flashcards') navigate(`/study/flashcards/${guide.id}`);
    else navigate(`/study/guide/${guide.id}`);
  };

  const handleDeleteLegacyGuide = async (id: number) => {
    try {
      await studyApi.deleteGuide(id);
      setLegacyGuides(prev => prev.filter(g => g.id !== id));
    } catch { /* ignore */ }
  };

  const handleCategorize = async (courseId?: number) => {
    if (!categorizeGuide) return;
    const targetCourseId = courseId ?? (categorizeCourseId ? Number(categorizeCourseId) : null);
    if (!targetCourseId) return;
    try {
      await studyApi.updateGuide(categorizeGuide.id, { course_id: targetCourseId });
      setCategorizeGuide(null);
      setCategorizeCourseId('');
      setCategorizeSearch('');
      setCategorizeNewName('');
      loadData();
    } catch { /* ignore */ }
  };

  const handleCreateAndCategorize = async () => {
    if (!categorizeGuide || !categorizeNewName.trim()) return;
    setCategorizeCreating(true);
    try {
      const newCourse = await coursesApi.create({ name: categorizeNewName.trim() });
      await handleCategorize(newCourse.id);
    } catch { /* ignore */ }
    setCategorizeCreating(false);
  };

  const handleReassignContent = async (courseId?: number) => {
    if (!reassignContent) return;
    const targetCourseId = courseId ?? (categorizeCourseId ? Number(categorizeCourseId) : null);
    if (!targetCourseId) return;
    try {
      await courseContentsApi.update(reassignContent.id, { course_id: targetCourseId });
      setReassignContent(null);
      setCategorizeCourseId('');
      setCategorizeSearch('');
      setCategorizeNewName('');
      loadData();
    } catch { /* ignore */ }
  };

  const handleCreateAndReassign = async () => {
    if (!reassignContent || !categorizeNewName.trim()) return;
    setCategorizeCreating(true);
    try {
      const newCourse = await coursesApi.create({ name: categorizeNewName.trim() });
      await handleReassignContent(newCourse.id);
    } catch { /* ignore */ }
    setCategorizeCreating(false);
  };

  const handleConvertGuide = (guide: StudyGuide, targetType: 'study_guide' | 'quiz' | 'flashcards') => {
    let content = guide.content;
    // Extract readable text from quiz/flashcard JSON
    if (guide.guide_type !== 'study_guide') {
      try {
        const parsed = JSON.parse(guide.content);
        if (guide.guide_type === 'quiz') {
          content = parsed.map((q: any) => `Q: ${q.question}\nA: ${q.correct_answer}`).join('\n\n');
        } else {
          content = parsed.map((c: any) => `${c.front}: ${c.back}`).join('\n');
        }
      } catch { /* use raw content */ }
    }
    startGeneration({
      title: guide.title.replace(/^(Study Guide|Quiz|Flashcards): ?/i, ''),
      content,
      type: targetType,
      mode: 'text',
    });
  };

  const contentTypeIcon = (type: string, itemId?: number) => {
    // Check guide type first for better icons on quiz/flashcard items
    if (itemId && contentGuideMap[itemId]) {
      const guideTypes = contentGuideMap[itemId];
      if (guideTypes.includes('quiz')) return '\uD83D\uDCCB';
      if (guideTypes.includes('flashcards')) return '\uD83C\uDCCF';
      if (guideTypes.includes('study_guide')) return '\uD83D\uDCD6';
    }
    const icons: Record<string, string> = {
      notes: '\uD83D\uDCDD',
      syllabus: '\uD83D\uDCCB',
      labs: '\uD83E\uDDEA',
      assignments: '\uD83D\uDCDA',
      readings: '\uD83D\uDCD6',
      resources: '\uD83D\uDCE6',
    };
    return icons[type] || '\uD83D\uDCC4';
  };

  const guideTypeLabel = (type: string) => {
    if (type === 'quiz') return 'Quiz';
    if (type === 'flashcards') return 'Flashcards';
    return 'Study Guide';
  };

  const resetModal = () => {
    setShowModal(false);
    setDuplicateCheck(null);
    setModalCourseId(''); setModalMaterialId(''); setModalMaterials([]);
  };

  const startGeneration = (params: PendingGeneration) => {
    const tempId = `gen-${Date.now()}`;
    const displayTitle = params.title || `New ${params.type.replace('_', ' ')}`;
    const hasFiles = !!(params.file || (params.files && params.files.length > 0) || (params.pastedImages && params.pastedImages.length > 0));
    setGeneratingItems(prev => [...prev, { tempId, title: displayTitle, guideType: params.type, status: hasFiles ? 'uploading' : 'generating' }]);

    (async () => {
      try {
        // Multi-file: extract combined text now that we're running in the background
        let content = params.content;
        let mode = params.mode;
        if (params.files && params.files.length > 1) {
          const resolvedCourseId = params.courseId || (await coursesApi.getDefault(filterChild || undefined)).id;
          const cc = await courseContentsApi.uploadMultiFiles(
            params.files,
            resolvedCourseId,
            params.title || undefined,
            'notes',
          );
          params.courseContentId = cc.id;
          content = cc.text_content || '';
          mode = 'text';
        }

        // Transition from uploading → generating once files are processed
        if (hasFiles) {
          setGeneratingItems(prev => prev.map(g =>
            g.tempId === tempId ? { ...g, status: 'generating' as const } : g
          ));
        }

        let result: any;
        if (mode === 'file' && params.file) {
          result = await studyApi.generateFromFile({
            file: params.file, title: params.title || undefined, guide_type: params.type,
            num_questions: params.type === 'quiz' ? 10 : undefined,
            num_cards: params.type === 'flashcards' ? 15 : undefined,
            course_id: params.courseId, course_content_id: params.courseContentId,
            focus_prompt: params.focusPrompt,
            document_type: params.documentType, study_goal: params.studyGoal, study_goal_text: params.studyGoalText,
          });
        } else if (params.pastedImages && params.pastedImages.length > 0) {
          result = await studyApi.generateFromTextAndImages({
            content: content,
            images: params.pastedImages,
            title: params.title || undefined,
            guide_type: params.type,
            num_questions: params.type === 'quiz' ? 10 : undefined,
            num_cards: params.type === 'flashcards' ? 15 : undefined,
            course_id: params.courseId,
            course_content_id: params.courseContentId,
            focus_prompt: params.focusPrompt,
            document_type: params.documentType, study_goal: params.studyGoal, study_goal_text: params.studyGoalText,
          });
        } else if (params.type === 'study_guide') {
          result = await studyApi.generateGuide({ title: params.title, content: content, regenerate_from_id: params.regenerateId, course_id: params.courseId, course_content_id: params.courseContentId, focus_prompt: params.focusPrompt, document_type: params.documentType, study_goal: params.studyGoal, study_goal_text: params.studyGoalText });
        } else if (params.type === 'quiz') {
          result = await studyApi.generateQuiz({ topic: params.title, content: content, num_questions: 10, regenerate_from_id: params.regenerateId, course_id: params.courseId, course_content_id: params.courseContentId, focus_prompt: params.focusPrompt });
        } else {
          result = await studyApi.generateFlashcards({ topic: params.title, content: content, num_cards: 15, regenerate_from_id: params.regenerateId, course_id: params.courseId, course_content_id: params.courseContentId, focus_prompt: params.focusPrompt });
        }
        setGeneratingItems(prev => prev.filter(g => g.tempId !== tempId));
        loadData();
        refreshAIUsage();

        // Show date prompt for auto-created tasks
        const tasks = result?.auto_created_tasks;
        if (tasks && tasks.length > 0) {
          const dateValues: Record<number, string> = {};
          tasks.forEach((t: AutoCreatedTask) => { dateValues[t.id] = t.due_date; });
          setDatePromptValues(dateValues);
          setDatePromptTasks(tasks);
        }
      } catch (err: any) {
        setGeneratingItems(prev => prev.map(g =>
          g.tempId === tempId
            ? { ...g, status: 'error' as const, error: err.response?.data?.detail || 'Generation failed' }
            : g
        ));
      }
    })();
  };

  /** Extract and concatenate text from multiple files using the backend extract endpoint.
   *  Files are processed sequentially to avoid hitting the per-minute rate limit. */
  const handleGenerateFromModal = async (modalParams: StudyMaterialGenerateParams) => {
    if (generatingRef.current) return;
    // Block AI generation when at limit (upload-only mode is allowed)
    if (atLimit && modalParams.types.length > 0) {
      resetModal();
      setShowLimitModal(true);
      return;
    }
    lastGenerateParamsRef.current = modalParams;

    const files = modalParams.files ?? (modalParams.file ? [modalParams.file] : []);
    const isMultiFile = files.length > 1;

    // Always close modal immediately — never leave it open in a "Generating..." state.
    // Background work (duplicate check, extraction, AI generation) continues after close.
    resetModal();

    // Upload-only mode: run upload/extraction in background
    if (modalParams.types.length === 0) {
      const courseId = modalParams.courseId;
      const uploadTempId = `upload-${Date.now()}`;
      const uploadTitle = modalParams.title || (files.length > 0 ? files[0].name.replace(/\.[^/.]+$/, '') : 'Uploaded material');
      setGeneratingItems(prev => [...prev, { tempId: uploadTempId, title: uploadTitle, guideType: 'upload', status: 'uploading' }]);
      (async () => {
        try {
          const resolvedCourseId = courseId ?? (await coursesApi.getDefault(filterChild || undefined)).id;
          if (files.length === 1) {
            // Single file: upload directly (preserves file metadata on backend)
            await courseContentsApi.uploadFile(
              files[0],
              resolvedCourseId,
              modalParams.title || undefined,
              'notes',
            );
          } else if (isMultiFile) {
            await courseContentsApi.uploadMultiFiles(
              files,
              resolvedCourseId,
              modalParams.title || undefined,
              'notes',
            );
          } else if (modalParams.pastedImages && modalParams.pastedImages.length > 0) {
            // Pasted images: upload as files so backend can store and extract text
            const imagesToUpload = modalParams.pastedImages;
            if (imagesToUpload.length === 1 && !modalParams.content?.trim()) {
              await courseContentsApi.uploadFile(
                imagesToUpload[0],
                resolvedCourseId,
                modalParams.title || undefined,
                'notes',
              );
            } else {
              // Multiple images or images + text: upload all as multi-file
              const allFiles = [...imagesToUpload];
              if (modalParams.content?.trim()) {
                const textBlob = new Blob([modalParams.content], { type: 'text/plain' });
                const textFile = new File([textBlob], 'pasted-content.txt', { type: 'text/plain' });
                allFiles.unshift(textFile);
              }
              await courseContentsApi.uploadMultiFiles(
                allFiles,
                resolvedCourseId,
                modalParams.title || undefined,
                'notes',
              );
            }
          } else {
            // Text/paste mode: create content with text only
            await courseContentsApi.create({
              course_id: resolvedCourseId,
              title: modalParams.title || 'Uploaded material',
              text_content: modalParams.content || undefined,
              content_type: 'notes',
            });
          }
          setGeneratingItems(prev => prev.filter(g => g.tempId !== uploadTempId));
          await loadData();
          showToast('Upload complete');
        } catch {
          setGeneratingItems(prev => prev.map(g =>
            g.tempId === uploadTempId
              ? { ...g, status: 'error' as const, error: 'Upload failed — please try again' }
              : g
          ));
        }
      })();
      return;
    }

    // Duplicate check runs after modal close — if found, re-open modal with warning
    if (!isMultiFile && modalParams.types.length === 1 && modalParams.mode === 'text' && !modalParams.pastedImages?.length) {
      try {
        const dupResult = await studyApi.checkDuplicate({ title: modalParams.title || undefined, guide_type: modalParams.types[0] });
        if (dupResult.exists) {
          setDuplicateCheck(dupResult);
          setShowModal(true);
          return;
        }
      } catch { /* continue */ }
    }

    // When multiple AI tools are selected and no courseContentId yet,
    // pre-create a single CourseContent so all generations share one material (#1061)
    let sharedCourseContentId = modalParams.courseContentId;
    const needsUpload = !sharedCourseContentId && modalParams.types.length > 1;
    const preTempId = needsUpload ? `pre-upload-${Date.now()}` : null;
    if (preTempId) {
      const preTitle = modalParams.title || (files.length > 0 ? files[0].name.replace(/\.[^/.]+$/, '') : 'Uploaded material');
      setGeneratingItems(prev => [...prev, { tempId: preTempId, title: preTitle, guideType: 'upload', status: 'uploading' }]);
    }
    if (needsUpload) {
      try {
        const cId = modalParams.courseId || (await coursesApi.getDefault(filterChild || undefined)).id;
        if (isMultiFile) {
          const cc = await courseContentsApi.uploadMultiFiles(
            files,
            cId,
            modalParams.title || undefined,
            'notes',
          );
          sharedCourseContentId = cc.id;
        } else if (modalParams.mode === 'file' && files.length === 1) {
          const cc = await courseContentsApi.uploadFile(
            files[0],
            cId,
            modalParams.title || undefined,
            'notes',
          );
          sharedCourseContentId = cc.id;
        } else if (modalParams.pastedImages && modalParams.pastedImages.length > 0) {
          // Pasted images: upload as files for shared content
          const allFiles = [...modalParams.pastedImages];
          if (modalParams.content?.trim()) {
            const textBlob = new Blob([modalParams.content], { type: 'text/plain' });
            const textFile = new File([textBlob], 'pasted-content.txt', { type: 'text/plain' });
            allFiles.unshift(textFile);
          }
          if (allFiles.length === 1) {
            const cc = await courseContentsApi.uploadFile(
              allFiles[0],
              cId,
              modalParams.title || undefined,
              'notes',
            );
            sharedCourseContentId = cc.id;
          } else {
            const cc = await courseContentsApi.uploadMultiFiles(
              allFiles,
              cId,
              modalParams.title || undefined,
              'notes',
            );
            sharedCourseContentId = cc.id;
          }
        } else {
          const cc = await courseContentsApi.create({
            course_id: cId,
            title: modalParams.title || 'Uploaded material',
            text_content: modalParams.content || undefined,
            content_type: 'notes',
          });
          sharedCourseContentId = cc.id;
        }
      } catch {
        // If pre-creation fails, fall through — each generation creates its own
      }
    }
    if (preTempId) {
      setGeneratingItems(prev => prev.filter(g => g.tempId !== preTempId));
    }

    setIsGenerating(true);
    try {
      // Fan out: one startGeneration() per selected type (parallel)
      for (const type of modalParams.types) {
        startGeneration({
          title: modalParams.title,
          content: modalParams.content,
          type,
          focusPrompt: modalParams.focusPrompt,
          mode: sharedCourseContentId ? 'text' : (isMultiFile ? 'text' : modalParams.mode),
          file: sharedCourseContentId ? undefined : (isMultiFile ? undefined : modalParams.file),
          files: sharedCourseContentId ? undefined : (isMultiFile ? files : undefined),
          pastedImages: sharedCourseContentId ? undefined : modalParams.pastedImages,
          regenerateId: duplicateCheck?.existing_guide?.id,
          courseId: modalParams.courseId,
          courseContentId: sharedCourseContentId,
          documentType: modalParams.documentType,
          studyGoal: modalParams.studyGoal,
          studyGoalText: modalParams.studyGoalText,
        });
      }
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDatePromptSave = async () => {
    for (const task of datePromptTasks) {
      const newDate = datePromptValues[task.id];
      if (newDate && newDate !== task.due_date) {
        try { await tasksApi.update(task.id, { due_date: newDate }); } catch { /* ignore */ }
      }
    }
    setDatePromptTasks([]);
    setDatePromptValues({});
    loadData();
  };

  const handleDatePromptCancel = () => {
    setDatePromptTasks([]);
    setDatePromptValues({});
    loadData();
  };

  // Toggle selection for batch assign (#623)
  const toggleContentSelection = (id: number) => {
    setSelectedContentIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAllUnlinked = () => {
    const unlinkedIds = filteredContent
      .filter(c => !linkedCourseIds.has(c.course_id))
      .map(c => c.id);
    const allSelected = unlinkedIds.every(id => selectedContentIds.has(id));
    if (allSelected) {
      setSelectedContentIds(new Set());
    } else {
      setSelectedContentIds(new Set(unlinkedIds));
    }
  };

  // Quick assign a single material's course to a child (#623)
  const handleQuickAssign = async (contentItem: CourseContentItem, childStudentId: number) => {
    try {
      const result = await parentApi.assignCoursesToChild(childStudentId, [contentItem.course_id]);
      if (result.assigned.length === 0) {
        showToast('Course could not be assigned — it may already be assigned or not available');
        return;
      }
      showToast(`Assigned "${contentItem.course_name || 'course'}" to child`);
      // Refresh linked data
      const linkedData = await courseContentsApi.getLinkedCourseIds();
      setLinkedCourseIds(new Set(linkedData.linked_course_ids));
      setCourseStudentMap(linkedData.course_student_map);
      setLinkedChildren(linkedData.children);
      setSelectedContentIds(new Set());
    } catch {
      showToast('Failed to assign course to child');
    }
  };

  // Batch assign selected materials' courses to selected children (#623)
  const handleBatchAssign = async () => {
    if (assignTargetChildren.size === 0 || selectedContentIds.size === 0) return;
    setAssigning(true);
    try {
      // Collect unique course IDs from selected content items
      const courseIdsToAssign = [...new Set(
        contentItems
          .filter(c => selectedContentIds.has(c.id))
          .map(c => c.course_id)
      )];
      // Assign to each selected child
      let totalAssigned = 0;
      for (const childSid of assignTargetChildren) {
        const result = await parentApi.assignCoursesToChild(childSid, courseIdsToAssign);
        totalAssigned += result.assigned.length;
      }
      if (totalAssigned === 0) {
        showToast('No courses could be assigned — they may already be assigned or not available');
      } else {
        showToast(`Assigned ${totalAssigned} course(s) to ${assignTargetChildren.size} child(ren)`);
      }
      // Refresh linked data
      const linkedData = await courseContentsApi.getLinkedCourseIds();
      setLinkedCourseIds(new Set(linkedData.linked_course_ids));
      setCourseStudentMap(linkedData.course_student_map);
      setLinkedChildren(linkedData.children);
      setSelectedContentIds(new Set());
      setAssignTargetChildren(new Set());
      setShowAssignModal(false);
    } catch {
      showToast('Failed to assign courses');
    } finally {
      setAssigning(false);
    }
  };

  // Scope course dropdown to courses visible in current content items
  const visibleCourses = useMemo(() => {
    const courseIdsInContent = new Set(contentItems.map(c => c.course_id));
    return courses.filter(c => courseIdsInContent.has(c.id));
  }, [courses, contentItems]);

  // Filtered courses for search dropdown
  const searchFilteredCourses = useMemo(() => {
    if (!courseSearchQuery.trim()) return visibleCourses;
    return visibleCourses.filter(c => c.name.toLowerCase().includes(courseSearchQuery.toLowerCase()));
  }, [visibleCourses, courseSearchQuery]);

  // Apply course + type + text search + assign status filters
  const materialSearchQuery = courseSearchQuery.trim().toLowerCase();
  const filteredContent = contentItems.filter(c => {
    if (filterCourse && c.course_id !== filterCourse) return false;
    if (filterType !== 'all' && !contentGuideMap[c.id]?.includes(filterType)) return false;
    // When text is entered but no specific course selected, filter by title or course name
    if (materialSearchQuery && !filterCourse) {
      const matchesTitle = c.title.toLowerCase().includes(materialSearchQuery);
      const matchesCourse = (c.course_name || '').toLowerCase().includes(materialSearchQuery);
      if (!matchesTitle && !matchesCourse) return false;
    }
    // Assign status filter (#623)
    if (isParent && assignFilter !== 'all') {
      const isLinked = linkedCourseIds.has(c.course_id);
      if (assignFilter === 'unlinked' && isLinked) return false;
      if (assignFilter === 'assigned' && !isLinked) return false;
    }
    return true;
  });

  // Group filtered content by category (#992)
  const groupedByCategory = useMemo(() => {
    const groups: Record<string, CourseContentItem[]> = {};
    const uncategorized: CourseContentItem[] = [];
    for (const item of filteredContent) {
      const cat = item.category || '';
      if (!cat) {
        uncategorized.push(item);
      } else {
        if (!groups[cat]) groups[cat] = [];
        groups[cat].push(item);
      }
    }
    // Sort within each group by display_order
    for (const key of Object.keys(groups)) {
      groups[key].sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0));
    }
    uncategorized.sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0));
    const categoryKeys = Object.keys(groups).sort();
    return { categoryKeys, groups, uncategorized };
  }, [filteredContent]);

  const hasAnyCategories = groupedByCategory.categoryKeys.length > 0;

  // Count unlinked materials for badge display (#623)
  const unlinkedCount = isParent
    ? contentItems.filter(c => !linkedCourseIds.has(c.course_id)).length
    : 0;

  // Apply guide type filter to legacy guides
  const filteredLegacy = filterType === 'all'
    ? legacyGuides
    : legacyGuides.filter(g => g.guide_type === filterType);

  // Count per type for filter tab badges
  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = { all: contentItems.length, study_guide: 0, quiz: 0, flashcards: 0 };
    for (const item of contentItems) {
      const types = contentGuideMap[item.id] || [];
      for (const t of types) {
        if (counts[t] !== undefined) counts[t]++;
      }
    }
    // Add legacy guides
    counts.all += legacyGuides.length;
    for (const g of legacyGuides) {
      if (counts[g.guide_type] !== undefined) counts[g.guide_type]++;
    }
    return counts;
  }, [contentItems, contentGuideMap, legacyGuides]);

  if (loading || loadError) {
    return (
      <DashboardLayout welcomeSubtitle="Manage study materials" showBackButton>
        {loadError ? (
          <div className="no-children-state">
            <h3>Unable to Load Class Materials</h3>
            <p>Something went wrong while loading your class materials. Please try again.</p>
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginTop: '20px' }}>
              <button className="link-child-btn" onClick={() => { setLoading(true); setLoadError(false); loadData(); }}>
                Retry
              </button>
              <button className="cancel-btn btn-secondary" onClick={() => window.location.reload()}>
                Refresh Page
              </button>
            </div>
          </div>
        ) : (
          <PageSkeleton />
        )}
      </DashboardLayout>
    );
  }

  // Render a single content row (extracted for category grouping #992)
  const renderContentRow = (item: CourseContentItem) => {
    const isUnlinked = isParent && linkedChildren.length > 0 && !linkedCourseIds.has(item.course_id);
    return (
      <div key={item.id} className={`guide-row${isUnlinked ? ' guide-row-unlinked' : ''}`}>
        {/* Selection checkbox */}
        <label className="guide-row-checkbox" onClick={(e) => e.stopPropagation()}>
          <input
            type="checkbox"
            checked={selectedContentIds.has(item.id)}
            onChange={() => toggleContentSelection(item.id)}
          />
        </label>
        <div className="guide-row-main" onClick={() => navigateToContent(item)}>
          <span className="guide-row-icon">{contentTypeIcon(item.content_type, item.id)}</span>
          <div className="guide-row-info">
            <span className="guide-row-title">
              {item.title}
              {isUnlinked && (
                <span className="guide-unlinked-badge">Not assigned</span>
              )}
            </span>
            <span className="guide-row-meta">
              {hasSubGuides.has(item.id) && (
                <span className="guide-sub-badge">Has Sub-Guides</span>
              )}
              {item.course_name && (
                <span className="guide-course-badge">{item.course_name}</span>
              )}
              {item.category && (
                <span className="guide-category-badge">{item.category}</span>
              )}
              {contentGuideMap[item.id] && (
                <span className="guide-type-label">
                  {(filterType !== 'all'
                    ? contentGuideMap[item.id].filter(t => t === filterType)
                    : contentGuideMap[item.id]
                  ).map(t => guideTypeLabel(t)).join(', ')}
                </span>
              )}
              <span className="guide-row-date">{new Date(item.created_at).toLocaleDateString()}</span>
            </span>
          </div>
        </div>
        <div className="guide-row-actions">
          {isUnlinked && linkedChildren.length === 1 && (
            <button
              className="guide-assign-btn"
              title={`Assign to ${linkedChildren[0].full_name}`}
              onClick={() => handleQuickAssign(item, linkedChildren[0].student_id)}
            >
              <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path d="M10 4v12M4 10h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
              Assign
            </button>
          )}
          {isUnlinked && linkedChildren.length > 1 && (
            <div className="guide-assign-dropdown">
              <button className="guide-assign-btn" title="Assign to child">
                <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <path d="M10 4v12M4 10h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
                Assign
              </button>
              <div className="guide-assign-dropdown-content">
                {linkedChildren.map(child => (
                  <button
                    key={child.student_id}
                    className="guide-assign-dropdown-item"
                    onClick={() => handleQuickAssign(item, child.student_id)}
                  >
                    {child.full_name}
                  </button>
                ))}
              </div>
            </div>
          )}
          {/* Move to category dropdown (#992) */}
          <div className="guide-assign-dropdown">
            <button className="guide-convert-btn" title="Move to category">&#128193;</button>
            <div className="guide-assign-dropdown-content">
              {item.category && (
                <button className="guide-assign-dropdown-item" onClick={() => handleMoveToCategory(item.id, '')}>
                  Remove from category
                </button>
              )}
              {categories.filter(c => c !== item.category).map(cat => (
                <button key={cat} className="guide-assign-dropdown-item" onClick={() => handleMoveToCategory(item.id, cat)}>
                  {cat}
                </button>
              ))}
              <button
                className="guide-assign-dropdown-item"
                style={{ borderTop: '1px solid var(--color-border)', fontStyle: 'italic' }}
                onClick={() => { setMoveToCategoryContentId(item.id); setNewCategoryName(''); }}
              >
                + New Category
              </button>
            </div>
          </div>
          <button className="guide-convert-btn" title="Edit" onClick={() => setEditContent(item)}>&#9998;</button>
          <button className="guide-convert-btn" title="Move to class" onClick={() => { setReassignContent(item); setCategorizeCourseId(''); setCategorizeSearch(''); setCategorizeNewName(''); }}>&#128194;</button>
          <button className="guide-delete-btn" title="Archive" onClick={() => handleArchiveContent(item.id)}>&#128465;</button>
        </div>
      </div>
    );
  };

  return (
    <DashboardLayout
      welcomeSubtitle="Manage study materials"
      showBackButton
      sidebarActions={[
        { label: '+ Create Study Material', onClick: () => setShowModal(true) },
      ]}
    >
      <div className="guides-page">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Class Materials' },
        ]} />
        <AIWarningBanner />

        {/* Child selector pills (parent only) + add action button */}
        {isParent && children.length > 0 && (
          <div className="guides-child-selector">
            {children.length > 1 && (
              <button
                className={`child-tab child-tab-all${filterChild === '' ? ' active' : ''}`}
                onClick={() => { setFilterChild(''); sessionStorage.removeItem('selectedChildId'); }}
                title="All children"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              </button>
            )}
            {children.map((child, index) => (
              <button
                key={child.user_id}
                className={`child-tab${filterChild === child.user_id ? ' active' : ''}`}
                onClick={() => { setFilterChild(child.user_id); sessionStorage.setItem('selectedChildId', String(child.user_id)); }}
              >
                <span className="child-color-dot" style={{ backgroundColor: CHILD_COLORS[index % CHILD_COLORS.length] }} />
                {child.full_name}
                {child.grade_level != null && <span className="grade-badge">Grade {child.grade_level}</span>}
              </button>
            ))}

            {/* "+" context menu */}
            <div className="add-action-wrapper" ref={childAddMenuRef}>
              <button
                className={`add-action-trigger${showChildAddMenu ? ' active' : ''}`}
                onClick={() => setShowChildAddMenu(v => !v)}
                aria-label="Add new"
              >
                <svg width="16" height="16" viewBox="0 0 18 18" fill="none" aria-hidden="true">
                  <path d="M9 3v12M3 9h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </button>
              {showChildAddMenu && (
                <div className="add-action-popover">
                  <button className="add-action-item" onClick={() => { setShowChildAddMenu(false); setShowCreateCourseModal(true); }}>
                    <span className="add-action-item-icon icon-with-plus">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                      </svg>
                    </span>
                    <span className="add-action-item-label">Create Class</span>
                  </button>
                  <button className="add-action-item" onClick={() => { setShowChildAddMenu(false); setShowModal(true); }}>
                    <span className="add-action-item-icon icon-with-plus">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                      </svg>
                    </span>
                    <span className="add-action-item-label">Create Class Material</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Course search box + Create button */}
        <div className="guides-header">
          <div className="guides-filters-row">
            <div className="guides-course-search" ref={courseSearchRef}>
              <input
                type="text"
                className="guides-course-search-input"
                placeholder="Search classes and materials..."
                value={courseSearchQuery}
                onChange={e => { setCourseSearchQuery(e.target.value); setCourseSearchOpen(true); }}
                onFocus={() => setCourseSearchOpen(true)}
              />
              {(filterCourse || courseSearchQuery) && (
                <button
                  className="guides-course-search-clear"
                  onClick={() => { setFilterCourse(''); setCourseSearchQuery(''); searchParams.delete('course'); setSearchParams(searchParams, { replace: true }); }}
                  aria-label="Clear filter"
                >
                  &times;
                </button>
              )}
              {courseSearchOpen && searchFilteredCourses.length > 0 && (
                <div className="guides-course-dropdown">
                  {filterCourse && (
                    <div
                      className="guides-course-dropdown-item all"
                      onClick={() => { setFilterCourse(''); setCourseSearchQuery(''); searchParams.delete('course'); setSearchParams(searchParams, { replace: true }); setCourseSearchOpen(false); }}
                    >
                      All Classes
                    </div>
                  )}
                  {searchFilteredCourses.map(c => (
                    <div
                      key={c.id}
                      className={`guides-course-dropdown-item${filterCourse === c.id ? ' active' : ''}`}
                      onClick={() => { setFilterCourse(c.id); setCourseSearchQuery(c.name); searchParams.set('course', String(c.id)); setSearchParams(searchParams, { replace: true }); setCourseSearchOpen(false); }}
                    >
                      {c.name}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Guide type filter tabs with counts */}
        <div className="guides-filter">
          {[
            { key: 'all', label: 'All' },
            { key: 'study_guide', label: '\uD83D\uDCD6 Study Guides' },
            { key: 'quiz', label: '\uD83D\uDCCB Quizzes' },
            { key: 'flashcards', label: '\uD83C\uDCCF Flashcards' },
          ].map(tab => (
            <button
              key={tab.key}
              className={`guides-filter-btn${filterType === tab.key ? ' active' : ''}`}
              onClick={() => { setFilterType(tab.key); if (tab.key === 'all') { searchParams.delete('type'); } else { searchParams.set('type', tab.key); } setSearchParams(searchParams, { replace: true }); }}
            >
              {tab.label}
              {typeCounts[tab.key] > 0 && <span className="filter-count">{typeCounts[tab.key]}</span>}
            </button>
          ))}
        </div>

        {/* Assign status filter (parent only) (#623) */}
        {isParent && linkedChildren.length > 0 && (
          <div className="guides-assign-filter">
            <span className="guides-assign-filter-label">Assignment:</span>
            {([
              { key: 'all' as const, label: 'All' },
              { key: 'unlinked' as const, label: 'Unlinked', count: unlinkedCount },
              { key: 'assigned' as const, label: 'Assigned' },
            ]).map(tab => (
              <button
                key={tab.key}
                className={`guides-assign-filter-btn${assignFilter === tab.key ? ' active' : ''}${tab.key === 'unlinked' && unlinkedCount > 0 ? ' has-unlinked' : ''}`}
                onClick={() => setAssignFilter(tab.key)}
              >
                {tab.label}
                {tab.count !== undefined && tab.count > 0 && (
                  <span className="assign-filter-count">{tab.count}</span>
                )}
              </button>
            ))}
            {selectedContentIds.size > 0 && (
              <button
                className="guides-batch-assign-btn"
                onClick={() => { setAssignTargetChildren(new Set()); setShowAssignModal(true); }}
              >
                Assign {selectedContentIds.size} to Child
              </button>
            )}
          </div>
        )}

        {/* Course content items */}
        <div className="guides-section">
          <div className="guides-section-header-row">
            <button className="collapse-toggle" onClick={() => setMaterialsExpanded(v => !v)}>
              <span className={`section-chevron${materialsExpanded ? ' expanded' : ''}`}>&#9654;</span>
              <h3>Class Materials ({filteredContent.length + generatingItems.length})</h3>
            </button>
            <button className="title-add-btn" onClick={() => setShowModal(true)} title="Create Class Material" aria-label="Create Class Material">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
            </button>
            {isParent && materialsExpanded && assignFilter === 'unlinked' && filteredContent.some(c => !linkedCourseIds.has(c.course_id)) && (
              <button className="guides-select-all-btn" onClick={toggleSelectAllUnlinked}>
                {filteredContent.filter(c => !linkedCourseIds.has(c.course_id)).every(c => selectedContentIds.has(c.id))
                  ? 'Deselect All'
                  : 'Select All Unlinked'}
              </button>
            )}
          </div>
          {materialsExpanded && (filteredContent.length > 0 || generatingItems.length > 0) ? (
            <>
              {/* In-progress generation placeholders */}
              {generatingItems.length > 0 && (
                <div className="guides-list">
                  {generatingItems.map(item => (
                    <div key={item.tempId} className={`guide-row ${item.status === 'error' ? 'guide-row-error' : 'guide-row-generating'}`}>
                      <div className="guide-row-main">
                        <span className="guide-row-icon">
                          {item.status === 'error' ? '\u26A0\uFE0F' : <LottieLoader size={28} />}
                        </span>
                        <div className="guide-row-info">
                          <span className="guide-row-title">{item.title}</span>
                          <span className="guide-row-meta">
                            {item.status === 'uploading'
                              ? <span className="generating-text">Uploading...</span>
                              : item.status === 'generating'
                              ? <span className="generating-text">Generating {guideTypeLabel(item.guideType)}...</span>
                              : <span className="error-text">{item.error}</span>
                            }
                          </span>
                        </div>
                      </div>
                      {item.status === 'error' && (
                        <div className="guide-row-actions">
                          <button className="guide-delete-btn" onClick={() => setGeneratingItems(prev => prev.filter(g => g.tempId !== item.tempId))}>
                            &times;
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Category groups (#992) */}
              {groupedByCategory.categoryKeys.map(cat => (
                <div key={cat} className="guides-category-group">
                  <button className="collapse-toggle category-toggle" onClick={() => toggleCategoryCollapse(cat)}>
                    <span className={`section-chevron${!collapsedCategories.has(cat) ? ' expanded' : ''}`}>&#9654;</span>
                    <span className="category-name">{cat}</span>
                    <span className="category-count">({groupedByCategory.groups[cat].length})</span>
                  </button>
                  {!collapsedCategories.has(cat) && (
                    <div className="guides-list">
                      {groupedByCategory.groups[cat].map(item => renderContentRow(item))}
                    </div>
                  )}
                </div>
              ))}

              {/* Uncategorized items */}
              {groupedByCategory.uncategorized.length > 0 && (
                <div className="guides-category-group">
                  {hasAnyCategories && (
                    <button className="collapse-toggle category-toggle" onClick={() => toggleCategoryCollapse('__uncategorized__')}>
                      <span className={`section-chevron${!collapsedCategories.has('__uncategorized__') ? ' expanded' : ''}`}>&#9654;</span>
                      <span className="category-name">Uncategorized</span>
                      <span className="category-count">({groupedByCategory.uncategorized.length})</span>
                    </button>
                  )}
                  {!collapsedCategories.has('__uncategorized__') && (
                    <div className="guides-list">
                      {groupedByCategory.uncategorized.map(item => renderContentRow(item))}
                    </div>
                  )}
                </div>
              )}

              {/* Bulk categorize action (#992) */}
              {selectedContentIds.size > 0 && (
                <div className="bulk-category-bar">
                  <span>{selectedContentIds.size} selected</span>
                  <select
                    value={moveCategoryTarget}
                    onChange={e => setMoveCategoryTarget(e.target.value)}
                    className="bulk-category-select"
                  >
                    <option value="">Move to category...</option>
                    {categories.map(c => <option key={c} value={c}>{c}</option>)}
                    <option value="__new__">+ New Category</option>
                  </select>
                  {moveCategoryTarget === '__new__' && (
                    <input
                      className="bulk-category-input"
                      value={newCategoryName}
                      onChange={e => setNewCategoryName(e.target.value)}
                      placeholder="Category name"
                      maxLength={100}
                    />
                  )}
                  <button
                    className="guides-batch-assign-btn"
                    disabled={bulkCategorizing || (!moveCategoryTarget || (moveCategoryTarget === '__new__' && !newCategoryName.trim()))}
                    onClick={() => handleBulkCategorize(moveCategoryTarget === '__new__' ? newCategoryName.trim() : moveCategoryTarget)}
                  >
                    {bulkCategorizing ? 'Moving...' : 'Move'}
                  </button>
                  <button
                    className="guides-batch-assign-btn bulk-archive-btn"
                    disabled={bulkArchiving}
                    onClick={handleBulkArchive}
                    title="Archive selected materials"
                  >
                    {bulkArchiving ? 'Archiving...' : `🗑️ Archive (${selectedContentIds.size})`}
                  </button>
                </div>
              )}
            </>
          ) : materialsExpanded ? (
            <EmptyState
              icon={<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="12" y1="18" x2="12" y2="12" /><line x1="9" y1="15" x2="15" y2="15" /></svg>}
              title="No materials yet"
              description="Upload class documents to generate study guides, quizzes, and flashcards."
              action={{ label: 'Upload Your First Document', onClick: () => setShowModal(true) }}
            />
          ) : null}
        </div>

        {/* Archive section */}
        <div className="guides-section archived-section">
          <button className="collapse-toggle" onClick={() => setShowArchived(!showArchived)}>
            <span className={`section-chevron${showArchived ? ' expanded' : ''}`}>&#9654;</span>
            <h3>Archived ({archivedContents.length + archivedGuides.length})</h3>
          </button>
        {showArchived && (archivedContents.length > 0 || archivedGuides.length > 0) && (
            <div className="guides-list">
              {archivedContents.map(item => (
                <div key={`ac-${item.id}`} className="guide-row guide-row-archived">
                  <div className="guide-row-main">
                    <span className="guide-row-icon">{contentTypeIcon(item.content_type)}</span>
                    <div className="guide-row-info">
                      <span className="guide-row-title">{item.title}</span>
                      <span className="guide-row-meta">
                        {item.course_name && <span className="guide-course-badge">{item.course_name}</span>}
                        <span className="guide-row-date">Archived {new Date(item.archived_at!).toLocaleDateString()}</span>
                      </span>
                    </div>
                  </div>
                  <div className="guide-row-actions">
                    <button className="guide-convert-btn" title="Restore" onClick={() => handleRestoreContent(item.id)}>&#8634;</button>
                    <button className="guide-delete-btn" title="Delete permanently" onClick={() => handlePermanentDeleteContent(item.id)}>&#128465;</button>
                  </div>
                </div>
              ))}
              {archivedGuides.map(guide => (
                <div key={`ag-${guide.id}`} className="guide-row guide-row-archived">
                  <div className="guide-row-main">
                    <span className="guide-row-icon">
                      {guide.guide_type === 'quiz' ? '\u2753' : guide.guide_type === 'flashcards' ? '\uD83C\uDCCF' : '\uD83D\uDCD6'}
                    </span>
                    <div className="guide-row-info">
                      <span className="guide-row-title">{guide.title}</span>
                      <span className="guide-row-meta">
                        <span className="guide-type-label">{guideTypeLabel(guide.guide_type)}</span>
                        <span className="guide-row-date">Archived {new Date(guide.archived_at!).toLocaleDateString()}</span>
                      </span>
                    </div>
                  </div>
                  <div className="guide-row-actions">
                    <button className="guide-convert-btn" title="Restore" onClick={() => handleRestoreGuide(guide.id)}>&#8634;</button>
                    <button className="guide-delete-btn" title="Delete permanently" onClick={() => handlePermanentDeleteGuide(guide.id)}>&#128465;</button>
                  </div>
                </div>
              ))}
            </div>
        )}
        </div>

        {/* Legacy study guides (no course_content_id) */}
        {filteredLegacy.length > 0 && (
          <div className="guides-section">
            <h3>Ungrouped Study Guides ({filteredLegacy.length})</h3>
            <div className="guides-list">
              {filteredLegacy.map(guide => (
                <div key={guide.id} className="guide-row">
                  <div className="guide-row-main" onClick={() => navigateToLegacyGuide(guide)}>
                    <span className="guide-row-icon">
                      {guide.guide_type === 'quiz' ? '?' : guide.guide_type === 'flashcards' ? '\uD83C\uDCCF' : '\uD83D\uDCD6'}
                    </span>
                    <div className="guide-row-info">
                      <span className="guide-row-title">{guide.title}</span>
                      <span className="guide-row-meta">
                        {guideTypeLabel(guide.guide_type)}
                        {guide.version > 1 && <span className="version-badge">v{guide.version}</span>}
                        <span className="guide-row-date">{new Date(guide.created_at).toLocaleDateString()}</span>
                        {isParent && sharedStatus.get(guide.id)?.status === 'viewed' && (
                          <span className="guide-share-badge guide-share-viewed">Viewed</span>
                        )}
                        {isParent && sharedStatus.get(guide.id)?.status === 'shared' && (
                          <span className="guide-share-badge guide-share-sent">Shared</span>
                        )}
                      </span>
                    </div>
                  </div>
                  <div className="guide-row-actions">
                    {/* Share with child (#1414) */}
                    {isParent && children.length === 1 && !sharedStatus.get(guide.id)?.shared_with_user_id && (
                      <button
                        className="guide-convert-btn guide-share-btn"
                        title={`Share with ${children[0].full_name}`}
                        disabled={sharingGuideId === guide.id}
                        onClick={() => handleShareGuide(guide.id, children[0].student_id)}
                      >
                        {sharingGuideId === guide.id ? '...' : 'Share'}
                      </button>
                    )}
                    {isParent && children.length > 1 && !sharedStatus.get(guide.id)?.shared_with_user_id && (
                      <div className="guide-assign-dropdown">
                        <button className="guide-convert-btn guide-share-btn" title="Share with child" disabled={sharingGuideId === guide.id}>
                          {sharingGuideId === guide.id ? '...' : 'Share'}
                        </button>
                        <div className="guide-assign-dropdown-content">
                          {children.map(child => (
                            <button
                              key={child.student_id}
                              className="guide-assign-dropdown-item"
                              onClick={() => handleShareGuide(guide.id, child.student_id)}
                            >
                              {child.full_name}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                    {guide.guide_type !== 'quiz' && (
                      <button className="guide-convert-btn" title="Generate quiz" onClick={() => handleConvertGuide(guide, 'quiz')}>
                        &#10067;
                      </button>
                    )}
                    {guide.guide_type !== 'flashcards' && (
                      <button className="guide-convert-btn" title="Generate flashcards" onClick={() => handleConvertGuide(guide, 'flashcards')}>
                        &#127183;
                      </button>
                    )}
                    {guide.guide_type !== 'study_guide' && (
                      <button className="guide-convert-btn" title="Generate study guide" onClick={() => handleConvertGuide(guide, 'study_guide')}>
                        &#128214;
                      </button>
                    )}
                    <button
                      className="guide-convert-btn"
                      title="Create task"
                      onClick={() => setTaskModalGuide(guide)}
                    >
                      &#128203;
                    </button>
                    <button
                      className="guide-convert-btn"
                      title="Move to class"
                      onClick={() => { setCategorizeGuide(guide); setCategorizeCourseId(''); }}
                    >
                      &#128194;
                    </button>
                    <button className="guide-delete-btn" title="Delete" onClick={() => handleDeleteLegacyGuide(guide.id)}>
                      &#128465;
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Shared by Parent section for students (#1414) */}
        {isStudent && sharedWithMe.length > 0 && (
          <div className="guides-section">
            <h3>Shared by Parent ({sharedWithMe.length})</h3>
            <div className="guides-list">
              {sharedWithMe.map(guide => (
                <div key={`shared-${guide.id}`} className="guide-row">
                  <div className="guide-row-main" onClick={() => {
                    if (guide.course_content_id) {
                      const tabMap: Record<string, string> = { quiz: 'quiz', flashcards: 'flashcards', study_guide: 'guide', mind_map: 'mindmap' };
                      navigate(`/course-materials/${guide.course_content_id}?tab=${tabMap[guide.guide_type] || 'guide'}`);
                    } else if (guide.guide_type === 'quiz') navigate(`/study/quiz/${guide.id}`);
                    else if (guide.guide_type === 'flashcards') navigate(`/study/flashcards/${guide.id}`);
                    else navigate(`/study/guide/${guide.id}`);
                  }}>
                    <span className="guide-row-icon">
                      {guide.guide_type === 'quiz' ? '?' : guide.guide_type === 'flashcards' ? '\uD83C\uDCCF' : '\uD83D\uDCD6'}
                    </span>
                    <div className="guide-row-info">
                      <span className="guide-row-title">
                        {guide.title}
                        <span className="guide-share-badge guide-share-from-parent">From {guide.shared_by_name}</span>
                      </span>
                      <span className="guide-row-meta">
                        {guideTypeLabel(guide.guide_type)}
                        <span className="guide-row-date">Shared {new Date(guide.shared_at).toLocaleDateString()}</span>
                        {guide.viewed_at && <span className="guide-share-badge guide-share-viewed">Viewed</span>}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Study Tools Modal */}
      <UploadMaterialWizard
        open={showModal}
        onClose={() => { resetModal(); setWizardChildId(''); }}
        onGenerate={handleGenerateFromModal}
        isGenerating={isGenerating}
        courses={wizardCourses}
        materials={modalMaterials}
        selectedCourseId={modalCourseId}
        onCourseChange={setModalCourseId}
        selectedMaterialId={modalMaterialId}
        onMaterialChange={setModalMaterialId}
        duplicateCheck={duplicateCheck}
        onViewExisting={() => {
          const guide = duplicateCheck?.existing_guide;
          if (guide) { resetModal(); setWizardChildId(''); navigateToLegacyGuide(guide); }
        }}
        onRegenerate={() => {
          if (lastGenerateParamsRef.current) {
            const params = lastGenerateParamsRef.current;
            setDuplicateCheck(null);
            resetModal();
            for (const type of params.types) {
              startGeneration({
                title: params.title,
                content: params.content,
                type,
                focusPrompt: params.focusPrompt,
                mode: params.mode,
                file: params.file,
                pastedImages: params.pastedImages,
                regenerateId: duplicateCheck?.existing_guide?.id,
                courseId: params.courseId,
                courseContentId: params.courseContentId,
                documentType: params.documentType,
                studyGoal: params.studyGoal,
                studyGoalText: params.studyGoalText,
              });
            }
          }
        }}
        onDismissDuplicate={() => setDuplicateCheck(null)}
        showParentNote={user?.role === 'student'}
        childName={isParent ? (wizardChildId ? children.find(c => c.user_id === wizardChildId || c.student_id === wizardChildId)?.full_name : (children.length === 1 ? children[0].full_name : undefined)) : undefined}
        children={isParent && children.length > 0 ? children.map(c => ({ id: c.student_id, name: c.full_name })) : undefined}
        onChildChange={(studentId) => {
          const child = children.find(c => c.student_id === studentId);
          setWizardChildId(child ? child.user_id : studentId);
        }}
      />

      <CreateTaskModal
        open={!!taskModalGuide}
        onClose={() => setTaskModalGuide(null)}
        prefillTitle={taskModalGuide ? `Review: ${taskModalGuide.title}` : ''}
        studyGuideId={taskModalGuide?.id}
        courseId={taskModalGuide?.course_id ?? undefined}
        linkedEntityLabel={taskModalGuide ? `Study Guide: ${taskModalGuide.title}` : undefined}
      />
      {/* Categorize modal */}
      {categorizeGuide && (
        <div className="modal-overlay" onClick={() => setCategorizeGuide(null)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Move to Class" ref={categorizeModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Move to Class</h2>
            <p className="modal-desc">Assign &ldquo;{categorizeGuide.title}&rdquo; to a class.</p>
            <div className="modal-form">
              <input
                type="text"
                placeholder="Search classes or type a new name..."
                value={categorizeSearch}
                onChange={(e) => { setCategorizeSearch(e.target.value); setCategorizeCourseId(''); setCategorizeNewName(''); }}
                autoFocus
              />
              <div className="categorize-list">
                {courses
                  .filter(c => !categorizeSearch || c.name.toLowerCase().includes(categorizeSearch.toLowerCase()))
                  .map(c => (
                    <div
                      key={c.id}
                      className={`categorize-item${categorizeCourseId === c.id ? ' selected' : ''}`}
                      onClick={() => { setCategorizeCourseId(c.id); setCategorizeNewName(''); }}
                    >
                      &#127891; {c.name}
                    </div>
                  ))
                }
                {categorizeSearch.trim() && !courses.some(c => c.name.toLowerCase() === categorizeSearch.trim().toLowerCase()) && (
                  <div
                    className={`categorize-item create-new${categorizeNewName ? ' selected' : ''}`}
                    onClick={() => { setCategorizeNewName(categorizeSearch.trim()); setCategorizeCourseId(''); }}
                  >
                    &#10133; Create &ldquo;{categorizeSearch.trim()}&rdquo;
                  </div>
                )}
                {categorizeSearch && courses.filter(c => c.name.toLowerCase().includes(categorizeSearch.toLowerCase())).length === 0 && !categorizeSearch.trim() && (
                  <div className="categorize-empty">No classes found</div>
                )}
              </div>
            </div>
            <div className="modal-actions">
              <button className="cancel-btn btn-secondary" onClick={() => setCategorizeGuide(null)}>Cancel</button>
              {categorizeNewName ? (
                <button className="generate-btn btn-primary" disabled={categorizeCreating} onClick={handleCreateAndCategorize}>
                  {categorizeCreating ? 'Creating...' : 'Create & Move'}
                </button>
              ) : (
                <button className="generate-btn btn-primary" disabled={!categorizeCourseId} onClick={() => handleCategorize()}>Move</button>
              )}
            </div>
          </div>
        </div>
      )}
      {/* Edit material modal */}
      {editContent && (
        <EditMaterialModal
          material={editContent}
          courses={courses}
          onClose={() => setEditContent(null)}
          onSaved={() => { setEditContent(null); loadData(); showToast('Material updated'); }}
        />
      )}
      {/* Reassign content to course modal */}
      {reassignContent && (
        <div className="modal-overlay" onClick={() => setReassignContent(null)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Move to Class" ref={reassignModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Move to Class</h2>
            <p className="modal-desc">Assign &ldquo;{reassignContent.title}&rdquo; to a class.</p>
            <div className="modal-form">
              <input
                type="text"
                placeholder="Search classes or type a new name..."
                value={categorizeSearch}
                onChange={(e) => { setCategorizeSearch(e.target.value); setCategorizeCourseId(''); setCategorizeNewName(''); }}
                autoFocus
              />
              <div className="categorize-list">
                {courses
                  .filter(c => !categorizeSearch || c.name.toLowerCase().includes(categorizeSearch.toLowerCase()))
                  .map(c => (
                    <div
                      key={c.id}
                      className={`categorize-item${categorizeCourseId === c.id ? ' selected' : ''}${c.id === reassignContent.course_id ? ' current' : ''}`}
                      onClick={() => { setCategorizeCourseId(c.id); setCategorizeNewName(''); }}
                    >
                      &#127891; {c.name}{c.id === reassignContent.course_id ? ' (current)' : ''}
                    </div>
                  ))
                }
                {categorizeSearch.trim() && !courses.some(c => c.name.toLowerCase() === categorizeSearch.trim().toLowerCase()) && (
                  <div
                    className={`categorize-item create-new${categorizeNewName ? ' selected' : ''}`}
                    onClick={() => { setCategorizeNewName(categorizeSearch.trim()); setCategorizeCourseId(''); }}
                  >
                    &#10133; Create &ldquo;{categorizeSearch.trim()}&rdquo;
                  </div>
                )}
              </div>
            </div>
            <div className="modal-actions">
              <button className="cancel-btn btn-secondary" onClick={() => setReassignContent(null)}>Cancel</button>
              {categorizeNewName ? (
                <button className="generate-btn btn-primary" disabled={categorizeCreating} onClick={handleCreateAndReassign}>
                  {categorizeCreating ? 'Creating...' : 'Create & Move'}
                </button>
              ) : (
                <button className="generate-btn btn-primary" disabled={!categorizeCourseId || categorizeCourseId === reassignContent.course_id} onClick={() => handleReassignContent()}>Move</button>
              )}
            </div>
          </div>
        </div>
      )}
      {/* Date prompt for auto-created tasks */}
      {datePromptTasks.length > 0 && (
        <div className="modal-overlay" onClick={handleDatePromptCancel}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Tasks Created" ref={datePromptModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Tasks Created</h2>
            <p className="modal-desc">
              {datePromptTasks.length === 1
                ? 'A task was auto-created from your class material. Set the action date:'
                : `${datePromptTasks.length} tasks were auto-created from your class material. Set the action dates:`}
            </p>
            <div className="modal-form">
              {datePromptTasks.map(task => (
                <label key={task.id}>
                  {task.title}
                  <input
                    type="date"
                    value={datePromptValues[task.id] || ''}
                    onChange={(e) => setDatePromptValues(prev => ({ ...prev, [task.id]: e.target.value }))}
                  />
                </label>
              ))}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn btn-secondary" onClick={handleDatePromptCancel}>Skip</button>
              <button className="generate-btn btn-primary" onClick={handleDatePromptSave}>Save Dates</button>
            </div>
          </div>
        </div>
      )}
      {/* Batch assign modal (#623) */}
      {showAssignModal && (
        <div className="modal-overlay" onClick={() => setShowAssignModal(false)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Assign to Children" ref={assignModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Assign to Children</h2>
            <p className="modal-desc">
              Assign {selectedContentIds.size} material(s) to your children. This will enroll them in the associated course(s).
            </p>
            <div className="modal-form">
              <div className="assign-children-list">
                {linkedChildren.map(child => (
                  <label key={child.student_id} className="assign-child-item">
                    <input
                      type="checkbox"
                      checked={assignTargetChildren.has(child.student_id)}
                      onChange={() => {
                        setAssignTargetChildren(prev => {
                          const next = new Set(prev);
                          if (next.has(child.student_id)) next.delete(child.student_id);
                          else next.add(child.student_id);
                          return next;
                        });
                      }}
                    />
                    <span className="assign-child-name">{child.full_name}</span>
                  </label>
                ))}
              </div>
              <div className="assign-materials-summary">
                <strong>Classes to assign:</strong>
                <ul>
                  {[...new Set(
                    contentItems
                      .filter(c => selectedContentIds.has(c.id))
                      .map(c => c.course_name || `Class #${c.course_id}`)
                  )].map(name => (
                    <li key={name}>{name}</li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="modal-actions">
              <button className="cancel-btn btn-secondary" onClick={() => setShowAssignModal(false)}>Cancel</button>
              <button
                className="generate-btn btn-primary"
                disabled={assignTargetChildren.size === 0 || assigning}
                onClick={handleBatchAssign}
              >
                {assigning ? 'Assigning...' : `Assign to ${assignTargetChildren.size} Child${assignTargetChildren.size !== 1 ? 'ren' : ''}`}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Create Course Modal */}
      {showCreateCourseModal && (
        <div className="modal-overlay" onClick={() => { setShowCreateCourseModal(false); setCreateCourseError(''); }}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Create Class" ref={createCourseModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Create Class</h2>
            <p className="modal-desc">Create a new class for your child.</p>
            <div className="modal-form">
              <label>
                Class Name *
                <input type="text" value={newCourseName} onChange={(e) => setNewCourseName(e.target.value)} placeholder="e.g. Math Grade 5" disabled={createCourseLoading} onKeyDown={(e) => e.key === 'Enter' && handleCreateCourse()} autoFocus />
              </label>
              <label>
                Subject (optional)
                <input type="text" value={newCourseSubject} onChange={(e) => setNewCourseSubject(e.target.value)} placeholder="e.g. Mathematics" disabled={createCourseLoading} />
              </label>
              <label>
                Description (optional)
                <textarea value={newCourseDescription} onChange={(e) => setNewCourseDescription(e.target.value)} placeholder="Class details..." rows={3} disabled={createCourseLoading} />
              </label>
              <label>
                Teacher Email (optional)
                <input type="email" value={newCourseTeacherEmail} onChange={(e) => setNewCourseTeacherEmail(e.target.value)} placeholder="teacher@example.com" disabled={createCourseLoading} />
              </label>
              {createCourseError && <p className="link-error">{createCourseError}</p>}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn btn-secondary" onClick={() => { setShowCreateCourseModal(false); setCreateCourseError(''); }} disabled={createCourseLoading}>Cancel</button>
              <button className="generate-btn btn-primary" onClick={handleCreateCourse} disabled={createCourseLoading || !newCourseName.trim()}>
                {createCourseLoading ? 'Creating...' : 'Create Class'}
              </button>
            </div>
          </div>
        </div>
      )}
      {confirmModal}
      <AILimitRequestModal open={showLimitModal} onClose={() => setShowLimitModal(false)} />
      {/* New Category modal (#992) */}
      {moveToCategoryContentId !== null && (
        <div className="modal-overlay" onClick={() => setMoveToCategoryContentId(null)}>
          <div className="modal-content modal-sm" onClick={e => e.stopPropagation()}>
            <h3>New Category</h3>
            <input
              className="modal-input"
              value={newCategoryName}
              onChange={e => setNewCategoryName(e.target.value)}
              placeholder="Category name"
              maxLength={100}
              autoFocus
              onKeyDown={e => {
                if (e.key === 'Enter' && newCategoryName.trim()) {
                  handleMoveToCategory(moveToCategoryContentId, newCategoryName.trim());
                }
              }}
            />
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setMoveToCategoryContentId(null)}>Cancel</button>
              <button
                className="btn-primary"
                disabled={!newCategoryName.trim()}
                onClick={() => handleMoveToCategory(moveToCategoryContentId, newCategoryName.trim())}
              >
                Create & Move
              </button>
            </div>
          </div>
        </div>
      )}
      {toast && <div className="toast-notification">{toast}</div>}
    </DashboardLayout>
  );
}
