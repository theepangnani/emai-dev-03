import React, { useState, useRef, useCallback } from 'react';
import { asgfApi, type FileUploadResponse } from '../../api/client';
import './ASGFUploadZone.css';

const MAX_FILES = 5;
const MAX_TOTAL_BYTES = 25 * 1024 * 1024; // 25 MB
const ACCEPTED_EXTENSIONS = '.pdf,.docx,.jpg,.jpeg,.png';

interface UploadedFile {
  file: File;
  status: 'pending' | 'uploading' | 'done' | 'error';
  progress: number;
  response?: FileUploadResponse;
  error?: string;
}

export interface ASGFUploadZoneProps {
  onFilesUploaded?: (files: FileUploadResponse[]) => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileTypeIcon(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() ?? '';
  switch (ext) {
    case 'pdf':
      return '\u{1F4C4}'; // page facing up
    case 'docx':
      return '\u{1F4DD}'; // memo
    case 'jpg':
    case 'jpeg':
    case 'png':
      return '\u{1F5BC}'; // framed picture
    default:
      return '\u{1F4CE}'; // paperclip
  }
}

export default function ASGFUploadZone({ onFilesUploaded }: ASGFUploadZoneProps) {
  const [expanded, setExpanded] = useState(false);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [showTooltip, setShowTooltip] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const totalBytes = files.reduce((sum, f) => sum + f.file.size, 0);

  const validateAndAddFiles = useCallback(
    (incoming: FileList | File[]) => {
      const arr = Array.from(incoming);
      const validFiles: File[] = [];
      const errors: string[] = [];

      for (const f of arr) {
        const ext = f.name.split('.').pop()?.toLowerCase() ?? '';
        const accepted = ['pdf', 'docx', 'jpg', 'jpeg', 'png'];
        if (!accepted.includes(ext)) {
          errors.push(`"${f.name}" is not a supported file type.`);
          continue;
        }
        validFiles.push(f);
      }

      setFiles((prev) => {
        const combined = [...prev, ...validFiles.map((f) => ({ file: f, status: 'pending' as const, progress: 0 }))];
        if (combined.length > MAX_FILES) {
          setError(`Maximum ${MAX_FILES} files allowed.`);
          return combined.slice(0, MAX_FILES);
        }
        const newTotal = combined.reduce((s, ff) => s + ff.file.size, 0);
        if (newTotal > MAX_TOTAL_BYTES) {
          setError(`Total upload size exceeds ${MAX_TOTAL_BYTES / (1024 * 1024)} MB limit.`);
          return prev; // reject the addition
        }
        if (errors.length > 0) {
          setError(errors.join(' '));
        } else {
          setError('');
        }
        return combined;
      });

      // Auto-expand on first file addition
      if (!expanded) setExpanded(true);
    },
    [expanded],
  );

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
    setError('');
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
    if (!expanded) setExpanded(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files.length > 0) {
      validateAndAddFiles(e.dataTransfer.files);
    }
  };

  const handleUpload = async () => {
    const pendingFiles = files.filter((f) => f.status === 'pending');
    if (pendingFiles.length === 0) return;

    setUploading(true);
    setUploadProgress(0);
    setError('');

    // Mark all as uploading
    setFiles((prev) =>
      prev.map((f) => (f.status === 'pending' ? { ...f, status: 'uploading' as const } : f)),
    );

    try {
      const result = await asgfApi.uploadDocuments(
        pendingFiles.map((f) => f.file),
        (progressEvent) => {
          if (progressEvent.total) {
            setUploadProgress(Math.round((progressEvent.loaded / progressEvent.total) * 100));
          }
        },
      );

      // Match responses back to files
      setFiles((prev) => {
        const updated = [...prev];
        let responseIdx = 0;
        for (let i = 0; i < updated.length; i++) {
          if (updated[i].status === 'uploading' && responseIdx < result.files.length) {
            updated[i] = { ...updated[i], status: 'done', progress: 100, response: result.files[responseIdx] };
            responseIdx++;
          }
        }
        return updated;
      });

      onFilesUploaded?.(result.files);
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'response' in err
          ? ((err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? 'Upload failed. Please try again.')
          : 'Upload failed. Please try again.';
      setError(message);
      setFiles((prev) =>
        prev.map((f) => (f.status === 'uploading' ? { ...f, status: 'error', error: message } : f)),
      );
    } finally {
      setUploading(false);
    }
  };

  const hasPendingFiles = files.some((f) => f.status === 'pending');

  if (!expanded) {
    return (
      <div
        className={`asgf-upload-collapsed ${isDragging ? 'dragging' : ''}`}
        onClick={() => setExpanded(true)}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <span className="asgf-upload-collapsed-icon">+</span>
        <span className="asgf-upload-collapsed-text">
          Add your class materials for a personalized study session
        </span>
      </div>
    );
  }

  return (
    <div className="asgf-upload-zone">
      <div className="asgf-upload-header">
        <h4 className="asgf-upload-title">Upload Materials</h4>
        <div className="asgf-tooltip-wrap">
          <button
            type="button"
            className="asgf-tooltip-trigger"
            aria-label="Document type guidance"
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
            onFocus={() => setShowTooltip(true)}
            onBlur={() => setShowTooltip(false)}
          >
            ?
          </button>
          {showTooltip && (
            <div className="asgf-tooltip-content" role="tooltip">
              Upload teacher notes, worksheets, textbook pages, your own notes, or past tests
            </div>
          )}
        </div>
        <button
          type="button"
          className="asgf-upload-collapse-btn"
          onClick={() => setExpanded(false)}
          aria-label="Collapse upload zone"
        >
          &#x2212;
        </button>
      </div>

      {/* Drop zone */}
      <div
        className={`asgf-dropzone ${isDragging ? 'dragging' : ''} ${files.length > 0 ? 'has-files' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {files.length === 0 ? (
          <div className="asgf-dropzone-prompt">
            <p className="asgf-dropzone-label">Drag and drop files here</p>
            <p className="asgf-dropzone-sublabel">PDF, DOCX, JPG, PNG &mdash; max 5 files, 25 MB total</p>
            <button
              type="button"
              className="asgf-browse-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              Browse files
            </button>
          </div>
        ) : (
          <div className="asgf-file-list">
            {files.map((f, i) => (
              <div key={`${f.file.name}-${i}`} className={`asgf-file-item asgf-file-${f.status}`}>
                <span className="asgf-file-icon">{getFileTypeIcon(f.file.name)}</span>
                <span className="asgf-file-name">{f.file.name}</span>
                <span className="asgf-file-size">{formatBytes(f.file.size)}</span>
                {f.status === 'uploading' && (
                  <span className="asgf-file-progress">{uploadProgress}%</span>
                )}
                {f.status === 'done' && <span className="asgf-file-check" aria-label="Uploaded">&#x2713;</span>}
                {f.status === 'error' && <span className="asgf-file-error-badge" title={f.error}>!</span>}
                <button
                  type="button"
                  className="asgf-file-remove"
                  onClick={() => removeFile(i)}
                  disabled={uploading}
                  aria-label={`Remove ${f.file.name}`}
                >
                  &times;
                </button>
              </div>
            ))}
            <button
              type="button"
              className="asgf-add-more-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading || files.length >= MAX_FILES}
            >
              + Add more files
            </button>
          </div>
        )}
      </div>

      {/* Upload progress bar */}
      {uploading && (
        <div className="asgf-progress-bar-track">
          <div className="asgf-progress-bar-fill" style={{ width: `${uploadProgress}%` }} />
        </div>
      )}

      {/* Error message */}
      {error && <p className="asgf-error">{error}</p>}

      {/* File count / size summary + upload button */}
      <div className="asgf-upload-footer">
        <span className="asgf-file-summary">
          {files.length} file{files.length !== 1 ? 's' : ''} ({formatBytes(totalBytes)})
        </span>
        {hasPendingFiles && (
          <button
            type="button"
            className="asgf-upload-btn"
            onClick={handleUpload}
            disabled={uploading}
          >
            {uploading ? 'Uploading...' : 'Upload'}
          </button>
        )}
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={`${ACCEPTED_EXTENSIONS},image/*;capture=camera`}
        style={{ display: 'none' }}
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) validateAndAddFiles(e.target.files);
          if (fileInputRef.current) fileInputRef.current.value = '';
        }}
      />
    </div>
  );
}
