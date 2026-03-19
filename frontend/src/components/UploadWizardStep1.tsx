import React, { useState, useRef, useMemo, useEffect } from 'react';
import CreateClassModal from './CreateClassModal';

const MAX_FILE_SIZE_MB = 20;
const MAX_FILES_PER_SESSION = 10;
const ACCEPTED_TYPES = '.pdf,.docx,.doc,.txt,.md,.xlsx,.xls,.csv,.pptx,.ppt,.png,.jpg,.jpeg,.gif,.bmp,.tiff,.webp,.zip';

interface UploadWizardStep1Props {
  // File state
  selectedFiles: File[];
  onAddFiles: (files: FileList | File[]) => void;
  onRemoveFile: (index: number) => void;
  // Text state
  studyContent: string;
  onStudyContentChange: (value: string) => void;
  // Pasted images
  pastedImages: File[];
  onAddPastedImages: (images: File[]) => void;
  onRemovePastedImage: (index: number) => void;
  onClearPastedImages: () => void;
  // Course selection
  courses?: { id: number; name: string }[];
  selectedCourseId?: number | '';
  onCourseChange?: (id: number | '') => void;
  onClassCreated?: (course: { id: number; name: string }) => void;
  courseDisabled?: boolean;
  // State
  isGenerating: boolean;
  error: string;
  isDragging: boolean;
  onDragOver: (e: React.DragEvent) => void;
  onDragLeave: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent) => void;
}

/** Stable blob URL thumbnail — avoids creating new URLs on every render */
function PastedImageThumb({ file, index, onRemove, disabled }: { file: File; index: number; onRemove: () => void; disabled: boolean }) {
  const url = useMemo(() => URL.createObjectURL(file), [file]);
  useEffect(() => () => URL.revokeObjectURL(url), [url]);
  return (
    <div className="uw-pasted-thumb">
      <img src={url} alt={`Pasted ${index + 1}`} />
      <button className="uw-pasted-remove" onClick={onRemove} disabled={disabled}>&times;</button>
    </div>
  );
}

function UploadWizardStep1({
  selectedFiles,
  onAddFiles,
  onRemoveFile,
  studyContent,
  onStudyContentChange,
  pastedImages,
  onAddPastedImages,
  onRemovePastedImage,
  onClearPastedImages,
  courses,
  selectedCourseId,
  onCourseChange,
  onClassCreated,
  courseDisabled,
  isGenerating,
  error,
  isDragging,
  onDragOver,
  onDragLeave,
  onDrop,
}: UploadWizardStep1Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [showCreateClassModal, setShowCreateClassModal] = useState(false);

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) onAddFiles(e.target.files);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  /** Detect pasted images inside the textarea */
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
      onAddPastedImages(newImages);
    }
  };

  const dropZoneClasses = [
    'uw-drop-zone',
    isDragging ? 'dragging' : '',
    selectedFiles.length > 0 ? 'has-files' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className="upload-wizard-step">
      {/* Course selector */}
      {courses && onCourseChange && (
        <div className="uw-course-select">
          <label>
            Class
            <select
              value={selectedCourseId ?? ''}
              onChange={(e) => {
                if (e.target.value === '__create__') {
                  setShowCreateClassModal(true);
                } else {
                  onCourseChange(e.target.value ? Number(e.target.value) : '');
                }
              }}
              disabled={isGenerating || courseDisabled}
            >
              <option value="">Select a class</option>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
              <option value="__create__">+ Create new class...</option>
            </select>
          </label>
        </div>
      )}

      {/* File drop zone — hero element */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        onChange={handleFileInputChange}
        accept={ACCEPTED_TYPES}
        style={{ display: 'none' }}
        disabled={isGenerating}
      />
      <div
        className={dropZoneClasses}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => !isGenerating && selectedFiles.length === 0 && fileInputRef.current?.click()}
      >
        {selectedFiles.length > 0 ? (
          <div className="uw-file-list" onClick={(e) => e.stopPropagation()}>
            {selectedFiles.map((f, idx) => (
              <div key={idx} className="uw-file-item">
                <span className="uw-file-icon">&#128196;</span>
                <div className="uw-file-info">
                  <span className="uw-file-name">{f.name}</span>
                  <span className="uw-file-size">{(f.size / 1024 / 1024).toFixed(2)} MB</span>
                </div>
                <button
                  className="uw-file-remove"
                  onClick={() => !isGenerating && onRemoveFile(idx)}
                  disabled={isGenerating}
                >
                  &times;
                </button>
              </div>
            ))}
            <button
              className="uw-add-more-btn"
              onClick={(e) => { e.stopPropagation(); if (!isGenerating) fileInputRef.current?.click(); }}
              disabled={isGenerating}
            >
              + Add more files
            </button>
          </div>
        ) : (
          <div className="uw-drop-content">
            <span className="upload-icon">&#128193;</span>
            <p>Drag &amp; drop files here, or click to browse</p>
            <small>
              PDF, Word, Excel, PowerPoint, Images, Text, ZIP &bull; Up to {MAX_FILES_PER_SESSION} files, {MAX_FILE_SIZE_MB} MB each
            </small>
          </div>
        )}
      </div>

      {/* Multi-file info banner */}
      {selectedFiles.length >= 2 && (
        <div className="upload-wizard-info-banner">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.3"/>
            <path d="M8 5v1M8 7.5v4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
          </svg>
          <span>
            Uploading {selectedFiles.length} files will create a <strong>master material</strong> with {selectedFiles.length} <strong>linked sub-materials</strong>, one per file.
          </span>
        </div>
      )}

      {/* Divider */}
      <div className="uw-divider"><span>or paste content below</span></div>

      {/* Text + image paste area */}
      <textarea
        className="uw-textarea"
        value={studyContent}
        onChange={(e) => onStudyContentChange(e.target.value)}
        onPaste={handlePaste}
        placeholder="Paste text, notes, or use Ctrl+V to paste screenshots..."
        rows={4}
        disabled={isGenerating}
      />
      <div className="uw-paste-hint">
        <span className="uw-paste-hint-icon">&#128247;</span>
        <span>Tip: Copy a screenshot and press <kbd>Ctrl+V</kbd> (or <kbd>&#8984;V</kbd>) in the box above to add images</span>
      </div>

      {/* Pasted image thumbnails */}
      {pastedImages.length > 0 && (
        <div className="uw-pasted-images">
          <div className="uw-pasted-images-header">
            <span>{pastedImages.length} image{pastedImages.length !== 1 ? 's' : ''} detected</span>
            <button className="uw-pasted-clear" onClick={onClearPastedImages} disabled={isGenerating}>
              Clear all
            </button>
          </div>
          <div className="uw-pasted-images-thumbs">
            {pastedImages.map((img, idx) => (
              <PastedImageThumb
                key={idx}
                file={img}
                index={idx}
                onRemove={() => onRemovePastedImage(idx)}
                disabled={isGenerating}
              />
            ))}
          </div>
          {pastedImages.length >= 10 && <small className="uw-pasted-limit-note">Maximum 10 images</small>}
        </div>
      )}

      {/* Create Class Modal */}
      <CreateClassModal
        open={showCreateClassModal}
        onClose={() => setShowCreateClassModal(false)}
        onCreated={(newCourse) => {
          setShowCreateClassModal(false);
          onClassCreated?.(newCourse);
        }}
      />

      {/* Error display */}
      {error && (
        <div className="uw-error">
          <span className="uw-error-icon">!</span>
          <span className="uw-error-message">{error}</span>
        </div>
      )}
    </div>
  );
}

export default UploadWizardStep1;
