import { useState, useRef, useCallback } from 'react';
import { assignmentsApi } from '../api/client';
import type { SubmissionResponse } from '../api/client';
import './AssignmentSubmission.css';

const MAX_FILE_SIZE_MB = 50;
const ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.txt'];

interface AssignmentSubmissionProps {
  assignmentId: number;
  assignmentTitle: string;
  dueDate: string | null;
  submission: SubmissionResponse | null;
  onSubmitted: (submission: SubmissionResponse) => void;
  onClose: () => void;
}

export function AssignmentSubmission({
  assignmentId,
  assignmentTitle,
  dueDate,
  submission,
  onSubmitted,
  onClose,
}: AssignmentSubmissionProps) {
  const [file, setFile] = useState<File | null>(null);
  const [notes, setNotes] = useState(submission?.submission_notes || '');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isResubmission = submission?.status === 'submitted' || submission?.status === 'graded';

  const validateFile = (f: File): string | null => {
    const ext = '.' + f.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `File type '${ext}' not allowed. Accepted: ${ALLOWED_EXTENSIONS.join(', ')}`;
    }
    if (f.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
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

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleSubmit = async () => {
    if (!file && !notes.trim()) {
      setError('Please attach a file or add notes before submitting.');
      return;
    }

    setSubmitting(true);
    setError('');

    try {
      const formData = new FormData();
      if (file) {
        formData.append('file', file);
      }
      if (notes.trim()) {
        formData.append('notes', notes.trim());
      }

      const result = await assignmentsApi.submit(assignmentId, formData);
      onSubmitted(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit assignment. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDownloadExisting = async () => {
    try {
      await assignmentsApi.downloadSubmission(assignmentId);
    } catch {
      setError('Failed to download submission file.');
    }
  };

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

  return (
    <div className="submission-panel">
      <div className="submission-header">
        <h4>{isResubmission ? 'Resubmit' : 'Submit'}: {assignmentTitle}</h4>
        <button className="submission-close-btn" onClick={onClose} aria-label="Close">&times;</button>
      </div>

      {/* Current submission status */}
      {submission && submission.status !== 'pending' && (
        <div className={`submission-status-banner ${submission.is_late ? 'late' : ''} ${submission.status}`}>
          <div className="submission-status-info">
            {submission.status === 'graded' ? (
              <span className="submission-status-label graded">Graded: {submission.grade ?? '—'}{submission.is_late ? ' (Late)' : ''}</span>
            ) : submission.status === 'submitted' ? (
              <span className={`submission-status-label submitted${submission.is_late ? ' late' : ''}`}>
                Submitted {formatDate(submission.submitted_at)}{submission.is_late ? ' (Late)' : ''}
              </span>
            ) : null}
          </div>
          {submission.has_file && submission.submission_file_name && (
            <button className="submission-download-btn" onClick={handleDownloadExisting} type="button">
              Download: {submission.submission_file_name}
            </button>
          )}
          {submission.submission_notes && (
            <p className="submission-existing-notes">Notes: {submission.submission_notes}</p>
          )}
        </div>
      )}

      {dueDate && (
        <p className={`submission-due-info${new Date(dueDate) < new Date() ? ' overdue' : ''}`}>
          Due: {formatDate(dueDate)}
          {new Date(dueDate) < new Date() && ' (submissions will be marked late)'}
        </p>
      )}

      {/* File upload */}
      <div
        className={`submission-drop-zone${isDragging ? ' dragging' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => fileInputRef.current?.click()}
      >
        {file ? (
          <div className="submission-file-info">
            <span className="submission-file-name">{file.name}</span>
            <span className="submission-file-size">({(file.size / 1024 / 1024).toFixed(1)} MB)</span>
            <button
              className="submission-file-remove"
              onClick={(e) => { e.stopPropagation(); setFile(null); }}
              type="button"
            >
              Remove
            </button>
          </div>
        ) : (
          <>
            <p className="submission-drop-text">
              {isResubmission ? 'Drop a new file to replace your submission' : 'Drop your file here or click to upload'}
            </p>
            <p className="submission-drop-hint">
              PDF, DOC, DOCX, JPG, PNG, TXT (max {MAX_FILE_SIZE_MB} MB)
            </p>
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

      {/* Notes */}
      <div className="submission-notes-section">
        <label htmlFor="submission-notes">Notes (optional)</label>
        <textarea
          id="submission-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Add any notes about your submission..."
          rows={3}
          disabled={submitting}
        />
      </div>

      {error && <p className="submission-error">{error}</p>}

      <div className="submission-actions">
        <button className="submission-cancel-btn" onClick={onClose} disabled={submitting}>Cancel</button>
        <button
          className="submission-submit-btn"
          onClick={handleSubmit}
          disabled={submitting || (!file && !notes.trim())}
        >
          {submitting ? 'Submitting...' : isResubmission ? 'Resubmit' : 'Submit'}
        </button>
      </div>
    </div>
  );
}
