import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  fetchGoogleClassroomPreview,
  parseScreenshot,
  bulkCreateClasses,
  type PreviewResponse,
  type BulkCreateRow,
  type BulkCreateResponse,
} from '../api/classImport';
import ImportReviewTable, { validateRow, type EditableRow } from './ImportReviewTable';
import { useFocusTrap } from '../hooks/useFocusTrap';

type TabId = 'google' | 'screenshot';

type Props = {
  open: boolean;
  onClose: () => void;
  onCreated: (count: number) => void;
};

const MAX_FILE_BYTES = 10 * 1024 * 1024;

function emptyRow(): EditableRow {
  return {
    class_name: '',
    section: null,
    teacher_name: '',
    teacher_email: null,
    google_classroom_id: null,
    existing: false,
    selected: true,
  };
}

export default function ImportClassesModal({ open, onClose, onCreated }: Props) {
  const modalRef = useFocusTrap<HTMLDivElement>(open, onClose);
  const prevOpenRef = useRef(false);

  const [activeTab, setActiveTab] = useState<TabId>('google');

  // Google tab state
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewLoaded, setPreviewLoaded] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [googleRows, setGoogleRows] = useState<EditableRow[]>([]);

  // Screenshot tab state
  const [file, setFile] = useState<File | null>(null);
  const [filePreviewUrl, setFilePreviewUrl] = useState<string | null>(null);
  const [parseLoading, setParseLoading] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [screenshotRows, setScreenshotRows] = useState<EditableRow[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Submit state
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<BulkCreateResponse | null>(null);

  // Reset everything when the modal opens
  useEffect(() => {
    const wasOpen = prevOpenRef.current;
    prevOpenRef.current = open;
    if (!open || wasOpen) return;
    setActiveTab('google');
    setPreviewLoading(false);
    setPreviewLoaded(false);
    setPreviewError(null);
    setPreview(null);
    setGoogleRows([]);
    setFile(null);
    setFilePreviewUrl((url) => {
      if (url) URL.revokeObjectURL(url);
      return null;
    });
    setParseLoading(false);
    setParseError(null);
    setScreenshotRows([]);
    setDragOver(false);
    setSubmitting(false);
    setSubmitError(null);
    setResult(null);
  }, [open]);

  // Free blob URL when file changes / unmount
  useEffect(() => {
    return () => {
      if (filePreviewUrl) URL.revokeObjectURL(filePreviewUrl);
    };
  }, [filePreviewUrl]);

  const loadPreview = useCallback(async () => {
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const data = await fetchGoogleClassroomPreview();
      setPreview(data);
      if (data.connected) {
        setGoogleRows(
          data.courses.map((c) => ({
            class_name: c.class_name,
            section: c.section,
            teacher_name: c.teacher_name,
            teacher_email: c.teacher_email,
            google_classroom_id: c.google_classroom_id,
            existing: c.existing,
            selected: !c.existing,
          })),
        );
      } else {
        setGoogleRows([]);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load Google Classroom preview';
      setPreviewError(msg);
    } finally {
      setPreviewLoading(false);
      setPreviewLoaded(true);
    }
  }, []);

  // Load preview once, when switching to google tab for the first time
  useEffect(() => {
    if (!open) return;
    if (activeTab !== 'google') return;
    if (previewLoaded || previewLoading) return;
    void loadPreview();
  }, [open, activeTab, previewLoaded, previewLoading, loadPreview]);

  const handleFileSelected = (f: File | null) => {
    if (!f) return;
    if (f.size > MAX_FILE_BYTES) {
      setParseError('File is larger than 10 MB.');
      return;
    }
    if (!f.type.startsWith('image/')) {
      setParseError('Please choose an image file.');
      return;
    }
    setParseError(null);
    setFile(f);
    setFilePreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(f);
    });
    setScreenshotRows([]);
  };

  const handleParse = async () => {
    if (!file) return;
    setParseLoading(true);
    setParseError(null);
    try {
      const data = await parseScreenshot(file);
      setScreenshotRows(
        data.parsed.map((r) => ({
          class_name: r.class_name,
          section: r.section,
          teacher_name: r.teacher_name,
          teacher_email: r.teacher_email,
          google_classroom_id: null,
          existing: false,
          selected: true,
        })),
      );
    } catch (err: unknown) {
      const anyErr = err as { response?: { status?: number } };
      if (anyErr?.response?.status === 422) {
        setParseError(
          "We couldn't read that screenshot. Try a clearer one or use the Google Classroom tab if your account is connected.",
        );
      } else {
        const msg = err instanceof Error ? err.message : 'Failed to parse screenshot';
        setParseError(msg);
      }
    } finally {
      setParseLoading(false);
    }
  };

  const activeRows = activeTab === 'google' ? googleRows : screenshotRows;

  const selectedValidRows = useMemo(
    () => activeRows.filter((r) => r.selected && !validateRow(r)),
    [activeRows],
  );
  const hasSelectedWithErrors = useMemo(
    () => activeRows.some((r) => r.selected && !!validateRow(r)),
    [activeRows],
  );
  const confirmCount = selectedValidRows.length;
  const confirmDisabled = submitting || confirmCount === 0 || hasSelectedWithErrors;

  const handleSubmit = async () => {
    if (confirmDisabled) return;
    setSubmitting(true);
    setSubmitError(null);
    const payload: BulkCreateRow[] = selectedValidRows.map((r) => ({
      class_name: r.class_name.trim(),
      section: r.section && r.section.trim() ? r.section.trim() : null,
      teacher_name: r.teacher_name.trim(),
      teacher_email: r.teacher_email && r.teacher_email.trim() ? r.teacher_email.trim() : null,
      google_classroom_id: r.google_classroom_id ?? null,
    }));
    try {
      const res = await bulkCreateClasses(payload);
      setResult(res);
    } catch (err: unknown) {
      const anyErr = err as { response?: { data?: { detail?: string } } };
      setSubmitError(anyErr?.response?.data?.detail || 'Failed to create classes');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCloseResult = () => {
    if (!result) {
      onClose();
      return;
    }
    const createdCount = result.created.length;
    onCreated(createdCount);
    onClose();
  };

  if (!open) return null;

  // --- Results summary view ---
  if (result) {
    const createdCount = result.created.length;
    const failedItems = result.failed;
    const skipped = failedItems.filter((f) => typeof f.existing_course_id === 'number').length;
    const failed = failedItems.length - skipped;
    return (
      <div className="modal-overlay">
        <div
          className="modal modal-lg"
          role="dialog"
          aria-modal="true"
          aria-label="Import classes result"
          ref={modalRef}
        >
          <h2>Import complete</h2>
          <div className="modal-form">
            <p className="modal-desc">
              Created <strong>{createdCount}</strong>, skipped <strong>{skipped}</strong> (already imported), failed <strong>{failed}</strong>.
            </p>
            {failedItems.length > 0 && (
              <ul className="import-result-list">
                {failedItems.map((f) => (
                  <li key={f.index}>
                    Row {f.index + 1}: {f.error}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="modal-actions">
            <button className="generate-btn" onClick={handleCloseResult}>
              Done
            </button>
          </div>
        </div>
      </div>
    );
  }

  const googleConnected = preview?.connected === true;
  const googleConnectUrl = preview && !preview.connected ? preview.connect_url : null;

  return (
    <div className="modal-overlay">
      <div
        className="modal modal-lg import-classes-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Import classes"
        ref={modalRef}
      >
        <h2>Import classes</h2>
        <p className="modal-desc">Bring your Google Classroom classes and teachers into ClassBridge.</p>

        <div className="import-tabs" role="tablist" aria-label="Import source">
          <button
            role="tab"
            type="button"
            id="import-tab-google"
            aria-selected={activeTab === 'google'}
            aria-controls="import-panel-google"
            className={`import-tab${activeTab === 'google' ? ' active' : ''}`}
            onClick={() => setActiveTab('google')}
            disabled={submitting}
          >
            From Google Classroom
          </button>
          <button
            role="tab"
            type="button"
            id="import-tab-screenshot"
            aria-selected={activeTab === 'screenshot'}
            aria-controls="import-panel-screenshot"
            className={`import-tab${activeTab === 'screenshot' ? ' active' : ''}`}
            onClick={() => setActiveTab('screenshot')}
            disabled={submitting}
          >
            From screenshot
          </button>
        </div>

        <div className="modal-form">
          {activeTab === 'google' && (
            <div
              role="tabpanel"
              id="import-panel-google"
              aria-labelledby="import-tab-google"
              className="import-panel"
            >
              {previewLoading && (
                <div className="import-skeleton" aria-live="polite">
                  <div className="import-skeleton-row" />
                  <div className="import-skeleton-row" />
                  <div className="import-skeleton-row" />
                </div>
              )}
              {!previewLoading && previewError && (
                <div className="import-error">{previewError}</div>
              )}
              {!previewLoading && !previewError && preview && !googleConnected && (
                <div className="import-connect">
                  <p>Connect your Google account to import classes directly from Google Classroom.</p>
                  {googleConnectUrl && (
                    <a className="generate-btn" href={googleConnectUrl}>
                      Connect Google
                    </a>
                  )}
                </div>
              )}
              {!previewLoading && !previewError && googleConnected && googleRows.length === 0 && (
                <div className="import-empty">
                  We didn't find any Google Classroom courses on your account.
                </div>
              )}
              {!previewLoading && !previewError && googleConnected && googleRows.length > 0 && (
                <ImportReviewTable
                  rows={googleRows}
                  onChange={setGoogleRows}
                  onRemove={(i) => setGoogleRows((rows) => rows.filter((_, idx) => idx !== i))}
                  onAdd={() => setGoogleRows((rows) => [...rows, emptyRow()])}
                  busy={submitting}
                />
              )}
            </div>
          )}

          {activeTab === 'screenshot' && (
            <div
              role="tabpanel"
              id="import-panel-screenshot"
              aria-labelledby="import-tab-screenshot"
              className="import-panel"
            >
              <div
                className={`import-dropzone${dragOver ? ' is-dragging' : ''}`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  const f = e.dataTransfer.files?.[0] ?? null;
                  handleFileSelected(f);
                }}
                onClick={() => fileInputRef.current?.click()}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    fileInputRef.current?.click();
                  }
                }}
                role="button"
                tabIndex={0}
                aria-label="Upload screenshot"
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  style={{ display: 'none' }}
                  onChange={(e) => handleFileSelected(e.target.files?.[0] ?? null)}
                />
                {!file && (
                  <p>
                    Drag an image here, or <span className="import-dropzone-link">click to browse</span>.
                    <br />
                    <small>PNG / JPG up to 10 MB.</small>
                  </p>
                )}
                {file && filePreviewUrl && (
                  <div className="import-preview">
                    <img src={filePreviewUrl} alt="Screenshot preview" className="import-preview-img" />
                    <div className="import-preview-meta">
                      <span>{file.name}</span>
                      <button
                        type="button"
                        className="cancel-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          setFile(null);
                          setFilePreviewUrl((prev) => {
                            if (prev) URL.revokeObjectURL(prev);
                            return null;
                          });
                          setScreenshotRows([]);
                        }}
                        disabled={parseLoading || submitting}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {parseError && <div className="import-error">{parseError}</div>}

              {file && (
                <div className="import-parse-actions">
                  <button
                    type="button"
                    className="generate-btn"
                    onClick={handleParse}
                    disabled={parseLoading || submitting}
                  >
                    {parseLoading ? 'AI is reading your screenshot…' : 'Parse screenshot'}
                  </button>
                </div>
              )}

              {screenshotRows.length > 0 && (
                <ImportReviewTable
                  rows={screenshotRows}
                  onChange={setScreenshotRows}
                  onRemove={(i) => setScreenshotRows((rows) => rows.filter((_, idx) => idx !== i))}
                  onAdd={() => setScreenshotRows((rows) => [...rows, emptyRow()])}
                  busy={submitting}
                  showCheckbox={false}
                />
              )}
            </div>
          )}

          {submitError && <div className="import-error">{submitError}</div>}
        </div>

        <div className="modal-actions">
          <button
            type="button"
            className="cancel-btn"
            onClick={onClose}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="generate-btn"
            onClick={handleSubmit}
            disabled={confirmDisabled}
          >
            {submitting ? 'Creating…' : `Create ${confirmCount} class${confirmCount === 1 ? '' : 'es'}`}
          </button>
        </div>
      </div>
    </div>
  );
}
