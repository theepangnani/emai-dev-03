import { useState, useRef, useCallback } from 'react';
import { bugReportsApi } from '../api/bugReports';
import { useFocusTrap } from '../utils/useFocusTrap';
import './BugReportModal.css';

interface BugReportModalProps {
  open: boolean;
  onClose: () => void;
}

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB
const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];

export function BugReportModal({ open, onClose }: BugReportModalProps) {
  const [description, setDescription] = useState('');
  const [screenshot, setScreenshot] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const trapRef = useFocusTrap(open, onClose);

  const resetForm = useCallback(() => {
    setDescription('');
    setScreenshot(null);
    setPreviewUrl(null);
    setError('');
    setSuccess(false);
  }, []);

  const handleClose = useCallback(() => {
    resetForm();
    onClose();
  }, [onClose, resetForm]);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) {
      setScreenshot(null);
      setPreviewUrl(null);
      return;
    }

    if (!ALLOWED_TYPES.includes(file.type)) {
      setError('Please select a PNG, JPG, or WebP image.');
      e.target.value = '';
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      setError('Screenshot must be under 5 MB.');
      e.target.value = '';
      return;
    }

    setError('');
    setScreenshot(file);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
  }, []);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;

    setError('');
    setSubmitting(true);

    try {
      await bugReportsApi.submit({
        description: description || undefined,
        screenshot: screenshot || undefined,
        pageUrl: window.location.href,
        userAgent: navigator.userAgent,
      });
      setSuccess(true);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || 'Failed to submit bug report. Please try again.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }, [description, screenshot, submitting]);

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal" ref={trapRef} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Report a Bug">
        <div className="modal-header">
          <h2>Report a Bug</h2>
          <button className="modal-close" onClick={handleClose} aria-label="Close">&times;</button>
        </div>

        {success ? (
          <div className="bug-report-success">
            <h3>Thank you!</h3>
            <p>Your bug report has been submitted. Our team will look into it.</p>
            <div className="bug-report-actions">
              <button className="btn-submit" onClick={handleClose}>Close</button>
            </div>
          </div>
        ) : (
          <form className="bug-report-form" onSubmit={handleSubmit}>
            <label>
              Description
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What went wrong? Describe the issue..."
                maxLength={2000}
              />
            </label>

            <label>
              Screenshot (optional)
              <input
                ref={fileRef}
                type="file"
                accept="image/png,image/jpeg,image/jpg,image/webp"
                className="bug-report-file-input"
                onChange={handleFileChange}
              />
            </label>

            {previewUrl && (
              <img src={previewUrl} alt="Screenshot preview" className="bug-report-preview" />
            )}

            {error && <div className="bug-report-error">{error}</div>}

            <div className="bug-report-actions">
              <button type="button" className="btn-cancel" onClick={handleClose}>Cancel</button>
              <button type="submit" className="btn-submit" disabled={submitting}>
                {submitting ? 'Submitting...' : 'Submit Report'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
