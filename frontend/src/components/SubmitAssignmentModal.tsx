import { useState, useRef, useCallback } from 'react';
import { submissionsApi } from '../api/submissions';
import type { SubmissionResponse } from '../api/submissions';
import './SubmitAssignmentModal.css';

const MAX_FILE_SIZE_MB = 10;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
const ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.txt'];

type ActiveTab = 'write' | 'upload';

interface SubmitAssignmentModalProps {
  assignmentId: number;
  assignmentTitle: string;
  dueDate: string | null;
  existingSubmission?: SubmissionResponse | null;
  onSubmitted: (submission: SubmissionResponse) => void;
  onClose: () => void;
}

export function SubmitAssignmentModal({
  assignmentId,
  assignmentTitle,
  dueDate,
  existingSubmission,
  onSubmitted,
  onClose,
}: SubmitAssignmentModalProps) {
  const [activeTab, setActiveTab] = useState<ActiveTab>('write');
  const [textAnswer, setTextAnswer] = useState(existingSubmission?.submission_notes || '');
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isAlreadySubmitted = existingSubmission &&
    (existingSubmission.status === 'submitted' || existingSubmission.status === 'graded' || existingSubmission.status === 'returned');

  const isLate = dueDate ? new Date(dueDate) < new Date() : false;

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleString([], {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const validateFile = (f: File): string | null => {
    const ext = '.' + (f.name.split('.').pop()?.toLowerCase() ?? '');
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `File type '${ext}' not allowed. Accepted: ${ALLOWED_EXTENSIONS.join(', ')}`;
    }
    if (f.size > MAX_FILE_SIZE_BYTES) {
      return `File size exceeds ${MAX_FILE_SIZE_MB} MB limit`;
    }
    return null;
  };

  const handleFileSelect = (f: File) => {
    const err = validateFile(f);
    if (err) {
      setError(err);
      return;
    }
    setError('');
    setFile(f);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFileSelect(dropped);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => setIsDragging(false), []);

  const handleSubmit = async () => {
    if (activeTab === 'write' && !textAnswer.trim()) {
      setError('Please write an answer before submitting.');
      return;
    }
    if (activeTab === 'upload' && !file) {
      setError('Please select a file to upload.');
      return;
    }

    setSubmitting(true);
    setError('');

    try {
      const result = await submissionsApi.submit(assignmentId, {
        text: activeTab === 'write' ? textAnswer.trim() : undefined,
        file: activeTab === 'upload' ? file ?? undefined : undefined,
      });
      setSuccess(true);
      setTimeout(() => {
        onSubmitted(result);
        onClose();
      }, 1200);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div className="sam-overlay" onClick={handleOverlayClick} role="dialog" aria-modal="true" aria-label={`Submit: ${assignmentTitle}`}>
      <div className="sam-modal">
        {/* Header */}
        <div className="sam-header">
          <div className="sam-header-info">
            <h2 className="sam-title">{isAlreadySubmitted ? 'Resubmit' : 'Submit'}: {assignmentTitle}</h2>
            {dueDate && (
              <p className={`sam-due${isLate ? ' sam-due--late' : ''}`}>
                Due: {formatDate(dueDate)}
                {isLate && ' — Submission will be marked late'}
              </p>
            )}
          </div>
          <button className="sam-close" onClick={onClose} aria-label="Close">&times;</button>
        </div>

        {/* Existing submission banner */}
        {isAlreadySubmitted && (
          <div className={`sam-existing-banner${existingSubmission.is_late ? ' late' : ''}`}>
            <span className="sam-existing-label">
              {existingSubmission.status === 'graded'
                ? `Graded: ${existingSubmission.grade ?? '—'}${existingSubmission.is_late ? ' (Late)' : ''}`
                : `Submitted ${formatDate(existingSubmission.submitted_at)}${existingSubmission.is_late ? ' (Late)' : ''}`}
            </span>
            {existingSubmission.has_file && existingSubmission.submission_file_name && (
              <span className="sam-existing-file">File: {existingSubmission.submission_file_name}</span>
            )}
          </div>
        )}

        {/* Tabs */}
        <div className="sam-tabs" role="tablist">
          <button
            role="tab"
            aria-selected={activeTab === 'write'}
            className={`sam-tab${activeTab === 'write' ? ' active' : ''}`}
            onClick={() => { setActiveTab('write'); setError(''); }}
          >
            Write Answer
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'upload'}
            className={`sam-tab${activeTab === 'upload' ? ' active' : ''}`}
            onClick={() => { setActiveTab('upload'); setError(''); }}
          >
            Upload File
          </button>
        </div>

        {/* Tab content */}
        <div className="sam-body">
          {activeTab === 'write' && (
            <div className="sam-write-panel">
              <label htmlFor="sam-text-answer" className="sam-label">Your Answer</label>
              <textarea
                id="sam-text-answer"
                className="sam-textarea"
                value={textAnswer}
                onChange={(e) => setTextAnswer(e.target.value)}
                placeholder="Type your answer here..."
                rows={8}
                disabled={submitting || success}
              />
            </div>
          )}

          {activeTab === 'upload' && (
            <div className="sam-upload-panel">
              <div
                className={`sam-drop-zone${isDragging ? ' dragging' : ''}`}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => fileInputRef.current?.click()}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click(); }}
                aria-label="Upload file drop zone"
              >
                {file ? (
                  <div className="sam-file-selected">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                    <span className="sam-file-name">{file.name}</span>
                    <span className="sam-file-size">({(file.size / 1024 / 1024).toFixed(1)} MB)</span>
                    <button
                      className="sam-file-remove"
                      onClick={(e) => { e.stopPropagation(); setFile(null); }}
                      type="button"
                      aria-label="Remove file"
                    >
                      Remove
                    </button>
                  </div>
                ) : (
                  <>
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="sam-upload-icon" aria-hidden="true">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                    <p className="sam-drop-text">Drop your file here or click to upload</p>
                    <p className="sam-drop-hint">PDF, DOC, DOCX, JPG, PNG, TXT &bull; Max {MAX_FILE_SIZE_MB} MB</p>
                  </>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={ALLOWED_EXTENSIONS.join(',')}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleFileSelect(f);
                  }}
                  style={{ display: 'none' }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Error / Success */}
        {error && <p className="sam-error" role="alert">{error}</p>}
        {success && <p className="sam-success" role="status">Submitted successfully!</p>}

        {/* Actions */}
        <div className="sam-actions">
          <button className="sam-btn-cancel" onClick={onClose} disabled={submitting || success}>
            Cancel
          </button>
          <button
            className="sam-btn-submit"
            onClick={handleSubmit}
            disabled={submitting || success || (activeTab === 'write' ? !textAnswer.trim() : !file)}
          >
            {submitting ? 'Submitting...' : success ? 'Submitted!' : isAlreadySubmitted ? 'Resubmit' : 'Submit'}
          </button>
        </div>
      </div>
    </div>
  );
}
