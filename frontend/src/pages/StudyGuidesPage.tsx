import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { studyApi, parentApi, courseContentsApi, coursesApi, tasksApi } from '../api/client';
import type { StudyGuide, SupportedFormats, DuplicateCheckResponse, ChildSummary, CourseContentItem, AutoCreatedTask } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { CreateTaskModal } from '../components/CreateTaskModal';
import { useConfirm } from '../components/ConfirmModal';
import './StudyGuidesPage.css';

const MAX_FILE_SIZE_MB = 100;

// Cross-page generation queue (ParentDashboard -> StudyGuidesPage)
interface PendingGeneration {
  title: string;
  content: string;
  type: 'study_guide' | 'quiz' | 'flashcards';
  mode: 'text' | 'file';
  file?: File;
  regenerateId?: number;
  courseId?: number;
  courseContentId?: number;
}

let _pendingGeneration: PendingGeneration | null = null;

export function queueStudyGeneration(params: PendingGeneration) {
  _pendingGeneration = params;
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
  const isParent = user?.role === 'parent';
  const { confirm, confirmModal } = useConfirm();

  // Course content items (primary list)
  const [contentItems, setContentItems] = useState<CourseContentItem[]>([]);
  // Legacy study guides without course_content_id
  const [legacyGuides, setLegacyGuides] = useState<StudyGuide[]>([]);
  // Map of course_content_id -> guide_types for filtering
  const [contentGuideMap, setContentGuideMap] = useState<Record<number, string[]>>({});
  const [loading, setLoading] = useState(true);

  // Filters
  const [filterChild, setFilterChild] = useState<number | ''>('');
  const [filterCourse, setFilterCourse] = useState<number | ''>('');
  const [filterType, setFilterType] = useState<string>('all');
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [courses, setCourses] = useState<CourseOption[]>([]);

  // Study tools modal
  const [showModal, setShowModal] = useState(false);
  const [studyTitle, setStudyTitle] = useState('');
  const [studyContent, setStudyContent] = useState('');
  const [studyType, setStudyType] = useState<'study_guide' | 'quiz' | 'flashcards'>('study_guide');
  const [studyMode, setStudyMode] = useState<'text' | 'file'>('text');
  const [modalCourseId, setModalCourseId] = useState<number | ''>('');
  const [modalMaterials, setModalMaterials] = useState<CourseContentItem[]>([]);
  const [modalMaterialId, setModalMaterialId] = useState<number | ''>('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isGenerating] = useState(false);
  const [studyError, setStudyError] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [supportedFormats, setSupportedFormats] = useState<SupportedFormats | null>(null);
  const [duplicateCheck, setDuplicateCheck] = useState<DuplicateCheckResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const generatingRef = useRef(false);

  // In-progress generation placeholders
  const [generatingItems, setGeneratingItems] = useState<GeneratingItem[]>([]);

  // Create task from guide
  const [taskModalGuide, setTaskModalGuide] = useState<StudyGuide | null>(null);

  // Date prompt for auto-created tasks
  const [datePromptTasks, setDatePromptTasks] = useState<AutoCreatedTask[]>([]);
  const [datePromptValues, setDatePromptValues] = useState<Record<number, string>>({});

  // Categorize ungrouped guide
  const [categorizeGuide, setCategorizeGuide] = useState<StudyGuide | null>(null);
  const [categorizeCourseId, setCategorizeCourseId] = useState<number | ''>('');
  const [categorizeSearch, setCategorizeSearch] = useState('');
  const [categorizeNewName, setCategorizeNewName] = useState('');
  const [categorizeCreating, setCategorizeCreating] = useState(false);

  useEffect(() => {
    loadData();
    if (_pendingGeneration) {
      const params = _pendingGeneration;
      _pendingGeneration = null;
      startGeneration(params);
    }
  }, []);

  useEffect(() => {
    if (showModal && !supportedFormats) {
      studyApi.getSupportedFormats().then(setSupportedFormats).catch(() => {});
    }
  }, [showModal, supportedFormats]);

  // Reload content when filters change
  useEffect(() => {
    loadContentItems();
  }, [filterChild, filterCourse]);

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
    try {
      const [contents, allGuides, courseList] = await Promise.all([
        courseContentsApi.listAll(),
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
    } catch { /* ignore */ } finally {
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

  // File handling
  const handleFileSelect = (file: File) => {
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setStudyError(`File size exceeds ${MAX_FILE_SIZE_MB} MB limit`);
      return;
    }
    setSelectedFile(file);
    setStudyMode('file');
    if (!studyTitle) setStudyTitle(file.name.replace(/\.[^/.]+$/, ''));
  };

  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(false); };
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  };
  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileSelect(file);
  };
  const clearFileSelection = () => {
    setSelectedFile(null); setStudyMode('text');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const resetModal = () => {
    setShowModal(false); setStudyTitle(''); setStudyContent('');
    setStudyType('study_guide'); setStudyMode('text'); setSelectedFile(null);
    setStudyError(''); setDuplicateCheck(null);
    setModalCourseId(''); setModalMaterialId(''); setModalMaterials([]);
    if (fileInputRef.current) fileInputRef.current.value = '';
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
          });
        } else if (params.type === 'study_guide') {
          result = await studyApi.generateGuide({ title: params.title, content: params.content, regenerate_from_id: params.regenerateId, course_id: params.courseId, course_content_id: params.courseContentId });
        } else if (params.type === 'quiz') {
          result = await studyApi.generateQuiz({ topic: params.title, content: params.content, num_questions: 10, regenerate_from_id: params.regenerateId, course_id: params.courseId, course_content_id: params.courseContentId });
        } else {
          result = await studyApi.generateFlashcards({ topic: params.title, content: params.content, num_cards: 15, regenerate_from_id: params.regenerateId, course_id: params.courseId, course_content_id: params.courseContentId });
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

  const handleGenerate = async () => {
    if (studyMode === 'file' && !selectedFile) { setStudyError('Please select a file'); return; }
    if (studyMode === 'text' && !studyContent.trim()) { setStudyError('Please enter content'); return; }
    if (generatingRef.current) return;

    if (!duplicateCheck && !await confirm({ title: 'Generate Study Material', message: `Generate ${studyType.replace('_', ' ')}? This will use AI credits.`, confirmLabel: 'Generate' })) return;

    if (studyMode === 'text' && !duplicateCheck) {
      try {
        const dupResult = await studyApi.checkDuplicate({ title: studyTitle || undefined, guide_type: studyType });
        if (dupResult.exists) { setDuplicateCheck(dupResult); return; }
      } catch { /* continue */ }
    }

    const params: PendingGeneration = {
      title: studyTitle || `New ${studyType.replace('_', ' ')}`,
      content: studyContent,
      type: studyType,
      mode: studyMode,
      file: selectedFile ?? undefined,
      regenerateId: duplicateCheck?.existing_guide?.id,
      courseId: modalCourseId ? (modalCourseId as number) : undefined,
      courseContentId: modalMaterialId ? (modalMaterialId as number) : undefined,
    };

    setDuplicateCheck(null);
    resetModal();
    startGeneration(params);
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

  // Apply course + type filters
  const filteredContent = contentItems.filter(c => {
    if (filterCourse && c.course_id !== filterCourse) return false;
    if (filterType !== 'all' && !contentGuideMap[c.id]?.includes(filterType)) return false;
    return true;
  });

  // Apply guide type filter to legacy guides
  const filteredLegacy = filterType === 'all'
    ? legacyGuides
    : legacyGuides.filter(g => g.guide_type === filterType);

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Manage study materials">
        <div className="loading-state">Loading...</div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      welcomeSubtitle="Manage study materials"
      sidebarActions={[
        { label: '+ Create Study Material', onClick: () => setShowModal(true) },
      ]}
    >
      <div className="guides-page">
        {/* Header with filters + create button */}
        <div className="guides-header">
          <div className="guides-filters-row">
            {isParent && children.length > 0 && (
              <select
                className="guides-filter-select"
                value={filterChild}
                onChange={e => setFilterChild(e.target.value ? Number(e.target.value) : '')}
              >
                <option value="">All Family</option>
                {children.map(child => (
                  <option key={child.user_id} value={child.user_id}>{child.full_name}</option>
                ))}
              </select>
            )}
            {courses.length > 0 && (
              <select
                className="guides-filter-select"
                value={filterCourse}
                onChange={e => setFilterCourse(e.target.value ? Number(e.target.value) : '')}
              >
                <option value="">All Courses</option>
                {courses.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            )}
          </div>
          <button className="generate-btn" onClick={() => setShowModal(true)}>+ Create</button>
        </div>

        {/* Guide type filter tabs */}
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
              onClick={() => setFilterType(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Course content items */}
        <div className="guides-section">
          <h3>Course Materials ({filteredContent.length + generatingItems.length})</h3>
          {filteredContent.length > 0 || generatingItems.length > 0 ? (
            <div className="guides-list">
              {/* In-progress generation placeholders */}
              {generatingItems.map(item => (
                <div key={item.tempId} className={`guide-row ${item.status === 'generating' ? 'guide-row-generating' : 'guide-row-error'}`}>
                  <div className="guide-row-main">
                    <span className="guide-row-icon">
                      {item.status === 'generating' ? '\u23F3' : '\u26A0\uFE0F'}
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
                </div>
              ))}
            </div>
          ) : (
            <div className="guides-empty">
              <p>No course materials yet. Click "+ Create" to generate study materials from your content.</p>
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
                      title="Move to course"
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
      {showModal && (
        <div className="modal-overlay" onClick={resetModal}>
          <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
            <h2>Create Study Material</h2>
            <p className="modal-desc">Upload a document or photo, or paste text to generate AI-powered study materials.</p>
            <div className="modal-form">
              <label>
                What to create
                <select value={studyType} onChange={(e) => setStudyType(e.target.value as any)} disabled={isGenerating}>
                  <option value="study_guide">Study Guide</option>
                  <option value="quiz">Practice Quiz</option>
                  <option value="flashcards">Flashcards</option>
                </select>
              </label>
              <label>
                Title (optional)
                <input type="text" value={studyTitle} onChange={(e) => setStudyTitle(e.target.value)} placeholder="e.g., Chapter 5 Review" disabled={isGenerating} />
              </label>
              <label>
                Course (optional)
                <select value={modalCourseId} onChange={(e) => setModalCourseId(e.target.value ? Number(e.target.value) : '')} disabled={isGenerating}>
                  <option value="">Main Course (default)</option>
                  {courses.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </label>
              {modalCourseId && modalMaterials.length > 0 && (
                <label>
                  Existing material (optional)
                  <select value={modalMaterialId} onChange={(e) => setModalMaterialId(e.target.value ? Number(e.target.value) : '')} disabled={isGenerating}>
                    <option value="">Create new material</option>
                    {modalMaterials.map(m => (
                      <option key={m.id} value={m.id}>{m.title}</option>
                    ))}
                  </select>
                </label>
              )}
              <div className="mode-toggle">
                <button className={`mode-btn ${studyMode === 'text' ? 'active' : ''}`} onClick={() => setStudyMode('text')} disabled={isGenerating}>Paste Text</button>
                <button className={`mode-btn ${studyMode === 'file' ? 'active' : ''}`} onClick={() => setStudyMode('file')} disabled={isGenerating}>Upload File</button>
              </div>
              {studyMode === 'text' ? (
                <label>
                  Content to study
                  <textarea value={studyContent} onChange={(e) => setStudyContent(e.target.value)} placeholder="Paste notes, textbook content, or any study material..." rows={8} disabled={isGenerating} />
                </label>
              ) : (
                <div className="file-upload-section">
                  <input ref={fileInputRef} type="file" onChange={handleFileInputChange} accept=".pdf,.docx,.doc,.txt,.md,.xlsx,.xls,.csv,.pptx,.ppt,.png,.jpg,.jpeg,.gif,.bmp,.tiff,.webp,.zip" style={{ display: 'none' }} disabled={isGenerating} />
                  <div className={`drop-zone ${isDragging ? 'dragging' : ''} ${selectedFile ? 'has-file' : ''}`} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop} onClick={() => !isGenerating && fileInputRef.current?.click()}>
                    {selectedFile ? (
                      <div className="selected-file">
                        <span className="file-icon">&#128196;</span>
                        <div className="file-info">
                          <span className="file-name">{selectedFile.name}</span>
                          <span className="file-size">{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</span>
                        </div>
                        <button className="clear-file-btn" onClick={(e) => { e.stopPropagation(); clearFileSelection(); }} disabled={isGenerating}>&times;</button>
                      </div>
                    ) : (
                      <div className="drop-zone-content">
                        <span className="upload-icon">&#128193;</span>
                        <p>Drag & drop a file here, or click to browse</p>
                        <small>Supports: PDF, Word, Excel, PowerPoint, Images (photos), Text, ZIP</small>
                      </div>
                    )}
                  </div>
                </div>
              )}
              {studyError && <p className="link-error">{studyError}</p>}
            </div>
            {duplicateCheck && duplicateCheck.exists && (
              <div className="duplicate-warning">
                <p>{duplicateCheck.message}</p>
                <div className="duplicate-actions">
                  <button className="generate-btn" onClick={() => { const guide = duplicateCheck.existing_guide!; resetModal(); navigateToLegacyGuide(guide); }}>View Existing</button>
                  <button className="generate-btn" onClick={handleGenerate}>Regenerate (New Version)</button>
                  <button className="cancel-btn" onClick={() => setDuplicateCheck(null)}>Cancel</button>
                </div>
              </div>
            )}
            <div className="modal-actions">
              <button className="cancel-btn" onClick={resetModal} disabled={isGenerating}>Cancel</button>
              <button className="generate-btn" onClick={handleGenerate} disabled={isGenerating || (studyMode === 'file' ? !selectedFile : !studyContent.trim())}>
                {isGenerating ? 'Generating...' : 'Generate'}
              </button>
            </div>
          </div>
        </div>
      )}

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
            <h2>Move to Course</h2>
            <p className="modal-desc">Assign &ldquo;{categorizeGuide.title}&rdquo; to a course.</p>
            <div className="modal-form">
              <input
                type="text"
                placeholder="Search courses or type a new name..."
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
                  <div className="categorize-empty">No courses found</div>
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
      {/* Date prompt for auto-created tasks */}
      {datePromptTasks.length > 0 && (
        <div className="modal-overlay" onClick={handleDatePromptCancel}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Tasks Created</h2>
            <p className="modal-desc">
              {datePromptTasks.length === 1
                ? 'A task was auto-created from your course material. Set the action date:'
                : `${datePromptTasks.length} tasks were auto-created from your course material. Set the action dates:`}
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
    </DashboardLayout>
  );
}
