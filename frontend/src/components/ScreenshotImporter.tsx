import { useState, useRef, useCallback } from 'react';
import { classroomImportApi } from '../api/classroomImport';
import './ScreenshotImporter.css';

interface ScreenshotImporterProps {
  studentId?: number;
  onSessionCreated: (sessionId: number) => void;
  onCancel?: () => void;
}

const MAX_FILES = 10;
const MAX_FILE_SIZE_MB = 10;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
const ACCEPTED_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif'];
const ACCEPT_STRING = 'image/png,image/jpeg,image/webp,image/gif';

const SOURCE_HINTS = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'assignment_list', label: 'Assignment List' },
  { value: 'assignment_detail', label: 'Assignment Detail' },
  { value: 'stream', label: 'Stream' },
  { value: 'grades', label: 'Grades' },
];

interface FileWithPreview {
  file: File;
  previewUrl: string;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ScreenshotImporter({
  studentId,
  onSessionCreated,
  onCancel,
}: ScreenshotImporterProps) {
  const [files, setFiles] = useState<FileWithPreview[]>([]);
  const [sourceHint, setSourceHint] = useState('auto');
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateAndAddFiles = useCallback((incoming: FileList | File[]) => {
    const newFiles: FileWithPreview[] = [];
    const errors: string[] = [];
    const currentCount = files.length;

    for (let i = 0; i < incoming.length; i++) {
      const file = incoming[i];

      if (!ACCEPTED_TYPES.includes(file.type)) {
        errors.push(`"${file.name}" is not a supported image type.`);
        continue;
      }

      if (file.size > MAX_FILE_SIZE_BYTES) {
        errors.push(`"${file.name}" exceeds ${MAX_FILE_SIZE_MB}MB limit.`);
        continue;
      }

      if (currentCount + newFiles.length >= MAX_FILES) {
        errors.push(`Maximum ${MAX_FILES} images allowed.`);
        break;
      }

      newFiles.push({
        file,
        previewUrl: URL.createObjectURL(file),
      });
    }

    if (errors.length > 0) {
      setError(errors.join(' '));
    } else {
      setError('');
    }

    if (newFiles.length > 0) {
      setFiles(prev => [...prev, ...newFiles]);
    }
  }, [files.length]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndAddFiles(e.dataTransfer.files);
    }
  }, [validateAndAddFiles]);

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndAddFiles(e.target.files);
    }
    // Reset input so re-selecting the same file works
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleRemoveFile = (index: number) => {
    setFiles(prev => {
      const removed = prev[index];
      if (removed) {
        URL.revokeObjectURL(removed.previewUrl);
      }
      return prev.filter((_, i) => i !== index);
    });
    setError('');
  };

  const handleSubmit = async () => {
    if (files.length === 0) return;

    setSubmitting(true);
    setError('');

    try {
      const rawFiles = files.map(f => f.file);
      const response = await classroomImportApi.importScreenshot(
        rawFiles,
        studentId,
        sourceHint,
      );
      onSessionCreated(response.data.session_id);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'Failed to analyze screenshots. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="si-container">
      {/* Header */}
      <div className="si-header">
        <h3 className="si-title">Import from Screenshots</h3>
        <p className="si-description">
          Take screenshots or photos of your Google Classroom pages and upload them below.
          AI will extract assignments, materials, and grades.
        </p>
      </div>

      {/* Drop zone */}
      <div
        className={`si-drop-zone${isDragging ? ' si-drop-zone--active' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click(); }}
      >
        <svg
          className="si-drop-icon"
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <polyline points="21 15 16 10 5 21" />
        </svg>
        <p className="si-drop-text">Drag & drop screenshots here, or click to browse</p>
        <p className="si-drop-subtext">PNG, JPG, WebP — Max {MAX_FILES} images, {MAX_FILE_SIZE_MB}MB each</p>
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPT_STRING}
          multiple
          onChange={handleFileInputChange}
          style={{ display: 'none' }}
        />
      </div>

      {/* Thumbnail preview grid */}
      {files.length > 0 && (
        <div className="si-thumbnails">
          {files.map((entry, index) => (
            <div key={`${entry.file.name}-${index}`} className="si-thumbnail">
              <div className="si-thumbnail-img-wrapper">
                <img
                  src={entry.previewUrl}
                  alt={entry.file.name}
                  className="si-thumbnail-img"
                />
                <button
                  className="si-thumbnail-remove"
                  onClick={(e) => { e.stopPropagation(); handleRemoveFile(index); }}
                  type="button"
                  aria-label={`Remove ${entry.file.name}`}
                  disabled={submitting}
                >
                  &times;
                </button>
              </div>
              <div className="si-thumbnail-info">
                <span className="si-thumbnail-name" title={entry.file.name}>
                  {entry.file.name}
                </span>
                <span className="si-thumbnail-size">
                  {formatFileSize(entry.file.size)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Source hint dropdown */}
      <div className="si-source-hint">
        <label htmlFor="si-source-select" className="si-source-label">
          What page is this from?
        </label>
        <select
          id="si-source-select"
          className="si-source-select"
          value={sourceHint}
          onChange={(e) => setSourceHint(e.target.value)}
          disabled={submitting}
        >
          {SOURCE_HINTS.map(hint => (
            <option key={hint.value} value={hint.value}>
              {hint.label}
            </option>
          ))}
        </select>
      </div>

      {/* Error message */}
      {error && <p className="si-error">{error}</p>}

      {/* Action buttons */}
      <div className="si-actions">
        {onCancel && (
          <button
            className="si-btn si-btn--secondary"
            onClick={onCancel}
            disabled={submitting}
            type="button"
          >
            Cancel
          </button>
        )}
        <button
          className="si-btn si-btn--primary"
          onClick={handleSubmit}
          disabled={files.length === 0 || submitting}
          type="button"
        >
          {submitting ? (
            <>
              <span className="si-spinner" aria-hidden="true" />
              AI is reading your screenshots...
            </>
          ) : (
            `Analyze Screenshot${files.length !== 1 ? 's' : ''}`
          )}
        </button>
      </div>
    </div>
  );
}
