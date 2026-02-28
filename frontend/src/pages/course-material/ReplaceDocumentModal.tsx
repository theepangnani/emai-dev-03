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

const MAX_FILE_SIZE_MB = 100;
const ACCEPTED_TYPES = '.pdf,.docx,.doc,.txt,.md,.xlsx,.xls,.csv,.pptx,.ppt,.png,.jpg,.jpeg,.gif,.bmp,.tiff,.webp,.zip';

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
  const [replaceFile, setReplaceFile] = useState<File | null>(null);
  const [replaceError, setReplaceError] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const replacingRef = useRef(false);

  const handleFileSelect = (file: File) => {
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setReplaceError(`File size exceeds ${MAX_FILE_SIZE_MB} MB limit`);
      return;
    }
    setReplaceFile(file);
    setReplaceError('');
  };

  const handleReplace = async () => {
    if (!replaceFile || replacingRef.current) return;
    replacingRef.current = true;
    const fileToUpload = replaceFile;
    const hadFile = content.has_file;

    onClose();
    onUploadStatusChange('uploading');

    try {
      const result = await courseContentsApi.replaceFile(content.id, fileToUpload);
      onContentUpdated(result);
      onUploadStatusChange(null);
      if (result.archived_guides_count > 0) {
        showToast(`Document replaced. ${result.archived_guides_count} linked study material(s) archived.`);
        onShowRegenPrompt();
        await onReloadData();
      } else {
        showToast(hadFile ? 'Document replaced successfully' : 'Document uploaded successfully');
        await onReloadData();
      }
    } catch (err: unknown) {
      onUploadStatusChange('error');
      setTimeout(() => onUploadStatusChange(null), 5000);
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      showToast(detail || 'Failed to upload document');
    } finally {
      replacingRef.current = false;
    }
  };

  const handleClose = () => {
    setReplaceFile(null);
    setReplaceError('');
    setIsDragging(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 500 }}>
        <h2>{content.has_file ? 'Replace Document' : 'Upload Document'}</h2>
        <p className="cm-replace-warning">
          {content.has_file
            ? 'Uploading a new file will replace the current document and re-extract text.'
            : 'Upload a file to attach to this content. Text will be extracted automatically.'}
          {content.has_file && guides.length > 0 && ' Linked study materials will be archived and can be regenerated.'}
        </p>
        <div
          className={`cm-replace-drop-zone${isDragging ? ' dragging' : ''}${replaceFile ? ' has-file' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={(e) => { e.preventDefault(); setIsDragging(false); }}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            const file = e.dataTransfer.files[0];
            if (file) handleFileSelect(file);
          }}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            style={{ display: 'none' }}
            accept={ACCEPTED_TYPES}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFileSelect(file);
            }}
          />
          {replaceFile ? (
            <div className="cm-replace-file-info">
              <span className="cm-replace-file-icon">&#128196;</span>
              <div className="cm-replace-file-details">
                <span className="cm-replace-file-name">{replaceFile.name}</span>
                <span className="cm-replace-file-size">{(replaceFile.size / 1024 / 1024).toFixed(2)} MB</span>
              </div>
              <button
                className="cm-replace-clear-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  setReplaceFile(null);
                  if (fileInputRef.current) fileInputRef.current.value = '';
                }}
              >&times;</button>
            </div>
          ) : (
            <div className="cm-replace-drop-content">
              <span className="cm-replace-upload-icon">&#128193;</span>
              <p>Drag & drop a file here, or click to browse</p>
              <small>PDF, Word, Excel, PowerPoint, Images, Text, ZIP</small>
            </div>
          )}
        </div>
        {replaceError && (
          <div className="modal-error">
            <span className="error-icon">!</span>
            <span className="error-message">{replaceError}</span>
            <button onClick={handleReplace} className="retry-btn" disabled={!replaceFile}>Try Again</button>
          </div>
        )}
        <div className="cm-replace-actions">
          <button className="cm-action-btn" onClick={handleClose}>Cancel</button>
          <button className="generate-btn" onClick={handleReplace} disabled={!replaceFile}>
            {content.has_file ? 'Replace Document' : 'Upload Document'}
          </button>
        </div>
      </div>
    </div>
  );
}
