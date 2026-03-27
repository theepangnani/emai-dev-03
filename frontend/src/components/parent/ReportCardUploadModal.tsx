import { useState, useRef, useCallback, useEffect } from 'react';
import { schoolReportCardsApi } from '../../api/schoolReportCards';
import { useFocusTrap } from '../../utils/useFocusTrap';
import './ReportCardUploadModal.css';

import { MAX_FILE_SIZE_MB } from '../../constants/upload';

const MAX_FILES = 10;
const ALLOWED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png'];
const ALLOWED_MIME_TYPES = [
  'application/pdf',
  'image/jpeg',
  'image/jpg',
  'image/png',
];

interface ReportCardUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  studentId: number;
  studentName: string;
  onUploadComplete: () => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase();
  if (ext === 'pdf') return '\u{1F4C4}';
  return '\u{1F5BC}';
}

function isAllowedFile(file: File): boolean {
  const ext = '.' + (file.name.split('.').pop()?.toLowerCase() || '');
  return ALLOWED_EXTENSIONS.includes(ext) || ALLOWED_MIME_TYPES.includes(file.type);
}

export default function ReportCardUploadModal({
  isOpen,
  onClose,
  studentId,
  studentName,
  onUploadComplete,
}: ReportCardUploadModalProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [schoolName, setSchoolName] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [successCount, setSuccessCount] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const trapRef = useFocusTrap(isOpen, onClose);

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setFiles([]);
      setSchoolName('');
      setIsDragging(false);
      setUploading(false);
      setError('');
      setSuccessCount(null);
    }
  }, [isOpen]);

  const addFiles = useCallback((incoming: FileList | File[]) => {
    const toAdd = Array.from(incoming);
    setError('');

    // Validate file types
    const invalid = toAdd.filter(f => !isAllowedFile(f));
    if (invalid.length > 0) {
      setError(`${invalid.map(f => f.name).join(', ')} — only PDF, JPG, and PNG files are accepted`);
    }

    // Validate file sizes
    const oversized = toAdd.filter(f => f.size > MAX_FILE_SIZE_MB * 1024 * 1024);
    if (oversized.length > 0) {
      setError(`${oversized.map(f => f.name).join(', ')} exceed${oversized.length === 1 ? 's' : ''} the ${MAX_FILE_SIZE_MB} MB limit`);
      return;
    }

    const valid = toAdd.filter(f => isAllowedFile(f) && f.size <= MAX_FILE_SIZE_MB * 1024 * 1024);
    if (valid.length === 0) return;

    setFiles(prev => {
      const existingNames = new Set(prev.map(f => f.name));
      const newUnique = valid.filter(f => !existingNames.has(f.name));
      const merged = [...prev, ...newUnique];
      if (merged.length > MAX_FILES) {
        setError(`Maximum ${MAX_FILES} files per upload. ${merged.length - MAX_FILES} file(s) were not added.`);
      }
      return merged.slice(0, MAX_FILES);
    });
  }, []);

  const removeFile = useCallback((index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
    setError('');
  }, []);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files);
    }
  };

  const handleBrowseClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(e.target.files);
    }
    // Reset input so re-selecting the same file works
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    setUploading(true);
    setError('');

    const formData = new FormData();
    formData.append('student_id', String(studentId));
    if (schoolName.trim()) {
      formData.append('school_name', schoolName.trim());
    }
    files.forEach(file => formData.append('files', file));

    try {
      const response = await schoolReportCardsApi.upload(formData);
      setSuccessCount(response.data.total_uploaded ?? files.length);
      onUploadComplete();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || 'Upload failed. Please try again.';
      setError(msg);
    } finally {
      setUploading(false);
    }
  };

  const handleClose = () => {
    if (uploading) return;
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="rc-upload-overlay" onClick={handleClose}>
      <div
        className="rc-upload-modal"
        ref={trapRef}
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Upload Report Cards"
      >
        {/* Header */}
        <div className="rc-upload-header">
          <div>
            <h2>Upload Report Cards</h2>
            <span className="rc-upload-header-subtitle">for {studentName}</span>
          </div>
          <button
            className="rc-upload-close"
            onClick={handleClose}
            aria-label="Close"
            disabled={uploading}
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="rc-upload-body">
          {successCount !== null ? (
            /* Success state */
            <div className="rc-upload-success">
              <h3>Upload Complete</h3>
              <p>
                {successCount} report card{successCount !== 1 ? 's' : ''} uploaded
                successfully!
              </p>
            </div>
          ) : (
            <>
              {/* Drop zone */}
              <div
                className={`rc-upload-drop-zone${isDragging ? ' dragging' : ''}${files.length > 0 ? ' has-files' : ''}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={files.length === 0 ? handleBrowseClick : undefined}
              >
                {files.length === 0 ? (
                  <div className="rc-upload-drop-content">
                    <span className="rc-upload-icon">{'\u{1F4C1}'}</span>
                    <p>Drag report cards here or click to browse</p>
                    <small>
                      PDF, JPG, PNG — up to {MAX_FILE_SIZE_MB} MB each, max{' '}
                      {MAX_FILES} files
                    </small>
                  </div>
                ) : (
                  <>
                    <div className="rc-upload-file-list">
                      {files.map((file, idx) => (
                        <div key={`${file.name}-${idx}`} className="rc-upload-file-item">
                          <span className="rc-upload-file-icon">
                            {getFileIcon(file.name)}
                          </span>
                          <div className="rc-upload-file-info">
                            <span className="rc-upload-file-name">{file.name}</span>
                            <span className="rc-upload-file-size">
                              {formatFileSize(file.size)}
                            </span>
                          </div>
                          <button
                            className="rc-upload-file-remove"
                            onClick={() => removeFile(idx)}
                            aria-label={`Remove ${file.name}`}
                            disabled={uploading}
                          >
                            &times;
                          </button>
                        </div>
                      ))}
                    </div>
                    {files.length < MAX_FILES && (
                      <button
                        className="rc-upload-add-more"
                        onClick={handleBrowseClick}
                        disabled={uploading}
                      >
                        + Add more files
                      </button>
                    )}
                  </>
                )}
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                multiple
                style={{ display: 'none' }}
                onChange={handleFileInputChange}
              />

              {/* School name field */}
              <div className="rc-upload-field">
                <label htmlFor="rc-school-name">School name (optional)</label>
                <input
                  id="rc-school-name"
                  type="text"
                  value={schoolName}
                  onChange={e => setSchoolName(e.target.value)}
                  placeholder="e.g. Maple Leaf Public School"
                  disabled={uploading}
                />
              </div>

              {/* Progress */}
              {uploading && (
                <div className="rc-upload-progress">
                  Uploading {files.length} file{files.length !== 1 ? 's' : ''}...
                </div>
              )}

              {/* Error */}
              {error && <div className="rc-upload-error">{error}</div>}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="rc-upload-footer">
          {successCount !== null ? (
            <button className="btn-primary" onClick={handleClose}>
              Close
            </button>
          ) : (
            <>
              <button
                className="btn-secondary"
                onClick={handleClose}
                disabled={uploading}
              >
                Cancel
              </button>
              <button
                className="btn-primary"
                onClick={handleUpload}
                disabled={uploading || files.length === 0}
              >
                {uploading
                  ? 'Uploading...'
                  : `Upload${files.length > 0 ? ` (${files.length})` : ''}`}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
