import { useState, useRef } from 'react';
import { courseContentsApi, type CourseContentItem, type CourseContentUpdateResponse, type StudyGuide } from '../../api/client';

interface ReplaceDocumentModalProps {
  content: CourseContentItem;
  guides: StudyGuide[];
  onClose: () => void;
  onContentUpdated: (result: CourseContentUpdateResponse) => void;
  showToast: (msg: string) => void;
  onShowRegenPrompt: () => void;
  onReloadData: () => Promise<void>;
  onUploadStatusChange: (status: 'uploading' | 'success' | 'error' | null) => void;
}

const MAX_FILE_SIZE_MB = 20;
const MAX_FILES = 10;
const ACCEPTED_TYPES = '.pdf,.docx,.doc,.txt,.md,.xlsx,.xls,.csv,.pptx,.ppt,.png,.jpg,.jpeg,.gif,.bmp,.tiff,.webp,.zip';
const IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp'];

function hasImageFile(files: File[]): boolean {
  return files.some(f => IMAGE_EXTS.some(ext => f.name.toLowerCase().endsWith(ext)));
}

export function ReplaceDocumentModal({
  content,
  guides,
  onClose,
  onContentUpdated,
  showToast,
  onShowRegenPrompt,
  onReloadData,
  onUploadStatusChange,
}: ReplaceDocumentModalProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [fileError, setFileError] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadState, setUploadState] = useState<'uploading' | 'complete' | 'error' | 'cancelled' | null>(null);
  const [uploadErrorMsg, setUploadErrorMsg] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const replacingRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const addFiles = (incoming: FileList | File[]) => {
    const arr = Array.from(incoming);
    const oversized = arr.filter(f => f.size > MAX_FILE_SIZE_MB * 1024 * 1024);
    if (oversized.length > 0) {
      setFileError(`File(s) exceed ${MAX_FILE_SIZE_MB} MB limit: ${oversized.map(f => f.name).join(', ')}`);
      return;
    }
    setFiles(prev => {
      const combined = [...prev, ...arr];
      if (combined.length > MAX_FILES) {
        setFileError(`Maximum ${MAX_FILES} files allowed`);
        return combined.slice(0, MAX_FILES);
      }
      setFileError('');
      return combined;
    });
  };

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
    setFileError('');
  };

  const handleUpload = async () => {
    if (files.length === 0 || replacingRef.current) return;
    replacingRef.current = true;
    const hadFile = content.has_file;

    setUploadState('uploading');
    setUploadProgress(0);
    setUploadErrorMsg('');
    onUploadStatusChange('uploading');

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      // First file replaces / attaches to the current content item
      const result = await courseContentsApi.replaceFile(content.id, files[0]);

      // Additional files create new content items in the same course
      for (let i = 1; i < files.length; i++) {
        await courseContentsApi.uploadFile(files[i], content.course_id, files[i].name);
      }

      onContentUpdated(result);
      onUploadStatusChange(null);

      const extra = files.length > 1 ? ` ${files.length - 1} additional file(s) added to course.` : '';
      if (result.archived_guides_count > 0) {
        showToast(`Document replaced. ${result.archived_guides_count} linked study material(s) archived.${extra}`);
        onShowRegenPrompt();
        await onReloadData();
      } else {
        const action = hadFile ? 'replaced' : 'uploaded';
        showToast(`Document ${action} successfully.${extra}`);
        await onReloadData();
      }
      // Auto-close after success
      setTimeout(() => onClose(), 1200);
    } catch (err: unknown) {
      if (abortController.signal.aborted) {
        setUploadState('cancelled');
        onUploadStatusChange(null);
      } else {
        setUploadState('error');
        onUploadStatusChange('error');
        setTimeout(() => onUploadStatusChange(null), 5000);
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        const msg = detail || 'Failed to upload document';
        setUploadErrorMsg(msg);
        showToast(msg);
      }
    } finally {
      replacingRef.current = false;
      abortControllerRef.current = null;
    }
  };

  const handleCancelUpload = () => {
    abortControllerRef.current?.abort();
  };

  const handleClose = () => {
    if (uploadState === 'uploading') {
      handleCancelUpload();
    }
    setFiles([]);
    setFileError('');
    setIsDragging(false);
    setUploadState(null);
    setUploadProgress(0);
    if (fileInputRef.current) fileInputRef.current.value = '';
    onClose();
  };

  const isReplace = content.has_file;

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 500 }}>
        <h2>{isReplace ? 'Replace Document' : 'Upload Document'}</h2>
        <p className="cm-replace-warning">
          {isReplace
            ? 'Uploading a new file will replace the current document and re-extract text.'
            : 'Upload files to attach to this content. Text will be extracted automatically.'}
          {isReplace && guides.length > 0 && ' Linked study materials will be archived and can be regenerated.'}
        </p>
        <div
          className={`cm-replace-drop-zone${isDragging ? ' dragging' : ''}${files.length > 0 ? ' has-file' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={(e) => { e.preventDefault(); setIsDragging(false); }}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            if (e.dataTransfer.files.length > 0) addFiles(e.dataTransfer.files);
          }}
          onClick={() => { if (files.length === 0) fileInputRef.current?.click(); }}
        >
          <input
            ref={fileInputRef}
            type="file"
            style={{ display: 'none' }}
            accept={ACCEPTED_TYPES}
            multiple
            onChange={(e) => {
              if (e.target.files && e.target.files.length > 0) addFiles(e.target.files);
              e.target.value = '';
            }}
          />
          {files.length > 0 ? (
            <div className="cm-replace-file-list" onClick={(e) => e.stopPropagation()}>
              {files.map((f, i) => (
                <div key={i} className="cm-replace-file-info">
                  <span className="cm-replace-file-icon">&#128196;</span>
                  <div className="cm-replace-file-details">
                    <span className="cm-replace-file-name">{f.name}</span>
                    <span className="cm-replace-file-size">{(f.size / 1024 / 1024).toFixed(2)} MB</span>
                  </div>
                  <button
                    className="cm-replace-clear-btn"
                    onClick={() => removeFile(i)}
                  >&times;</button>
                </div>
              ))}
              {files.length < MAX_FILES && (
                <button
                  className="cm-replace-add-more"
                  onClick={() => fileInputRef.current?.click()}
                >
                  + Add more files ({MAX_FILES - files.length} remaining)
                </button>
              )}
            </div>
          ) : (
            <div className="cm-replace-drop-content">
              <span className="cm-replace-upload-icon">&#128193;</span>
              <p>Drag & drop files here, or click to browse</p>
              <small>PDF, Word, Excel, PowerPoint, Images, Text, ZIP &middot; up to {MAX_FILES} files &middot; {MAX_FILE_SIZE_MB} MB each</small>
            </div>
          )}
        </div>
        {hasImageFile(files) && (
          <div className="cm-ocr-hint">
            &#10003; OCR enabled — text will be automatically extracted from images
          </div>
        )}
        {fileError && (
          <div className="modal-error">
            <span className="error-icon">!</span>
            <span className="error-message">{fileError}</span>
          </div>
        )}
        <div className="cm-replace-actions">
          <button className="cm-action-btn" onClick={handleClose}>Cancel</button>
          <button className="generate-btn" onClick={handleUpload} disabled={files.length === 0}>
            {isReplace ? 'Replace Document' : `Upload ${files.length > 1 ? `${files.length} Documents` : 'Document'}`}
          </button>
        </div>
      </div>
    </div>
  );
}
