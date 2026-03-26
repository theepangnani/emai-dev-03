import { useState, useRef } from 'react';
import { courseContentsApi, type CourseContentItem, type CourseContentUpdateResponse, type StudyGuide } from '../../api/client';
import '../../components/UploadMaterialWizard.css';

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

const MAX_FILE_SIZE_MB = 30;
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
  const fileInputRef = useRef<HTMLInputElement>(null);
  const replacingRef = useRef(false);

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

    onClose();
    onUploadStatusChange('uploading');

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
    setFiles([]);
    setFileError('');
    setIsDragging(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
    onClose();
  };

  const isReplace = content.has_file;

  return (
    <div className="upload-wizard-overlay" onClick={handleClose}>
      <div className="upload-wizard-modal" onClick={(e) => e.stopPropagation()}>
        <div className="uw-header">
          <h2 style={{ flex: 1 }}>{isReplace ? 'Replace Document' : 'Upload Class Material'}</h2>
        </div>
        <div className="uw-body">
        <p className="cm-replace-warning">
          {isReplace
            ? 'Uploading a new file will replace the current document and re-extract text.'
            : 'Upload files to attach to this content. Text will be extracted automatically.'}
          {isReplace && guides.length > 0 && ' Linked study materials will be archived and can be regenerated.'}
        </p>
        <div
          className={`uw-drop-zone${isDragging ? ' dragging' : ''}${files.length > 0 ? ' has-files' : ''}`}
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
            <div className="uw-file-list" onClick={(e) => e.stopPropagation()}>
              {files.map((f, i) => (
                <div key={i} className="uw-file-item">
                  <span className="uw-file-icon">&#128196;</span>
                  <div className="uw-file-info">
                    <span className="uw-file-name">{f.name}</span>
                    <span className="uw-file-size">{(f.size / 1024 / 1024).toFixed(2)} MB</span>
                  </div>
                  <button
                    className="uw-file-remove"
                    onClick={() => removeFile(i)}
                  >&times;</button>
                </div>
              ))}
              {files.length < MAX_FILES && (
                <button
                  className="uw-add-more-btn"
                  onClick={() => fileInputRef.current?.click()}
                >
                  + Add more files ({MAX_FILES - files.length} remaining)
                </button>
              )}
            </div>
          ) : (
            <div className="uw-drop-content">
              <span className="uw-upload-icon">&#128193;</span>
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
          <div className="uw-error">
            <span className="uw-error-icon">!</span>
            <span className="uw-error-message">{fileError}</span>
          </div>
        )}
        </div>
        <div className="uw-footer">
          <button className="btn-secondary" onClick={handleClose}>Cancel</button>
          <button className="btn-primary" onClick={handleUpload} disabled={files.length === 0}>
            {isReplace ? 'Replace Document' : `Upload ${files.length > 1 ? `${files.length} Documents` : 'Document'}`}
          </button>
        </div>
      </div>
    </div>
  );
}
