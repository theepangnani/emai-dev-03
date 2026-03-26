import React, { useState, useRef, useEffect, useCallback } from 'react';
import UploadWizardStep1 from './UploadWizardStep1';
import UploadWizardStep2 from './UploadWizardStep2';
import { coursesApi } from '../api/courses';
import './UploadMaterialWizard.css';
import { MAX_FILE_SIZE_MB } from '../constants/upload';
const MAX_FILES_PER_SESSION = 10;

export type StudyMaterialType = 'study_guide' | 'quiz' | 'flashcards';

export interface StudyMaterialGenerateParams {
  title: string;
  content: string;
  types: StudyMaterialType[];
  focusPrompt?: string;
  mode: 'text' | 'file';
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
  const [selectedTypes, setSelectedTypes] = useState<Set<StudyMaterialType>>(new Set());
  const [focusPrompt, setFocusPrompt] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [pastedImages, setPastedImages] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState('');
  const [documentType, setDocumentType] = useState('');
  const [studyGoal, setStudyGoal] = useState('');
  const [studyGoalText, setStudyGoalText] = useState('');
  const [masterFileIndex, setMasterFileIndex] = useState(0);
  const [managedCourses, setManagedCourses] = useState<{ id: number; name: string }[] | undefined>(undefined);
  const [internalCourseId, setInternalCourseId] = useState<number | ''>(selectedCourseId ?? '');
  const [internalChildId, setInternalChildId] = useState<number | ''>('');

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
    setSelectedTypes(new Set());
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFocusPrompt('');
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
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDocumentType('');
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStudyGoal('');
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStudyGoalText('');

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
    if (!open || !courses || courses.length === 0) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setManagedCourses(courses);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setInternalCourseId(courses.length === 1 ? courses[0].id : (selectedCourseId ?? ''));
  }, [open, courses, selectedCourseId]);

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
  const needsCourse = !!(managedCourses && managedCourses.length > 0 && !internalCourseId);
  const needsChild = !!(children && children.length > 1 && !internalChildId);

  const handleSubmit = (withAITools: boolean) => {
    const hasFiles = selectedFiles.length > 0;
    const effectiveMode: 'text' | 'file' = hasFiles ? 'file' : 'text';

    if (effectiveMode === 'text' && !studyContent.trim() && pastedImages.length === 0 && !selectedMaterialId) {
      setError('Please upload a file, paste content, or paste images');
      return;
    }

    if (managedCourses && managedCourses.length > 0 && !internalCourseId) {
      setError('Please select a class');
      return;
    }

    if (children && children.length > 1 && !internalChildId) {
      setError('Please select a child');
      return;
    }

    const types = withAITools ? Array.from(selectedTypes) : [];

    // Reorder files so user-selected master is first (#2051)
    let orderedFiles = selectedFiles;
    if (selectedFiles.length > 1 && masterFileIndex > 0) {
      orderedFiles = [
        selectedFiles[masterFileIndex],
        ...selectedFiles.slice(0, masterFileIndex),
        ...selectedFiles.slice(masterFileIndex + 1),
      ];
    }

    onGenerate({
      title: studyTitle || (orderedFiles.length > 0 ? orderedFiles[0].name.replace(/\.[^/.]+$/, '') : 'Uploaded material'),
      content: studyContent,
      types,
      focusPrompt: focusPrompt.trim() || undefined,
      mode: effectiveMode,
      file: orderedFiles.length === 1 ? orderedFiles[0] : undefined,
      files: orderedFiles.length > 0 ? orderedFiles : undefined,
      pastedImages: pastedImages.length > 0 ? pastedImages : undefined,
      courseId: internalCourseId || undefined,
      courseContentId: selectedMaterialId ? (selectedMaterialId as number) : undefined,
      documentType: documentType || undefined,
      studyGoal: studyGoal || undefined,
      studyGoalText: studyGoalText.trim() || undefined,
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
            {childName && (!children || children.length <= 1) && (
              <span className="uw-child-label">for {childName}</span>
            )}
            {children && children.length > 1 && onChildChange && (
              <select
                className="uw-child-select"
                value={internalChildId}
                onChange={(e) => {
                  const id = Number(e.target.value);
                  setInternalChildId(id);
                  setInternalCourseId('');
                  onChildChange(id);
                }}
              >
                <option value="">Select a child</option>
                {children.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            )}
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
              courses={managedCourses}
              selectedCourseId={internalCourseId}
              onCourseChange={setInternalCourseId}
              onClassCreated={handleClassCreated}
              courseDisabled={needsChild}
              isGenerating={isGenerating}
              error={error}
              isDragging={isDragging}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            />
          )}
          {step === 2 && (
            <UploadWizardStep2
              selectedFiles={selectedFiles}
              studyContent={studyContent}
              pastedImages={pastedImages}
              selectedTypes={selectedTypes}
              onToggleType={(type) => setSelectedTypes(prev => {
                const next = new Set(prev);
                if (next.has(type)) next.delete(type); else next.add(type);
                return next;
              })}
              studyTitle={studyTitle}
              onStudyTitleChange={setStudyTitle}
              focusPrompt={focusPrompt}
              onFocusPromptChange={setFocusPrompt}
              isGenerating={isGenerating}
              documentType={documentType}
              onDocumentTypeChange={setDocumentType}
              studyGoal={studyGoal}
              studyGoalText={studyGoalText}
              onStudyGoalChange={(goal, text) => { setStudyGoal(goal); setStudyGoalText(text || ''); }}
              masterFileIndex={masterFileIndex}
              onMasterFileIndexChange={setMasterFileIndex}
            />
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
              <button className="btn-link" onClick={() => handleSubmit(false)} disabled={isGenerating || hasNoContent || needsCourse || needsChild}>Just Upload</button>
              <button className="btn-primary" onClick={() => setStep(2)} disabled={hasNoContent || needsCourse || needsChild}>Next &rarr;</button>
            </>
          ) : (
            <>
              <button className="btn-secondary" onClick={() => handleSubmit(false)} disabled={isGenerating}>Skip</button>
              <button className="btn-primary" onClick={() => handleSubmit(true)} disabled={isGenerating || selectedTypes.size === 0}>
                {isGenerating ? 'Generating...' : selectedTypes.size > 1 ? `Upload & Create (${selectedTypes.size})` : 'Upload & Create'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
