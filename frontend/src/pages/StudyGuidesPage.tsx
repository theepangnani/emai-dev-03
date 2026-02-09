import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { studyApi, parentApi } from '../api/client';
import type { StudyGuide, SupportedFormats, DuplicateCheckResponse, ChildSummary } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { CourseAssignSelect } from '../components/CourseAssignSelect';
import { CreateTaskModal } from '../components/CreateTaskModal';
import { useConfirm } from '../components/ConfirmModal';
import './StudyGuidesPage.css';

const MAX_FILE_SIZE_MB = 100;

// Cross-page generation queue (ParentDashboard → StudyGuidesPage)
interface PendingGeneration {
  title: string;
  content: string;
  type: 'study_guide' | 'quiz' | 'flashcards';
  mode: 'text' | 'file';
  file?: File;
  regenerateId?: number;
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

export function StudyGuidesPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isParent = user?.role === 'parent';
  const { confirm, confirmModal } = useConfirm();

  const [myGuides, setMyGuides] = useState<StudyGuide[]>([]);
  const [childGuides, setChildGuides] = useState<StudyGuide[]>([]);
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState<string>('all');

  // Study tools modal
  const [showModal, setShowModal] = useState(false);
  const [studyTitle, setStudyTitle] = useState('');
  const [studyContent, setStudyContent] = useState('');
  const [studyType, setStudyType] = useState<'study_guide' | 'quiz' | 'flashcards'>('study_guide');
  const [studyMode, setStudyMode] = useState<'text' | 'file'>('text');
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

  // Convert guide to another type (e.g. study guide → quiz)
  const [convertingGuideId, setConvertingGuideId] = useState<number | null>(null);

  // Create task from guide
  const [taskModalGuide, setTaskModalGuide] = useState<StudyGuide | null>(null);

  useEffect(() => {
    loadData();
    // Pick up pending generation queued from ParentDashboard navigation
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

  const loadData = async () => {
    try {
      const guides = await studyApi.listGuides();
      setMyGuides(guides);

      if (isParent) {
        const childrenData = await parentApi.getChildren();
        setChildren(childrenData);
        if (childrenData.length > 0) {
          const allChildGuides = await studyApi.listGuides({ include_children: true });
          setChildGuides(allChildGuides.filter(g => g.user_id !== user?.id));
        }
      }
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  };

  const handleDeleteGuide = async (id: number) => {
    try {
      await studyApi.deleteGuide(id);
      setMyGuides(prev => prev.filter(g => g.id !== id));
    } catch { /* ignore */ }
  };

  const navigateToGuide = (guide: StudyGuide) => {
    if (guide.guide_type === 'quiz') navigate(`/study/quiz/${guide.id}`);
    else if (guide.guide_type === 'flashcards') navigate(`/study/flashcards/${guide.id}`);
    else navigate(`/study/guide/${guide.id}`);
  };

  const guideIcon = (type: string) => {
    if (type === 'quiz') return '?';
    if (type === 'flashcards') return '\uD83C\uDCCF';
    return '\uD83D\uDCD6';
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
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleConvert = async (guide: StudyGuide, targetType: 'study_guide' | 'quiz' | 'flashcards') => {
    if (convertingGuideId) return;
    const baseTitle = guide.title.replace(/^(Study Guide|Quiz|Flashcards):\s*/i, '');

    // Check if target type already exists for this content
    try {
      const dupResult = await studyApi.checkDuplicate({ title: baseTitle, guide_type: targetType });
      if (dupResult.exists && dupResult.existing_guide) {
        const existing = dupResult.existing_guide;
        const typeName = targetType.replace('_', ' ');
        const goToExisting = await confirm({
          title: 'Already Exists',
          message: `A ${typeName} already exists: "${existing.title}" (v${existing.version}). Would you like to view it?`,
          confirmLabel: 'View Existing',
          cancelLabel: 'Stay Here',
        });
        if (goToExisting) {
          navigate(targetType === 'quiz' ? `/study/quiz/${existing.id}` : targetType === 'flashcards' ? `/study/flashcards/${existing.id}` : `/study/guide/${existing.id}`);
        }
        return;
      }
    } catch { /* continue if check fails */ }

    const typeName = targetType.replace('_', ' ');
    if (!await confirm({ title: 'Generate ' + typeName, message: `Generate a ${typeName} from "${guide.title}"? This will use AI credits.`, confirmLabel: 'Generate' })) return;

    setConvertingGuideId(guide.id);
    try {
      let result;
      if (targetType === 'quiz') {
        result = await studyApi.generateQuiz({
          topic: baseTitle, content: guide.content,
          course_id: guide.course_id ?? undefined, num_questions: 10,
        });
        navigate(`/study/quiz/${result.id}`);
      } else if (targetType === 'flashcards') {
        result = await studyApi.generateFlashcards({
          topic: baseTitle, content: guide.content,
          course_id: guide.course_id ?? undefined, num_cards: 15,
        });
        navigate(`/study/flashcards/${result.id}`);
      } else {
        result = await studyApi.generateGuide({
          title: baseTitle, content: guide.content,
          course_id: guide.course_id ?? undefined,
        });
        navigate(`/study/guide/${result.id}`);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || `Failed to generate ${targetType.replace('_', ' ')}`);
    } finally {
      setConvertingGuideId(null);
    }
  };

  const startGeneration = (params: PendingGeneration) => {
    const tempId = `gen-${Date.now()}`;
    const displayTitle = params.title || `New ${params.type.replace('_', ' ')}`;
    setGeneratingItems(prev => [...prev, { tempId, title: displayTitle, guideType: params.type, status: 'generating' }]);

    (async () => {
      try {
        if (params.mode === 'file' && params.file) {
          await studyApi.generateFromFile({
            file: params.file, title: params.title || undefined, guide_type: params.type,
            num_questions: params.type === 'quiz' ? 10 : undefined,
            num_cards: params.type === 'flashcards' ? 15 : undefined,
          });
        } else if (params.type === 'study_guide') {
          await studyApi.generateGuide({ title: params.title, content: params.content, regenerate_from_id: params.regenerateId });
        } else if (params.type === 'quiz') {
          await studyApi.generateQuiz({ topic: params.title, content: params.content, num_questions: 10, regenerate_from_id: params.regenerateId });
        } else {
          await studyApi.generateFlashcards({ topic: params.title, content: params.content, num_cards: 15, regenerate_from_id: params.regenerateId });
        }
        // Success: remove placeholder, refresh list from API
        setGeneratingItems(prev => prev.filter(g => g.tempId !== tempId));
        loadData();
      } catch (err: any) {
        // Error: update placeholder to show error
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

    // Capture form state before closing modal
    const params: PendingGeneration = {
      title: studyTitle || `New ${studyType.replace('_', ' ')}`,
      content: studyContent,
      type: studyType,
      mode: studyMode,
      file: selectedFile ?? undefined,
      regenerateId: duplicateCheck?.existing_guide?.id,
    };

    // Close modal immediately and start background generation
    setDuplicateCheck(null);
    resetModal();
    startGeneration(params);
  };

  const filteredMyGuides = filterType === 'all' ? myGuides : myGuides.filter(g => g.guide_type === filterType);
  const filteredChildGuides = filterType === 'all' ? childGuides : childGuides.filter(g => g.guide_type === filterType);

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
        { label: '+ Create Study Guide', onClick: () => setShowModal(true) },
      ]}
    >
      <div className="guides-page">
        {/* Header with filter + create button */}
        <div className="guides-header">
          <div className="guides-filter">
            {['all', 'study_guide', 'quiz', 'flashcards'].map(type => (
              <button
                key={type}
                className={`guides-filter-btn ${filterType === type ? 'active' : ''}`}
                onClick={() => setFilterType(type)}
              >
                {type === 'all' ? 'All' : guideTypeLabel(type)}
              </button>
            ))}
          </div>
          <button className="generate-btn" onClick={() => setShowModal(true)}>+ Create Study Guide</button>
        </div>

        {/* My guides */}
        <div className="guides-section">
          <h3>My Study Materials ({filteredMyGuides.length + generatingItems.length})</h3>
          {filteredMyGuides.length > 0 || generatingItems.length > 0 ? (
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
                        ✕
                      </button>
                    </div>
                  )}
                </div>
              ))}
              {filteredMyGuides.map(guide => (
                <div key={guide.id} className="guide-row">
                  <div className="guide-row-main" onClick={() => navigateToGuide(guide)}>
                    <span className="guide-row-icon">{guideIcon(guide.guide_type)}</span>
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
                      <button
                        className="guide-convert-btn"
                        title="Generate Quiz from this"
                        disabled={convertingGuideId === guide.id}
                        onClick={() => handleConvert(guide, 'quiz')}
                      >
                        {convertingGuideId === guide.id ? '...' : '?'}
                      </button>
                    )}
                    {guide.guide_type !== 'flashcards' && (
                      <button
                        className="guide-convert-btn"
                        title="Generate Flashcards from this"
                        disabled={convertingGuideId === guide.id}
                        onClick={() => handleConvert(guide, 'flashcards')}
                      >
                        {convertingGuideId === guide.id ? '...' : '\uD83C\uDCCF'}
                      </button>
                    )}
                    {guide.guide_type !== 'study_guide' && (
                      <button
                        className="guide-convert-btn"
                        title="Generate Study Guide from this"
                        disabled={convertingGuideId === guide.id}
                        onClick={() => handleConvert(guide, 'study_guide')}
                      >
                        {convertingGuideId === guide.id ? '...' : '\uD83D\uDCD6'}
                      </button>
                    )}
                    <button
                      className="guide-convert-btn"
                      title="Create task from this"
                      onClick={() => setTaskModalGuide(guide)}
                    >
                      +Task
                    </button>
                    <CourseAssignSelect
                      guideId={guide.id}
                      currentCourseId={guide.course_id}
                      onCourseChanged={(courseId) => setMyGuides(prev =>
                        prev.map(g => g.id === guide.id ? { ...g, course_id: courseId } : g)
                      )}
                    />
                    <button className="guide-delete-btn" onClick={() => handleDeleteGuide(guide.id)}>
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="guides-empty">
              <p>No study materials yet. Create one to get started!</p>
            </div>
          )}
        </div>

        {/* Children's guides */}
        {isParent && children.length > 0 && filteredChildGuides.length > 0 && (
          <div className="guides-section">
            <h3>Children's Materials ({filteredChildGuides.length})</h3>
            <div className="guides-list">
              {filteredChildGuides.map(guide => (
                <div key={guide.id} className="guide-row">
                  <div className="guide-row-main" onClick={() => navigateToGuide(guide)}>
                    <span className="guide-row-icon">{guideIcon(guide.guide_type)}</span>
                    <div className="guide-row-info">
                      <span className="guide-row-title">{guide.title}</span>
                      <span className="guide-row-meta">
                        {guideTypeLabel(guide.guide_type)}
                        <span className="guide-row-date">{new Date(guide.created_at).toLocaleDateString()}</span>
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
                        <span className="file-icon">📄</span>
                        <div className="file-info">
                          <span className="file-name">{selectedFile.name}</span>
                          <span className="file-size">{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</span>
                        </div>
                        <button className="clear-file-btn" onClick={(e) => { e.stopPropagation(); clearFileSelection(); }} disabled={isGenerating}>✕</button>
                      </div>
                    ) : (
                      <div className="drop-zone-content">
                        <span className="upload-icon">📁</span>
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
                  <button className="generate-btn" onClick={() => { const guide = duplicateCheck.existing_guide!; resetModal(); navigateToGuide(guide); }}>View Existing</button>
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
      {confirmModal}
    </DashboardLayout>
  );
}
