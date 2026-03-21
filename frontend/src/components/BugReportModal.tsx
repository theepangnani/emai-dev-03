import { useState, useRef, useCallback, useEffect } from 'react';
import { bugReportsApi } from '../api/bugReports';
import { useFocusTrap } from '../utils/useFocusTrap';
import './BugReportModal.css';

interface BugReportModalProps {
  open: boolean;
  onClose: () => void;
  prefillDescription?: string;
  prefillPageUrl?: string;
}

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB
const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];

export function BugReportModal({ open, onClose, prefillDescription, prefillPageUrl }: BugReportModalProps) {
  const [description, setDescription] = useState('');
  const [screenshot, setScreenshot] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const trapRef = useFocusTrap(open, onClose);

  // Prefill description when modal opens
  useEffect(() => {
    if (open && prefillDescription) {
      setDescription(prefillDescription);
    }
  }, [open, prefillDescription]);

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

  const setScreenshotFile = useCallback((file: File) => {
    if (!ALLOWED_TYPES.includes(file.type)) {
      setError('Please select a PNG, JPG, or WebP image.');
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      setError('Screenshot must be under 5 MB.');
      return;
    }
    setError('');
    setScreenshot(file);
    setPreviewUrl(URL.createObjectURL(file));
  }, []);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) {
      setScreenshot(null);
      setPreviewUrl(null);
      return;
    }
    setScreenshotFile(file);
  }, [setScreenshotFile]);

  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith('image/')) {
        e.preventDefault();
        const file = items[i].getAsFile();
        if (file) {
          setScreenshotFile(file);
        }
        return;
      }
    }
  }, [setScreenshotFile]);

  const handleRemoveScreenshot = useCallback(() => {
    setScreenshot(null);
    setPreviewUrl(null);
    if (fileRef.current) fileRef.current.value = '';
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
        pageUrl: prefillPageUrl || window.location.href,
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
  }, [description, screenshot, submitting, prefillPageUrl]);

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal" ref={trapRef} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Report a Bug" onPaste={handlePaste}>
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

            <div className="bug-report-screenshot-section">
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
              <p className="bug-report-paste-hint">Or paste from clipboard (Ctrl+V)</p>
            </div>

            {previewUrl && (
              <div className="bug-report-preview-container">
                <img src={previewUrl} alt="Screenshot preview" className="bug-report-preview" />
                <button type="button" className="bug-report-remove-preview" onClick={handleRemoveScreenshot} aria-label="Remove screenshot">&times;</button>
              </div>
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
