import { useState, useRef, useCallback } from 'react';
import { courseContentsApi } from '../api/client';
import type { BulkUploadResponse, BulkUploadFileResult } from '../api/courses';
import { UploadProgressBar, type UploadStatus } from './UploadProgressBar';
import './BulkImportWizard.css';

interface CourseOption {
  id: number;
  name: string;
}

interface BulkImportWizardProps {
  open: boolean;
  onClose: () => void;
  /** Available courses to upload to */
  courses: CourseOption[];
  /** Pre-selected course ID (e.g. when opened from CourseDetailPage) */
  defaultCourseId?: number;
  /** Called after wizard completes to refresh content lists */
  onComplete?: () => void;
}

type WizardStep = 'select' | 'preview' | 'course' | 'upload' | 'summary';

interface FileEntry {
  file: File;
  /** Relative path within folder (if available) */
  relativePath: string;
  /** Whether this file should be included */
  included: boolean;
}

const MAX_FILE_SIZE_MB = 100;
const MAX_BULK_FILES = 20;

const CONTENT_TYPES = [
  { value: 'notes', label: 'Notes' },
  { value: 'syllabus', label: 'Syllabus' },
  { value: 'labs', label: 'Labs' },
  { value: 'assignments', label: 'Assignments' },
  { value: 'readings', label: 'Readings' },
  { value: 'resources', label: 'Resources' },
  { value: 'other', label: 'Other' },
];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function getFileIcon(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  const icons: Record<string, string> = {
    pdf: '\uD83D\uDCC4',
    doc: '\uD83D\uDCC3', docx: '\uD83D\uDCC3',
    xls: '\uD83D\uDCCA', xlsx: '\uD83D\uDCCA', csv: '\uD83D\uDCCA',
    ppt: '\uD83D\uDCBB', pptx: '\uD83D\uDCBB',
    png: '\uD83D\uDDBC', jpg: '\uD83D\uDDBC', jpeg: '\uD83D\uDDBC', gif: '\uD83D\uDDBC',
    txt: '\uD83D\uDCDD', md: '\uD83D\uDCDD',
    zip: '\uD83D\uDCE6',
  };
  return icons[ext] || '\uD83D\uDCC1';
}

export function BulkImportWizard({
  open,
  onClose,
  courses,
  defaultCourseId,
  onComplete,
}: BulkImportWizardProps) {
  const [step, setStep] = useState<WizardStep>('select');
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<number | ''>(defaultCourseId || '');
  const [contentType, setContentType] = useState('notes');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus | null>(null);
  const [uploadErrorMsg, setUploadErrorMsg] = useState('');
  const [uploadResult, setUploadResult] = useState<BulkUploadResponse | null>(null);
  const [selectError, setSelectError] = useState('');

  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const resetWizard = useCallback(() => {
    setStep('select');
    setFiles([]);
    setSelectedCourseId(defaultCourseId || '');
    setContentType('notes');
    setUploadProgress(0);
    setUploadStatus(null);
    setUploadErrorMsg('');
    setUploadResult(null);
    setSelectError('');
    if (fileInputRef.current) fileInputRef.current.value = '';
    if (folderInputRef.current) folderInputRef.current.value = '';
  }, [defaultCourseId]);

  const handleClose = () => {
    if (uploadStatus === 'uploading') {
      abortControllerRef.current?.abort();
    }
    resetWizard();
    onClose();
  };

  const processFileList = (fileList: FileList) => {
    const entries: FileEntry[] = [];
    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i];
      // Skip hidden files and system files
      if (file.name.startsWith('.') || file.name === 'Thumbs.db' || file.name === 'desktop.ini') {
        continue;
      }
      // Use webkitRelativePath if available (folder upload), else just filename
      const relativePath = (file as any).webkitRelativePath || file.name;

      // Skip files that are too large (mark but don't reject all)
      const tooLarge = file.size > MAX_FILE_SIZE_MB * 1024 * 1024;

      entries.push({
        file,
        relativePath,
        included: !tooLarge && file.size > 0,
      });
    }
    return entries;
  };

  const handleFolderSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;

    const entries = processFileList(fileList);
    if (entries.length === 0) {
      setSelectError('No valid files found in selected folder.');
      return;
    }
    setSelectError('');
    setFiles(entries);
    setStep('preview');
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;

    const entries = processFileList(fileList);
    if (entries.length === 0) {
      setSelectError('No valid files selected.');
      return;
    }
    setSelectError('');
    setFiles(entries);
    setStep('preview');
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const fileList = e.dataTransfer.files;
    if (!fileList || fileList.length === 0) return;

    const entries = processFileList(fileList);
    if (entries.length === 0) {
      setSelectError('No valid files found.');
      return;
    }
    setSelectError('');
    setFiles(entries);
    setStep('preview');
  };

  const toggleFile = (index: number) => {
    setFiles(prev => prev.map((f, i) =>
      i === index ? { ...f, included: !f.included } : f
    ));
  };

  const toggleAll = (included: boolean) => {
    setFiles(prev => prev.map(f => ({
      ...f,
      included: f.file.size > 0 && f.file.size <= MAX_FILE_SIZE_MB * 1024 * 1024 ? included : false,
    })));
  };

  const includedFiles = files.filter(f => f.included);
  const totalSize = includedFiles.reduce((sum, f) => sum + f.file.size, 0);

  const handleStartUpload = async () => {
    if (!selectedCourseId || includedFiles.length === 0) return;

    setStep('upload');
    setUploadStatus('uploading');
    setUploadProgress(0);
    setUploadErrorMsg('');

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      const filesToUpload = includedFiles.map(f => f.file);
      const result = await courseContentsApi.bulkUpload(
        filesToUpload,
        selectedCourseId as number,
        contentType,
        {
          onUploadProgress: (event) => {
            const percent = Math.round((event.loaded * 100) / (event.total || 1));
            setUploadProgress(percent);
          },
          signal: abortController.signal,
        },
      );
      setUploadResult(result);
      setUploadStatus('complete');
      setUploadProgress(100);
      setStep('summary');
    } catch (err: unknown) {
      if (abortController.signal.aborted) {
        setUploadStatus('cancelled');
        setUploadErrorMsg('Upload was cancelled.');
      } else {
        setUploadStatus('error');
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setUploadErrorMsg(detail || 'Upload failed. Please try again.');
      }
    } finally {
      abortControllerRef.current = null;
    }
  };

  const handleCancelUpload = () => {
    abortControllerRef.current?.abort();
  };

  const handleFinish = () => {
    resetWizard();
    onComplete?.();
    onClose();
  };

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal modal-lg bulk-import-wizard" onClick={(e) => e.stopPropagation()}>
        {/* Wizard header with step indicator */}
        <div className="biw-header">
          <h2>Import Files</h2>
          <div className="biw-steps">
            {(['select', 'preview', 'course', 'upload', 'summary'] as WizardStep[]).map((s, i) => (
              <div
                key={s}
                className={`biw-step-dot${step === s ? ' active' : ''}${
                  (['select', 'preview', 'course', 'upload', 'summary'] as WizardStep[]).indexOf(step) > i ? ' done' : ''
                }`}
              >
                {i + 1}
              </div>
            ))}
          </div>
        </div>

        {/* Step 1: Select Files */}
        {step === 'select' && (
          <div className="biw-content">
            <p className="biw-description">
              Select a folder or multiple files to import. You can review and pick which files to upload next.
            </p>
            <div
              className="biw-drop-zone"
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
            >
              <div className="biw-drop-zone-content">
                <span className="biw-drop-icon">{'\uD83D\uDCC2'}</span>
                <p>Drag & drop files here</p>
                <div className="biw-drop-buttons">
                  {/* Hidden inputs */}
                  <input
                    ref={folderInputRef}
                    type="file"
                    // @ts-expect-error webkitdirectory is non-standard but widely supported
                    webkitdirectory=""
                    multiple
                    style={{ display: 'none' }}
                    onChange={handleFolderSelect}
                  />
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.docx,.doc,.txt,.md,.xlsx,.xls,.csv,.pptx,.ppt,.png,.jpg,.jpeg,.gif,.bmp,.tiff,.webp,.zip"
                    style={{ display: 'none' }}
                    onChange={handleFileSelect}
                  />
                  <button
                    className="generate-btn"
                    onClick={() => folderInputRef.current?.click()}
                  >
                    Select Folder
                  </button>
                  <button
                    className="cancel-btn"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    Select Files
                  </button>
                </div>
                <small>Supports: PDF, Word, Excel, PowerPoint, Images, Text, ZIP</small>
                <small>Max {MAX_FILE_SIZE_MB} MB per file, up to {MAX_BULK_FILES} files</small>
              </div>
            </div>
            {selectError && (
              <div className="biw-error">{selectError}</div>
            )}
            <div className="biw-actions">
              <button className="cancel-btn" onClick={handleClose}>Cancel</button>
            </div>
          </div>
        )}

        {/* Step 2: Preview files */}
        {step === 'preview' && (
          <div className="biw-content">
            <div className="biw-preview-header">
              <p className="biw-description">
                {files.length} file{files.length !== 1 ? 's' : ''} found.
                Select which files to upload ({includedFiles.length} selected, {formatFileSize(totalSize)} total).
              </p>
              {includedFiles.length > MAX_BULK_FILES && (
                <div className="biw-warning">
                  Too many files selected. Maximum {MAX_BULK_FILES} files per upload.
                  Please deselect some files.
                </div>
              )}
              <div className="biw-select-all">
                <button className="biw-link-btn" onClick={() => toggleAll(true)}>Select All</button>
                <button className="biw-link-btn" onClick={() => toggleAll(false)}>Deselect All</button>
              </div>
            </div>
            <div className="biw-file-list">
              {files.map((entry, idx) => {
                const tooLarge = entry.file.size > MAX_FILE_SIZE_MB * 1024 * 1024;
                const empty = entry.file.size === 0;
                return (
                  <label
                    key={idx}
                    className={`biw-file-item${!entry.included ? ' excluded' : ''}${tooLarge || empty ? ' invalid' : ''}`}
                  >
                    <input
                      type="checkbox"
                      checked={entry.included}
                      onChange={() => toggleFile(idx)}
                      disabled={tooLarge || empty}
                    />
                    <span className="biw-file-icon">{getFileIcon(entry.file.name)}</span>
                    <div className="biw-file-details">
                      <span className="biw-file-name" title={entry.relativePath}>
                        {entry.relativePath}
                      </span>
                      <span className="biw-file-size">
                        {formatFileSize(entry.file.size)}
                        {tooLarge && <span className="biw-file-warning"> (too large)</span>}
                        {empty && <span className="biw-file-warning"> (empty)</span>}
                      </span>
                    </div>
                  </label>
                );
              })}
            </div>
            <div className="biw-actions">
              <button className="cancel-btn" onClick={() => { setStep('select'); setFiles([]); }}>Back</button>
              <button
                className="generate-btn"
                onClick={() => setStep('course')}
                disabled={includedFiles.length === 0 || includedFiles.length > MAX_BULK_FILES}
              >
                Next: Choose Class
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Select target course */}
        {step === 'course' && (
          <div className="biw-content">
            <p className="biw-description">
              Choose the class and content type for {includedFiles.length} file{includedFiles.length !== 1 ? 's' : ''}.
            </p>
            <div className="biw-course-form">
              <label>
                Class *
                <select
                  value={selectedCourseId}
                  onChange={(e) => setSelectedCourseId(e.target.value ? Number(e.target.value) : '')}
                >
                  <option value="">Select a class...</option>
                  {courses.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </label>
              <label>
                Content Type
                <select value={contentType} onChange={(e) => setContentType(e.target.value)}>
                  {CONTENT_TYPES.map(t => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </label>
            </div>
            <div className="biw-upload-summary">
              <strong>{includedFiles.length}</strong> file{includedFiles.length !== 1 ? 's' : ''} ({formatFileSize(totalSize)})
              {selectedCourseId && (
                <> will be uploaded to <strong>{courses.find(c => c.id === selectedCourseId)?.name}</strong></>
              )}
            </div>
            <div className="biw-actions">
              <button className="cancel-btn" onClick={() => setStep('preview')}>Back</button>
              <button
                className="generate-btn"
                onClick={handleStartUpload}
                disabled={!selectedCourseId}
              >
                Upload {includedFiles.length} File{includedFiles.length !== 1 ? 's' : ''}
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Upload progress */}
        {step === 'upload' && (
          <div className="biw-content">
            <p className="biw-description">
              Uploading {includedFiles.length} file{includedFiles.length !== 1 ? 's' : ''}...
            </p>
            <div className="biw-upload-progress">
              <UploadProgressBar
                fileName={`${includedFiles.length} files (${formatFileSize(totalSize)})`}
                fileSize={totalSize}
                progress={uploadProgress}
                status={uploadStatus || 'uploading'}
                errorMessage={uploadErrorMsg}
                onCancel={handleCancelUpload}
                onRetry={handleStartUpload}
              />
            </div>
            {uploadStatus === 'cancelled' && (
              <div className="biw-actions">
                <button className="cancel-btn" onClick={handleClose}>Close</button>
                <button className="generate-btn" onClick={() => { setStep('course'); setUploadStatus(null); }}>
                  Try Again
                </button>
              </div>
            )}
            {uploadStatus === 'error' && (
              <div className="biw-actions">
                <button className="cancel-btn" onClick={handleClose}>Close</button>
                <button className="generate-btn" onClick={handleStartUpload}>
                  Retry Upload
                </button>
              </div>
            )}
          </div>
        )}

        {/* Step 5: Summary */}
        {step === 'summary' && uploadResult && (
          <div className="biw-content">
            <div className="biw-summary-header">
              <h3>Import Complete</h3>
              <div className="biw-summary-stats">
                <div className="biw-stat biw-stat--success">
                  <span className="biw-stat-number">{uploadResult.succeeded}</span>
                  <span className="biw-stat-label">Succeeded</span>
                </div>
                {uploadResult.failed > 0 && (
                  <div className="biw-stat biw-stat--error">
                    <span className="biw-stat-number">{uploadResult.failed}</span>
                    <span className="biw-stat-label">Failed</span>
                  </div>
                )}
                <div className="biw-stat">
                  <span className="biw-stat-number">{uploadResult.total}</span>
                  <span className="biw-stat-label">Total</span>
                </div>
              </div>
            </div>
            <div className="biw-results-list">
              {uploadResult.results.map((r: BulkUploadFileResult, idx: number) => (
                <div key={idx} className={`biw-result-item ${r.success ? 'biw-result--success' : 'biw-result--error'}`}>
                  <span className="biw-result-icon">{r.success ? '\u2705' : '\u274C'}</span>
                  <span className="biw-result-filename" title={r.filename}>{r.filename}</span>
                  {r.error && <span className="biw-result-error">{r.error}</span>}
                </div>
              ))}
            </div>
            <div className="biw-actions">
              <button className="generate-btn" onClick={handleFinish}>
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
