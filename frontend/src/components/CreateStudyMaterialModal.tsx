import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { studyApi } from '../api/study';
import type { SupportedFormats, DuplicateCheckResponse } from '../api/study';

const MAX_FILE_SIZE_MB = 20;
const MAX_FILES_PER_SESSION = 10;

interface CourseOption { id: number; name: string; }
interface MaterialOption { id: number; title: string; }

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
}

type SelectableType = StudyMaterialType | 'other';

interface CreateStudyMaterialModalProps {
  open: boolean;
  onClose: () => void;
  onGenerate: (params: StudyMaterialGenerateParams) => void;
  isGenerating: boolean;
  // Pre-fill values (e.g. from one-click study on assignment)
  initialTitle?: string;
  initialContent?: string;
  // Course/material selection (StudyGuidesPage uses these, ParentDashboard doesn't)
  courses?: CourseOption[];
  materials?: MaterialOption[];
  selectedCourseId?: number | '';
  onCourseChange?: (id: number | '') => void;
  selectedMaterialId?: number | '';
  onMaterialChange?: (id: number | '') => void;
  duplicateCheck?: DuplicateCheckResponse | null;
  onViewExisting?: () => void;
  onRegenerate?: () => void;
  onDismissDuplicate?: () => void;
  /** Show parent notification note for student uploads (#552) */
  showParentNote?: boolean;
}

export default function CreateStudyMaterialModal({
  open,
  onClose,
  onGenerate,
  isGenerating,
  initialTitle = '',
  initialContent = '',
  courses,
  materials,
  selectedCourseId,
  onCourseChange,
  selectedMaterialId,
  onMaterialChange,
  duplicateCheck,
  onViewExisting,
  onRegenerate,
  onDismissDuplicate,
  showParentNote = false,
}: CreateStudyMaterialModalProps) {
  const [studyTitle, setStudyTitle] = useState('');
  const [studyContent, setStudyContent] = useState('');
  const [selectedTypes, setSelectedTypes] = useState<Set<SelectableType>>(new Set());
  const [focusPrompt, setFocusPrompt] = useState('');
  const [otherPrompt, setOtherPrompt] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [studyError, setStudyError] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [supportedFormats, setSupportedFormats] = useState<SupportedFormats | null>(null);
  const [pastedImages, setPastedImages] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load supported formats on first open
  useEffect(() => {
    if (open && !supportedFormats) {
      studyApi.getSupportedFormats().then(setSupportedFormats).catch(() => {});
    }
  }, [open, supportedFormats]);

  // Reset state when modal opens/closes; apply initial values on open
  useEffect(() => {
    if (!open) return;
    // Intentional sync setState on open to reset form fields
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStudyTitle(initialTitle);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStudyContent(initialContent);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSelectedTypes(new Set());
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFocusPrompt('');
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOtherPrompt('');
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSelectedFiles([]);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStudyError('');
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsDragging(false);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPastedImages([]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, [open, initialTitle, initialContent]);

  const addFiles = useCallback((incoming: FileList | File[]) => {
    const toAdd = Array.from(incoming);
    const oversized = toAdd.filter(f => f.size > MAX_FILE_SIZE_MB * 1024 * 1024);
    if (oversized.length > 0) {
      setStudyError(`${oversized.map(f => f.name).join(', ')} exceed${oversized.length === 1 ? 's' : ''} the ${MAX_FILE_SIZE_MB} MB limit`);
    }
    const valid = toAdd.filter(f => f.size <= MAX_FILE_SIZE_MB * 1024 * 1024);
    if (valid.length === 0) return;
    setSelectedFiles(prev => {
      const existingNames = new Set(prev.map(f => f.name));
      const newUnique = valid.filter(f => !existingNames.has(f.name));
      const merged = [...prev, ...newUnique];
      if (merged.length > MAX_FILES_PER_SESSION) {
        setStudyError(`Maximum ${MAX_FILES_PER_SESSION} files per upload. ${merged.length - MAX_FILES_PER_SESSION} file(s) were not added.`);
        return merged.slice(0, MAX_FILES_PER_SESSION);
      }
      return merged;
    });
    // Auto-fill title only when adding the first file and title is empty
    setStudyTitle(prev => {
      if (!prev && valid.length > 0) return valid[0].name.replace(/\.[^/.]+$/, '');
      return prev;
    });
  }, []);

  // Global paste handler — captures pasted files (Ctrl+V from Explorer) anywhere in the modal
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

  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(false); };
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setIsDragging(false);
    if (e.dataTransfer.files.length > 0) addFiles(e.dataTransfer.files);
  };
  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) addFiles(e.target.files);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };
  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  // Clipboard paste handler — captures images from email paste
  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    const newImages: File[] = [];
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith('image/')) {
        const file = items[i].getAsFile();
        if (file) newImages.push(file);
      }
    }

    if (newImages.length > 0) {
      // Don't prevent default — let text paste normally into textarea via onChange
      setPastedImages(prev => [...prev, ...newImages].slice(0, 10));
    }
  };

  const handleSubmit = () => {
    // Determine mode: files take priority if any selected, else text/images
    const hasFiles = selectedFiles.length > 0;
    const effectiveMode: 'text' | 'file' = hasFiles ? 'file' : 'text';
    if (effectiveMode === 'text' && !studyContent.trim() && pastedImages.length === 0 && !selectedMaterialId) { setStudyError('Please upload a file, paste content, or paste images'); return; }
    if (selectedTypes.has('other') && !otherPrompt.trim()) { setStudyError('Please describe what you want to generate'); return; }

    // Map selectable types to actual StudyMaterialType values
    // "other" maps to study_guide with the custom prompt as focusPrompt
    const hasOther = selectedTypes.has('other');
    const types: StudyMaterialType[] = Array.from(selectedTypes)
      .filter((t): t is StudyMaterialType => t !== 'other');
    if (hasOther && !types.includes('study_guide')) types.push('study_guide');

    // Merge focus prompts: otherPrompt takes priority when "other" is selected
    const effectivePrompt = hasOther
      ? otherPrompt.trim()
      : focusPrompt.trim() || undefined;

    onGenerate({
      title: studyTitle || (selectedFiles.length > 0 ? selectedFiles[0].name.replace(/\.[^/.]+$/, '') : 'Uploaded material'),
      content: studyContent,
      types,
      focusPrompt: effectivePrompt,
      mode: effectiveMode,
      // Legacy single-file field for callers that still use it
      file: selectedFiles.length === 1 ? selectedFiles[0] : undefined,
      // Multi-file: pass all selected files (one material combining all)
      files: selectedFiles.length > 0 ? selectedFiles : undefined,
      pastedImages: pastedImages.length > 0 ? pastedImages : undefined,
      courseId: selectedCourseId ? (selectedCourseId as number) : undefined,
      courseContentId: selectedMaterialId ? (selectedMaterialId as number) : undefined,
    });
  };

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
        <h2>Upload Documents</h2>
        <p className="modal-desc">Upload a document or photo, or paste text and images. Optionally generate AI study materials.</p>
        <div className="modal-form">
          <fieldset className="material-type-checkboxes" disabled={isGenerating}>
            <legend>Generate AI study tools (optional)</legend>
            {([
              { value: 'study_guide' as const, label: 'Study Guide' },
              { value: 'quiz' as const, label: 'Practice Quiz' },
              { value: 'flashcards' as const, label: 'Flashcards' },
              { value: 'other' as const, label: 'Other' },
            ]).map(opt => (
              <label key={opt.value} className={`material-type-checkbox${selectedTypes.has(opt.value) ? ' checked' : ''}`}>
                <input
                  type="checkbox"
                  checked={selectedTypes.has(opt.value)}
                  onChange={() => {
                    setSelectedTypes(prev => {
                      const next = new Set(prev);
                      if (next.has(opt.value)) {
                        next.delete(opt.value);
                      } else {
                        next.add(opt.value);
                      }
                      return next;
                    });
                  }}
                />
                {opt.label}
              </label>
            ))}
          </fieldset>
          {selectedTypes.has('other') && (
            <label>
              Describe what to generate
              <input
                type="text"
                value={otherPrompt}
                onChange={(e) => setOtherPrompt(e.target.value)}
                placeholder="e.g., Create a timeline of key events"
                disabled={isGenerating}
              />
            </label>
          )}
          {selectedTypes.size > 0 && !selectedTypes.has('other') && (
            <label>
              Focus on... (optional)
              <input
                type="text"
                value={focusPrompt}
                onChange={(e) => setFocusPrompt(e.target.value)}
                placeholder="e.g., photosynthesis and the Calvin cycle"
                disabled={isGenerating}
              />
            </label>
          )}
          <label>
            Title (optional)
            <input type="text" value={studyTitle} onChange={(e) => setStudyTitle(e.target.value)} placeholder="e.g., Chapter 5 Review" disabled={isGenerating} />
          </label>

          {/* Course selector (only shown if courses prop is provided) */}
          {courses && onCourseChange && (
            <label>
              Class (optional)
              <select value={selectedCourseId ?? ''} onChange={(e) => onCourseChange(e.target.value ? Number(e.target.value) : '')} disabled={isGenerating}>
                <option value="">Main Class (default)</option>
                {courses.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </label>
          )}

          {/* Material selector (only shown if course is selected and materials exist) */}
          {selectedCourseId && materials && materials.length > 0 && onMaterialChange && (
            <label>
              Existing material (optional)
              <select value={selectedMaterialId ?? ''} onChange={(e) => onMaterialChange(e.target.value ? Number(e.target.value) : '')} disabled={isGenerating}>
                <option value="">Create new material</option>
                {materials.map(m => (
                  <option key={m.id} value={m.id}>{m.title}</option>
                ))}
              </select>
            </label>
          )}

          {/* File drop zone — always visible */}
          <div className="file-upload-section">
            <input ref={fileInputRef} type="file" multiple onChange={handleFileInputChange} accept=".pdf,.docx,.doc,.txt,.md,.xlsx,.xls,.csv,.pptx,.ppt,.png,.jpg,.jpeg,.gif,.bmp,.tiff,.webp,.zip" style={{ display: 'none' }} disabled={isGenerating} />
            <div className={`drop-zone ${isDragging ? 'dragging' : ''} ${selectedFiles.length > 0 ? 'has-file' : ''}`} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop} onClick={() => !isGenerating && fileInputRef.current?.click()}>
              {selectedFiles.length > 0 ? (
                <div className="selected-files-list" onClick={(e) => e.stopPropagation()}>
                  {selectedFiles.map((f, idx) => (
                    <div key={idx} className="selected-file">
                      <span className="file-icon">&#128196;</span>
                      <div className="file-info">
                        <span className="file-name">{f.name}</span>
                        <span className="file-size">{(f.size / 1024 / 1024).toFixed(2)} MB</span>
                      </div>
                      <button className="clear-file-btn" onClick={() => !isGenerating && removeFile(idx)} disabled={isGenerating}>&times;</button>
                    </div>
                  ))}
                  <button
                    className="add-more-files-btn"
                    onClick={(e) => { e.stopPropagation(); if (!isGenerating) fileInputRef.current?.click(); }}
                    disabled={isGenerating}
                  >
                    + Add more files
                  </button>
                </div>
              ) : (
                <div className="drop-zone-content">
                  <span className="upload-icon">&#128193;</span>
                  <p>Drag & drop files here, or click to browse</p>
                  <small>Supports: PDF, Word, Excel, PowerPoint, Images, Text, ZIP &bull; Up to {MAX_FILES_PER_SESSION} files, {MAX_FILE_SIZE_MB} MB each</small>
                </div>
              )}
            </div>
          </div>

          <div className="upload-divider"><span>or paste content</span></div>

          {/* Text area — always visible */}
          <label>
            Content to study
            <textarea
              value={studyContent}
              onChange={(e) => setStudyContent(e.target.value)}
              onPaste={handlePaste}
              placeholder="Paste notes, email content, or screenshots — images will be detected automatically..."
              rows={4}
              disabled={isGenerating}
            />
          </label>
          {/* Pasted image thumbnails */}
          {pastedImages.length > 0 && (
            <div className="pasted-images-strip">
              <div className="pasted-images-header">
                <span>{pastedImages.length} image{pastedImages.length !== 1 ? 's' : ''} detected</span>
                <button className="clear-images-btn" onClick={() => setPastedImages([])} disabled={isGenerating}>
                  Clear all
                </button>
              </div>
              <div className="pasted-images-thumbnails">
                {pastedImages.map((img, idx) => (
                  <PastedImageThumb
                    key={idx}
                    file={img}
                    index={idx}
                    onRemove={() => setPastedImages(prev => prev.filter((_, i) => i !== idx))}
                    disabled={isGenerating}
                  />
                ))}
              </div>
              {pastedImages.length >= 10 && <small className="images-limit-note">Maximum 10 images</small>}
            </div>
          )}
          {studyError && (
            <div className="modal-error">
              <span className="error-icon">!</span>
              <span className="error-message">{studyError}</span>
              <button onClick={handleSubmit} className="retry-btn" disabled={isGenerating}>Try Again</button>
            </div>
          )}
        </div>

        {/* Parent notification note (#552) */}
        {showParentNote && (
          <p className="modal-info-note">
            Your parent will be notified about this upload.
          </p>
        )}

        {/* Duplicate check warning */}
        {duplicateCheck && duplicateCheck.exists && (
          <div className="duplicate-warning">
            <p>{duplicateCheck.message}</p>
            <div className="duplicate-actions">
              {onViewExisting && <button className="generate-btn" onClick={onViewExisting}>View Existing</button>}
              {onRegenerate && <button className="generate-btn" onClick={onRegenerate}>Regenerate (New Version)</button>}
              {onDismissDuplicate && <button className="cancel-btn" onClick={onDismissDuplicate}>Cancel</button>}
            </div>
          </div>
        )}

        <div className="modal-actions">
          <button className="cancel-btn" onClick={onClose} disabled={isGenerating}>Cancel</button>
          <button
            className="generate-btn"
            onClick={handleSubmit}
            disabled={isGenerating || (selectedFiles.length === 0 && !studyContent.trim() && pastedImages.length === 0)}
          >
            {isGenerating ? <><span className="btn-spinner" /> Generating...</> : selectedTypes.size > 0 ? (selectedTypes.size > 1 ? `Upload & Generate ${selectedTypes.size} Materials` : 'Upload & Generate') : (selectedFiles.length > 1 ? `Upload ${selectedFiles.length} Files` : 'Upload')}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Stable blob URL thumbnail — avoids creating new URLs on every render */
function PastedImageThumb({ file, index, onRemove, disabled }: { file: File; index: number; onRemove: () => void; disabled: boolean }) {
  const url = useMemo(() => URL.createObjectURL(file), [file]);
  useEffect(() => () => URL.revokeObjectURL(url), [url]);
  return (
    <div className="pasted-image-thumb">
      <img src={url} alt={`Pasted ${index + 1}`} />
      <button className="remove-image-btn" onClick={onRemove} disabled={disabled}>&times;</button>
    </div>
  );
}
