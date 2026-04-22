import React, { useState, useRef, useEffect, useCallback } from 'react';
import UploadWizardStep1 from './UploadWizardStep1';
import CreateClassModal from './CreateClassModal';
import { coursesApi } from '../api/courses';
import { parentApi } from '../api/client';
import './UploadMaterialWizard.css';

import { MAX_FILE_SIZE_MB, MAX_FILES_PER_SESSION } from '../constants/upload';

export type StudyMaterialType = 'study_guide' | 'quiz' | 'flashcards';

export interface StudyMaterialGenerateParams {
  title: string;
  content: string;
  types: StudyMaterialType[];
  focusPrompt?: string;
  // 'question' retained in the union to keep the type stable for any external caller still
  // passing it — handleGenerateFromModal redirects such calls to /ask (#3955). The wizard
  // itself no longer emits it.
  mode: 'text' | 'file' | 'question';
  file?: File;
  files?: File[];
  pastedImages?: File[];
  courseId?: number;
  courseContentId?: number;
  documentType?: string;
  studyGoal?: string;
  studyGoalText?: string;
}

interface UploadMaterialWizardProps {
  open: boolean;
  onClose: () => void;
  onGenerate: (params: StudyMaterialGenerateParams) => void;
  isGenerating: boolean;
  initialTitle?: string;
  initialContent?: string;
  courses?: { id: number; name: string }[];
  materials?: { id: number; title: string }[];
  selectedCourseId?: number | '';
  onCourseChange?: (id: number | '') => void;
  selectedMaterialId?: number | '';
  onMaterialChange?: (id: number | '') => void;
  duplicateCheck?: { exists: boolean; message: string | null } | null;
  onViewExisting?: () => void;
  onRegenerate?: () => void;
  onDismissDuplicate?: () => void;
  showParentNote?: boolean;
  childName?: string;
  children?: { id: number; name: string }[];
  onChildChange?: (studentId: number) => void;
}

export default function UploadMaterialWizard({
  open,
  onClose,
  onGenerate,
  isGenerating,
  initialTitle = '',
  initialContent = '',
  courses,
  selectedCourseId,
  selectedMaterialId,
  duplicateCheck,
  onViewExisting,
  onRegenerate,
  onDismissDuplicate,
  showParentNote = false,
  childName,
  children,
  onChildChange,
}: UploadMaterialWizardProps) {
  const [step, setStep] = useState<1 | 2>(1);
  const [studyTitle, setStudyTitle] = useState('');
  const [studyContent, setStudyContent] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [pastedImages, setPastedImages] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState('');
  const [masterFileIndex, setMasterFileIndex] = useState(0);
  const [managedCourses, setManagedCourses] = useState<{ id: number; name: string }[] | undefined>(undefined);
  const [internalCourseId, setInternalCourseId] = useState<number | ''>(selectedCourseId ?? '');
  const [internalChildId, setInternalChildId] = useState<number | ''>('');
  const [showCreateClassModal, setShowCreateClassModal] = useState(false);

  const selectedFilesRef = useRef<File[]>([]);
  const prevOpenRef = useRef(false);

  // Reset state only when modal first opens (open transitions false → true)
  useEffect(() => {
    const wasOpen = prevOpenRef.current;
    prevOpenRef.current = open;
    if (!open || wasOpen) return; // skip if closing or already open
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStep(1);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStudyTitle(initialTitle);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStudyContent(initialContent);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSelectedFiles([]);
    selectedFilesRef.current = [];
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPastedImages([]);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsDragging(false);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setError('');
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setInternalChildId('');
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMasterFileIndex(0);

    // Use provided courses, or fetch them if not provided
    if (courses && courses.length > 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setManagedCourses(courses);
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setInternalCourseId(courses.length === 1 ? courses[0].id : (selectedCourseId ?? ''));
    } else if (!children || children.length === 0) {
      // Only fetch all courses when NOT in parent multi-child context
      // (parent context provides courses via prop after child selection)
      coursesApi.list().then((data) => {
        const mapped = data.map((c: { id: number; name: string }) => ({ id: c.id, name: c.name }));
        setManagedCourses(mapped);
        setInternalCourseId(mapped.length === 1 ? mapped[0].id : (selectedCourseId ?? ''));
      }).catch(() => { /* courses will remain undefined — selector won't show */ });
    } else {
      // Parent multi-child context: show empty class selector (disabled until child selected)
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setManagedCourses([]);
    }
  }, [open, initialTitle, initialContent, courses, selectedCourseId, children]);

  // Sync managedCourses when courses prop changes while modal is already open
  // (e.g., parent switches child context)
  useEffect(() => {
    if (!open || !courses) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setManagedCourses(courses);
    if (courses.length === 1) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setInternalCourseId(courses[0].id);
    }
  }, [open, courses, selectedCourseId]);

  // Fetch courses when child is selected on Step 2 — fallback for async prop pipeline
  useEffect(() => {
    if (!open || !internalChildId) return;
    let cancelled = false;
    parentApi.getChildOverview(Number(internalChildId)).then((overview) => {
      if (cancelled || !overview?.courses) return;
      const mapped = overview.courses.map((c: { id: number; name: string }) => ({ id: c.id, name: c.name }));
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setManagedCourses(mapped);
      if (mapped.length === 1) setInternalCourseId(mapped[0].id);
    }).catch(() => { /* fallback silently fails — user can still create a class */ });
    return () => { cancelled = true; };
  }, [open, internalChildId]);

  const addFiles = useCallback((incoming: FileList | File[]) => {
    const toAdd = Array.from(incoming);
    const oversized = toAdd.filter(f => f.size > MAX_FILE_SIZE_MB * 1024 * 1024);
    if (oversized.length > 0) {
      setError(`${oversized.map(f => f.name).join(', ')} exceed${oversized.length === 1 ? 's' : ''} the ${MAX_FILE_SIZE_MB} MB limit`);
    }
    const valid = toAdd.filter(f => f.size <= MAX_FILE_SIZE_MB * 1024 * 1024);
    if (valid.length === 0) return;

    const prev = selectedFilesRef.current;
    const existingNames = new Set(prev.map(f => f.name));
    const newUnique = valid.filter(f => !existingNames.has(f.name));
    const merged = [...prev, ...newUnique];
    if (merged.length > MAX_FILES_PER_SESSION) {
      setError(`Maximum ${MAX_FILES_PER_SESSION} files per upload. ${merged.length - MAX_FILES_PER_SESSION} file(s) were not added.`);
    }
    const capped = merged.slice(0, MAX_FILES_PER_SESSION);
    selectedFilesRef.current = capped;
    setSelectedFiles(capped);

    // Auto-fill title only when adding the first file and title is empty
    setStudyTitle(prev => {
      if (!prev && valid.length > 0) return valid[0].name.replace(/\.[^/.]+$/, '');
      return prev;
    });
  }, []);

  // Global paste handler
  useEffect(() => {
    if (!open) return;
    const handler = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;

      const files: File[] = [];
      const images: File[] = [];
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.kind === 'file') {
          const file = item.getAsFile();
          if (!file) continue;
          if (item.type.startsWith('image/')) {
            images.push(file);
          } else {
            files.push(file);
          }
        }
      }

      if (files.length > 0) {
        e.preventDefault();
        addFiles(files);
      } else if (images.length > 0) {
        const target = e.target as HTMLElement;
        if (target?.tagName !== 'TEXTAREA') {
          e.preventDefault();
          setPastedImages(prev => [...prev, ...images].slice(0, 10));
        }
      }
    };

    document.addEventListener('paste', handler);
    return () => document.removeEventListener('paste', handler);
  }, [open, addFiles]);

  const handleClassCreated = (course: { id: number; name: string }) => {
    setManagedCourses(prev => [...(prev || []), { id: course.id, name: course.name }]);
    setInternalCourseId(course.id);
  };

  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(false); };
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setIsDragging(false);
    if (e.dataTransfer.files.length > 0) addFiles(e.dataTransfer.files);
  };

  const removeFile = (index: number) => {
    setSelectedFiles(prev => {
      const next = prev.filter((_, i) => i !== index);
      selectedFilesRef.current = next;
      return next;
    });
    // Reset master index when files change (#2051)
    setMasterFileIndex(prev => {
      if (index === prev) return 0;
      if (index < prev) return prev - 1;
      return prev;
    });
  };

  const hasNoContent = selectedFiles.length === 0 && !studyContent.trim() && pastedImages.length === 0;
  const needsCourse = !internalCourseId;
  const needsChild = !!(children && children.length > 1 && !internalChildId);

  const handleSubmit = () => {
    const hasFiles = selectedFiles.length > 0;
    const effectiveMode: 'text' | 'file' = hasFiles ? 'file' : 'text';

    if (effectiveMode === 'text' && !studyContent.trim() && pastedImages.length === 0 && !selectedMaterialId) {
      setError('Please upload a file, paste content, or paste images');
      return;
    }

    if (!internalCourseId) {
      setError('Please select a class');
      return;
    }

    if (children && children.length > 1 && !internalChildId) {
      setError('Please select a child');
      return;
    }

    // Reorder files so user-selected master is first (#2051)
    let orderedFiles = selectedFiles;
    if (selectedFiles.length > 1 && masterFileIndex > 0) {
      orderedFiles = [
        selectedFiles[masterFileIndex],
        ...selectedFiles.slice(0, masterFileIndex),
        ...selectedFiles.slice(masterFileIndex + 1),
      ];
    }

    // Upload-only: no AI generation types selected from wizard
    onGenerate({
      title: studyTitle || (orderedFiles.length > 0 ? orderedFiles[0].name.replace(/\.[^/.]+$/, '') : 'Uploaded material'),
      content: studyContent,
      types: [],
      mode: effectiveMode,
      file: orderedFiles.length === 1 ? orderedFiles[0] : undefined,
      files: orderedFiles.length > 0 ? orderedFiles : undefined,
      pastedImages: pastedImages.length > 0 ? pastedImages : undefined,
      courseId: internalCourseId || undefined,
      courseContentId: selectedMaterialId ? (selectedMaterialId as number) : undefined,
    });
  };

  if (!open) return null;

  return (
    <div className="upload-wizard-overlay" onClick={onClose}>
      <div className="upload-wizard-modal" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="uw-header">
          {step === 2 && <button className="uw-back-btn" onClick={() => setStep(1)}>&larr;</button>}
          <div className="uw-header-titles">
            <h2>Upload Class Material</h2>
          </div>
          <span className="uw-step-indicator">Step {step} of 2</span>
        </div>

        {/* Body */}
        <div className="uw-body">
          {step === 1 && (
            <UploadWizardStep1
              selectedFiles={selectedFiles}
              onAddFiles={addFiles}
              onRemoveFile={removeFile}
              studyContent={studyContent}
              onStudyContentChange={setStudyContent}
              pastedImages={pastedImages}
              onAddPastedImages={(imgs) => setPastedImages(prev => [...prev, ...imgs].slice(0, 10))}
              onRemovePastedImage={(idx) => setPastedImages(prev => prev.filter((_, i) => i !== idx))}
              onClearPastedImages={() => setPastedImages([])}
              isGenerating={isGenerating}
              error={error}
              isDragging={isDragging}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            />
          )}
          {step === 2 && (
            <div className="upload-wizard-step">
              {/* Child selector (parent with multiple children) */}
              {children && children.length > 1 && onChildChange && (
                <div className="uw-field">
                  <label htmlFor="uw-child-select">Student</label>
                  <select
                    id="uw-child-select"
                    className="uw-child-select"
                    value={internalChildId}
                    onChange={(e) => {
                      const id = Number(e.target.value);
                      setInternalChildId(id);
                      setInternalCourseId('');
                      onChildChange(id);
                    }}
                  >
                    <option value="">Select a student</option>
                    {children.map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
              )}

              {/* Single child display */}
              {childName && (!children || children.length <= 1) && (
                <div className="uw-field">
                  <label>Student</label>
                  <div className="uw-static-value">{childName}</div>
                </div>
              )}

              {/* Class selector (mandatory) */}
              <div className="uw-field">
                <label htmlFor="uw-course-select">Class <span className="uw-required">*</span></label>
                <select
                  id="uw-course-select"
                  value={internalCourseId}
                  onChange={(e) => {
                    if (e.target.value === '__create__') {
                      setShowCreateClassModal(true);
                    } else {
                      setInternalCourseId(e.target.value ? Number(e.target.value) : '');
                    }
                  }}
                  disabled={isGenerating || needsChild}
                >
                  <option value="">Select a class</option>
                  {(managedCourses || []).map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                  <option value="__create__">+ Create new class...</option>
                </select>
              </div>

              {/* Title field */}
              <div className="uw-field">
                <label htmlFor="uw-title">Title</label>
                <input
                  id="uw-title"
                  type="text"
                  value={studyTitle}
                  onChange={(e) => setStudyTitle(e.target.value)}
                  placeholder="e.g., Chapter 5 Review (auto-filled from filename)"
                  disabled={isGenerating}
                />
              </div>

              {/* Master file selection for multi-file uploads (#2051) */}
              {selectedFiles.length >= 2 && studyTitle && (
                <div className="upload-wizard-naming-preview">
                  <p style={{ fontWeight: 600, fontSize: '0.8125rem', marginBottom: '0.375rem' }}>
                    Materials that will be created:
                  </p>
                  <ul className="uw-master-select-list">
                    {selectedFiles.map((file, i) => {
                      const isMaster = i === masterFileIndex;
                      const fileTitle = file.name.replace(/\.[^/.]+$/, '');
                      return (
                        <li
                          key={i}
                          className={`uw-master-select-item${isMaster ? ' selected' : ''}`}
                          onClick={() => { if (!isGenerating) setMasterFileIndex(i); }}
                          role="radio"
                          aria-checked={isMaster}
                          tabIndex={0}
                          onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && !isGenerating) { e.preventDefault(); setMasterFileIndex(i); } }}
                        >
                          <span className={`uw-master-radio${isMaster ? ' checked' : ''}`} />
                          <span className="uw-master-select-name">
                            {isMaster ? (
                              <><strong>{studyTitle}</strong> <span className="uw-master-label">(master)</span></>
                            ) : (
                              <>{fileTitle}</>
                            )}
                          </span>
                          <span className="uw-master-select-filename">{file.name}</span>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}

              {/* Upload summary */}
              <div className="uw-summary-bar" style={{ marginTop: '0.75rem' }}>
                <span className="uw-summary-icon">&#x2705;</span>
                <span className="uw-summary-text">
                  {selectedFiles.length > 0
                    ? `${selectedFiles.length} file${selectedFiles.length !== 1 ? 's' : ''} ready to upload`
                    : pastedImages.length > 0
                      ? `${pastedImages.length} image${pastedImages.length !== 1 ? 's' : ''} ready`
                      : 'Pasted text ready'}
                </span>
              </div>

              {/* Error display */}
              {error && (
                <div className="uw-error">
                  <span className="uw-error-icon">!</span>
                  <span className="uw-error-message">{error}</span>
                </div>
              )}

              {/* Create Class Modal */}
              <CreateClassModal
                open={showCreateClassModal}
                onClose={() => setShowCreateClassModal(false)}
                onCreated={(newCourse) => {
                  setShowCreateClassModal(false);
                  handleClassCreated(newCourse);
                }}
              />
            </div>
          )}

          {/* Parent note */}
          {showParentNote && (
            <p className="uw-parent-note">Your parent will be notified about this upload.</p>
          )}

          {/* Duplicate warning */}
          {duplicateCheck?.exists && (
            <div className="uw-error">
              <span>{duplicateCheck.message}</span>
              {onViewExisting && <button onClick={onViewExisting}>View Existing</button>}
              {onRegenerate && <button onClick={onRegenerate}>Regenerate</button>}
              {onDismissDuplicate && <button onClick={onDismissDuplicate}>Cancel</button>}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="uw-footer">
          {step === 1 ? (
            <>
              <button className="btn-secondary" onClick={onClose} disabled={isGenerating}>Cancel</button>
              <button className="btn-primary" onClick={() => setStep(2)} disabled={hasNoContent}>Next &rarr;</button>
            </>
          ) : (
            <>
              <button className="btn-secondary" onClick={() => setStep(1)} disabled={isGenerating}>Back</button>
              <button className="btn-primary" onClick={handleSubmit} disabled={isGenerating || needsCourse || needsChild}>
                {isGenerating ? 'Uploading...' : 'Upload'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
