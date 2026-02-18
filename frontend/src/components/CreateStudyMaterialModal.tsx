import React, { useState, useRef, useEffect } from 'react';
import { studyApi, SupportedFormats, DuplicateCheckResponse } from '../api/study';

const MAX_FILE_SIZE_MB = 100;

interface CourseOption { id: number; name: string; }
interface MaterialOption { id: number; title: string; }

export interface StudyMaterialGenerateParams {
  title: string;
  content: string;
  type: 'study_guide' | 'quiz' | 'flashcards';
  mode: 'text' | 'file';
  file?: File;
  pastedImages?: File[];
  courseId?: number;
  courseContentId?: number;
}

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
}: CreateStudyMaterialModalProps) {
  const [studyTitle, setStudyTitle] = useState('');
  const [studyContent, setStudyContent] = useState('');
  const [studyType, setStudyType] = useState<'study_guide' | 'quiz' | 'flashcards'>('study_guide');
  const [studyMode, setStudyMode] = useState<'text' | 'file'>('text');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
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
    setStudyType('study_guide');
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStudyMode('text');
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSelectedFile(null);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStudyError('');
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsDragging(false);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPastedImages([]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, [open, initialTitle, initialContent]);

  const handleFileSelect = (file: File) => {
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setStudyError(`File size exceeds ${MAX_FILE_SIZE_MB} MB limit`);
      return;
    }
    setSelectedFile(file);
    setStudyMode('file');
    if (!studyTitle) {
      setStudyTitle(file.name.replace(/\.[^/.]+$/, ''));
    }
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
    if (studyMode === 'file' && !selectedFile) { setStudyError('Please select a file'); return; }
    if (studyMode === 'text' && !studyContent.trim() && pastedImages.length === 0) { setStudyError('Please enter content or paste images'); return; }

    onGenerate({
      title: studyTitle || `New ${studyType.replace('_', ' ')}`,
      content: studyContent,
      type: studyType,
      mode: studyMode,
      file: selectedFile ?? undefined,
      pastedImages: pastedImages.length > 0 ? pastedImages : undefined,
      courseId: selectedCourseId ? (selectedCourseId as number) : undefined,
      courseContentId: selectedMaterialId ? (selectedMaterialId as number) : undefined,
    });
  };

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
        <h2>Create Study Material</h2>
        <p className="modal-desc">Upload a document or photo, or paste text and images to generate AI-powered study materials.</p>
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

          {/* Course selector (only shown if courses prop is provided) */}
          {courses && onCourseChange && (
            <label>
              Course (optional)
              <select value={selectedCourseId ?? ''} onChange={(e) => onCourseChange(e.target.value ? Number(e.target.value) : '')} disabled={isGenerating}>
                <option value="">Main Course (default)</option>
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

          <div className="mode-toggle">
            <button className={`mode-btn ${studyMode === 'text' ? 'active' : ''}`} onClick={() => setStudyMode('text')} disabled={isGenerating}>Paste Text</button>
            <button className={`mode-btn ${studyMode === 'file' ? 'active' : ''}`} onClick={() => setStudyMode('file')} disabled={isGenerating}>Upload File</button>
          </div>

          {studyMode === 'text' ? (
            <>
              <label>
                Content to study
                <textarea
                  value={studyContent}
                  onChange={(e) => setStudyContent(e.target.value)}
                  onPaste={handlePaste}
                  placeholder="Paste notes, email content, or screenshots — images will be detected automatically..."
                  rows={8}
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
                      <div key={idx} className="pasted-image-thumb">
                        <img
                          src={URL.createObjectURL(img)}
                          alt={`Pasted ${idx + 1}`}
                          onLoad={(e) => URL.revokeObjectURL((e.target as HTMLImageElement).src)}
                        />
                        <button
                          className="remove-image-btn"
                          onClick={() => setPastedImages(prev => prev.filter((_, i) => i !== idx))}
                          disabled={isGenerating}
                        >
                          &times;
                        </button>
                      </div>
                    ))}
                  </div>
                  {pastedImages.length >= 10 && <small className="images-limit-note">Maximum 10 images</small>}
                </div>
              )}
            </>
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
            disabled={isGenerating || (studyMode === 'file' ? !selectedFile : (!studyContent.trim() && pastedImages.length === 0))}
          >
            {isGenerating ? 'Generating...' : 'Generate'}
          </button>
        </div>
      </div>
    </div>
  );
}
