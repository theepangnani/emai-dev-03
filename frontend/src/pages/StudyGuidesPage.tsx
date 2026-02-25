import { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { studyApi, parentApi, courseContentsApi, coursesApi, tasksApi } from '../api/client';
import type { StudyGuide, DuplicateCheckResponse, ChildSummary, CourseContentItem, AutoCreatedTask } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { CreateTaskModal } from '../components/CreateTaskModal';
import { useConfirm } from '../components/ConfirmModal';
import { PageSkeleton } from '../components/Skeleton';
import { LottieLoader } from '../components/LottieLoader';
import { AddActionButton } from '../components/AddActionButton';
import { PageNav } from '../components/PageNav';
import { CHILD_COLORS } from '../components/parent/useParentDashboard';
import CreateStudyMaterialModal, { type StudyMaterialGenerateParams } from '../components/CreateStudyMaterialModal';
import { EditMaterialModal } from '../components/EditMaterialModal';
import './StudyGuidesPage.css';

// Cross-page generation queue (ParentDashboard -> StudyGuidesPage)
interface PendingGeneration {
  title: string;
  content: string;
  type: 'study_guide' | 'quiz' | 'flashcards';
  focusPrompt?: string;
  mode: 'text' | 'file';
  file?: File;
  pastedImages?: File[];
  regenerateId?: number;
  courseId?: number;
  courseContentId?: number;
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
  status: 'generating' | 'error';
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

  // Course content items (primary list)
  const [contentItems, setContentItems] = useState<CourseContentItem[]>([]);
  // Legacy study guides without course_content_id
  const [legacyGuides, setLegacyGuides] = useState<StudyGuide[]>([]);
  // Map of course_content_id -> guide_types for filtering
  const [contentGuideMap, setContentGuideMap] = useState<Record<number, string[]>>({});
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
    }, 15000);
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

  const loadData = async () => {
    setLoadError(false);
    try {
      const contentParams: Record<string, any> = {};
      if (filterChild) contentParams.student_user_id = filterChild;
      const [contents, allGuides, courseList] = await Promise.all([
        courseContentsApi.listAll(contentParams),
        studyApi.listGuides(),
        coursesApi.list(),
      ]);
      setContentItems(contents);
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

      if (isParent) {
        const childrenData = await parentApi.getChildren();
        setChildren(childrenData);
      }
    } catch {
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
    if (guide.guide_type === 'quiz') navigate(`/study/quiz/${guide.id}`);
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
      if (guideTypes.includes('quiz')) return '\u2753';
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
    setGeneratingItems(prev => [...prev, { tempId, title: displayTitle, guideType: params.type, status: 'generating' }]);

    (async () => {
      try {
        let result: any;
        if (params.mode === 'file' && params.file) {
          result = await studyApi.generateFromFile({
            file: params.file, title: params.title || undefined, guide_type: params.type,
            num_questions: params.type === 'quiz' ? 10 : undefined,
            num_cards: params.type === 'flashcards' ? 15 : undefined,
            course_id: params.courseId, course_content_id: params.courseContentId,
            focus_prompt: params.focusPrompt,
          });
        } else if (params.pastedImages && params.pastedImages.length > 0) {
          result = await studyApi.generateFromTextAndImages({
            content: params.content,
            images: params.pastedImages,
            title: params.title || undefined,
            guide_type: params.type,
            num_questions: params.type === 'quiz' ? 10 : undefined,
            num_cards: params.type === 'flashcards' ? 15 : undefined,
            course_id: params.courseId,
            course_content_id: params.courseContentId,
            focus_prompt: params.focusPrompt,
          });
        } else if (params.type === 'study_guide') {
          result = await studyApi.generateGuide({ title: params.title, content: params.content, regenerate_from_id: params.regenerateId, course_id: params.courseId, course_content_id: params.courseContentId, focus_prompt: params.focusPrompt });
        } else if (params.type === 'quiz') {
          result = await studyApi.generateQuiz({ topic: params.title, content: params.content, num_questions: 10, regenerate_from_id: params.regenerateId, course_id: params.courseId, course_content_id: params.courseContentId, focus_prompt: params.focusPrompt });
        } else {
          result = await studyApi.generateFlashcards({ topic: params.title, content: params.content, num_cards: 15, regenerate_from_id: params.regenerateId, course_id: params.courseId, course_content_id: params.courseContentId, focus_prompt: params.focusPrompt });
        }
        setGeneratingItems(prev => prev.filter(g => g.tempId !== tempId));
        loadData();

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

  const handleGenerateFromModal = async (modalParams: StudyMaterialGenerateParams) => {
    if (generatingRef.current) return;
    lastGenerateParamsRef.current = modalParams;

    setIsGenerating(true);
    try {
      // Upload-only mode: no AI types selected → create course content directly
      if (modalParams.types.length === 0) {
        try {
          const courseId = modalParams.courseId
            ?? (await coursesApi.getDefault()).id;
          if (modalParams.mode === 'file' && modalParams.file) {
            // File upload: save original file + extract text on backend
            await courseContentsApi.uploadFile(
              modalParams.file,
              courseId,
              modalParams.title || undefined,
              'notes',
            );
          } else {
            // Text/paste mode: create content with text only
            await courseContentsApi.create({
              course_id: courseId,
              title: modalParams.title || 'Uploaded material',
              text_content: modalParams.content || undefined,
              content_type: 'notes',
            });
          }
          resetModal();
          loadData();
        } catch {
          // Silently handle — user will see content list refresh
        }
        return;
      }

      // Check for duplicates only when single type selected (skip for multi-select)
      if (modalParams.types.length === 1 && modalParams.mode === 'text' && !modalParams.pastedImages?.length) {
        try {
          const dupResult = await studyApi.checkDuplicate({ title: modalParams.title || undefined, guide_type: modalParams.types[0] });
          if (dupResult.exists) { setDuplicateCheck(dupResult); return; }
        } catch { /* continue */ }
      }

      setDuplicateCheck(null);
      resetModal();

      // Fan out: one startGeneration() per selected type (parallel)
      for (const type of modalParams.types) {
        startGeneration({
          title: modalParams.title,
          content: modalParams.content,
          type,
          focusPrompt: modalParams.focusPrompt,
          mode: modalParams.mode,
          file: modalParams.file,
          pastedImages: modalParams.pastedImages,
          regenerateId: duplicateCheck?.existing_guide?.id,
          courseId: modalParams.courseId,
          courseContentId: modalParams.courseContentId,
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
  };

  const handleDatePromptCancel = () => {
    setDatePromptTasks([]);
    setDatePromptValues({});
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

  // Apply course + type + text search filters
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
    return true;
  });

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
              <button className="cancel-btn" onClick={() => window.location.reload()}>
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

        {/* Child selector pills (parent only) + add action button */}
        {isParent && children.length > 0 && (
          <div className="guides-child-selector">
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
            <AddActionButton actions={[
              { icon: '\u{1F4DD}', label: 'Upload Document', onClick: () => setShowModal(true) },
            ]} />
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
            { key: 'quiz', label: '\u2753 Quizzes' },
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

        {/* Course content items */}
        <div className="guides-section">
          <button className="collapse-toggle" onClick={() => setMaterialsExpanded(v => !v)}>
            <span className={`section-chevron${materialsExpanded ? ' expanded' : ''}`}>&#9654;</span>
            <h3>Class Materials ({filteredContent.length + generatingItems.length})</h3>
          </button>
          {materialsExpanded && (filteredContent.length > 0 || generatingItems.length > 0) ? (
            <div className="guides-list">
              {/* In-progress generation placeholders */}
              {generatingItems.map(item => (
                <div key={item.tempId} className={`guide-row ${item.status === 'generating' ? 'guide-row-generating' : 'guide-row-error'}`}>
                  <div className="guide-row-main">
                    <span className="guide-row-icon">
                      {item.status === 'generating' ? <LottieLoader size={28} /> : '\u26A0\uFE0F'}
                    </span>
                    <div className="guide-row-info">
                      <span className="guide-row-title">{item.title}</span>
                      <span className="guide-row-meta">
                        {item.status === 'generating'
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
              {filteredContent.map(item => (
                <div key={item.id} className="guide-row">
                  <div className="guide-row-main" onClick={() => navigateToContent(item)}>
                    <span className="guide-row-icon">{contentTypeIcon(item.content_type, item.id)}</span>
                    <div className="guide-row-info">
                      <span className="guide-row-title">{item.title}</span>
                      <span className="guide-row-meta">
                        {item.course_name && (
                          <span className="guide-course-badge">{item.course_name}</span>
                        )}
                        <span className="guide-type-label">
                          {contentGuideMap[item.id]
                            ? contentGuideMap[item.id].map(t => guideTypeLabel(t)).join(', ')
                            : item.content_type}
                        </span>
                        <span className="guide-row-date">{new Date(item.created_at).toLocaleDateString()}</span>
                      </span>
                    </div>
                  </div>
                  <div className="guide-row-actions">
                    <button className="guide-convert-btn" title="Edit" onClick={() => setEditContent(item)}>&#9998;</button>
                    <button className="guide-convert-btn" title="Move to class" onClick={() => { setReassignContent(item); setCategorizeCourseId(''); setCategorizeSearch(''); setCategorizeNewName(''); }}>&#128194;</button>
                    <button className="guide-delete-btn" title="Archive" onClick={() => handleArchiveContent(item.id)}>&#128465;</button>
                  </div>
                </div>
              ))}
            </div>
          ) : materialsExpanded ? (
            <div className="guides-empty">
              <p>No class materials yet. Use "+ Create Study Material" from the sidebar to get started.</p>
            </div>
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
                      </span>
                    </div>
                  </div>
                  <div className="guide-row-actions">
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
      </div>

      {/* Study Tools Modal */}
      <CreateStudyMaterialModal
        open={showModal}
        onClose={resetModal}
        onGenerate={handleGenerateFromModal}
        isGenerating={isGenerating}
        courses={courses}
        materials={modalMaterials}
        selectedCourseId={modalCourseId}
        onCourseChange={setModalCourseId}
        selectedMaterialId={modalMaterialId}
        onMaterialChange={setModalMaterialId}
        duplicateCheck={duplicateCheck}
        onViewExisting={() => {
          const guide = duplicateCheck?.existing_guide;
          if (guide) { resetModal(); navigateToLegacyGuide(guide); }
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
              });
            }
          }
        }}
        onDismissDuplicate={() => setDuplicateCheck(null)}
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
          <div className="modal" onClick={(e) => e.stopPropagation()}>
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
              <button className="cancel-btn" onClick={() => setCategorizeGuide(null)}>Cancel</button>
              {categorizeNewName ? (
                <button className="generate-btn" disabled={categorizeCreating} onClick={handleCreateAndCategorize}>
                  {categorizeCreating ? 'Creating...' : 'Create & Move'}
                </button>
              ) : (
                <button className="generate-btn" disabled={!categorizeCourseId} onClick={() => handleCategorize()}>Move</button>
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
          <div className="modal" onClick={(e) => e.stopPropagation()}>
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
              <button className="cancel-btn" onClick={() => setReassignContent(null)}>Cancel</button>
              {categorizeNewName ? (
                <button className="generate-btn" disabled={categorizeCreating} onClick={handleCreateAndReassign}>
                  {categorizeCreating ? 'Creating...' : 'Create & Move'}
                </button>
              ) : (
                <button className="generate-btn" disabled={!categorizeCourseId || categorizeCourseId === reassignContent.course_id} onClick={() => handleReassignContent()}>Move</button>
              )}
            </div>
          </div>
        </div>
      )}
      {/* Date prompt for auto-created tasks */}
      {datePromptTasks.length > 0 && (
        <div className="modal-overlay" onClick={handleDatePromptCancel}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
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
              <button className="cancel-btn" onClick={handleDatePromptCancel}>Skip</button>
              <button className="generate-btn" onClick={handleDatePromptSave}>Save Dates</button>
            </div>
          </div>
        </div>
      )}
      {confirmModal}
      {toast && <div className="toast-notification">{toast}</div>}
    </DashboardLayout>
  );
}
