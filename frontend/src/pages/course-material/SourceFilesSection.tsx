import { useState, useEffect } from 'react';
import { courseContentsApi, type SourceFileItem } from '../../api/client';

interface SourceFilesSectionProps {
  contentId: number;
  sourceFilesCount: number;
}

function formatFileSize(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function getFileIcon(fileType: string | null, filename: string): string {
  const type = fileType || '';
  const ext = filename.split('.').pop()?.toLowerCase() || '';

  if (type.startsWith('image/') || ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff'].includes(ext)) return '\uD83D\uDDBC\uFE0F';
  if (type === 'application/pdf' || ext === 'pdf') return '\uD83D\uDCC4';
  if (type.includes('word') || ['doc', 'docx'].includes(ext)) return '\uD83D\uDCC3';
  if (type.includes('spreadsheet') || type.includes('excel') || ['xls', 'xlsx', 'csv'].includes(ext)) return '\uD83D\uDCCA';
  if (type.includes('presentation') || type.includes('powerpoint') || ['ppt', 'pptx'].includes(ext)) return '\uD83D\uDCCA';
  if (type.startsWith('text/') || ['txt', 'md', 'rtf'].includes(ext)) return '\uD83D\uDCC4';
  return '\uD83D\uDCC1';
}

function isViewableInline(fileType: string | null): boolean {
  if (!fileType) return false;
  return fileType.startsWith('image/') || fileType === 'application/pdf';
}

export function SourceFilesSection({ contentId, sourceFilesCount }: SourceFilesSectionProps) {
  const [files, setFiles] = useState<SourceFileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (sourceFilesCount === 0) return;
    if (!expanded) return;
    if (files.length > 0) return; // already loaded

    setLoading(true);
    courseContentsApi.listSourceFiles(contentId)
      .then(setFiles)
      .catch(() => setError('Failed to load source files'))
      .finally(() => setLoading(false));
  }, [contentId, sourceFilesCount, expanded, files.length]);

  if (sourceFilesCount === 0) return null;

  const handleDownload = async (file: SourceFileItem) => {
    try {
      await courseContentsApi.downloadSourceFile(file.id, file.filename);
    } catch {
      setError('Failed to download file');
    }
  };

  const handleView = (file: SourceFileItem) => {
    const url = `/api/source-files/${file.id}/download`;
    window.open(url, '_blank');
  };

  return (
    <div className="cm-source-files-section">
      <button
        className="cm-source-files-toggle"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        <span className="cm-source-files-icon">{'\uD83D\uDCCE'}</span>
        <span>Source Files ({sourceFilesCount})</span>
        <span className={`cm-source-files-chevron${expanded ? ' open' : ''}`}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
            <path d="M3 4.5l3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </span>
      </button>

      {expanded && (
        <div className="cm-source-files-list">
          {loading && <p className="cm-source-files-loading">Loading files...</p>}
          {error && <p className="cm-source-files-error">{error}</p>}
          {!loading && !error && files.length === 0 && (
            <p className="cm-source-files-empty">No source files found.</p>
          )}
          {files.map(file => (
            <div key={file.id} className="cm-source-file-item">
              <span className="cm-source-file-icon">{getFileIcon(file.file_type, file.filename)}</span>
              <div className="cm-source-file-info">
                <span className="cm-source-file-name">{file.filename}</span>
                <span className="cm-source-file-meta">
                  {file.file_type && <span className="cm-source-file-type">{file.file_type.split('/').pop()?.toUpperCase()}</span>}
                  {file.file_size != null && <span className="cm-source-file-size">{formatFileSize(file.file_size)}</span>}
                </span>
              </div>
              <div className="cm-source-file-actions">
                {isViewableInline(file.file_type) && (
                  <button
                    className="cm-source-file-btn view"
                    onClick={() => handleView(file)}
                    title="View file"
                  >
                    View
                  </button>
                )}
                <button
                  className="cm-source-file-btn download"
                  onClick={() => handleDownload(file)}
                  title="Download file"
                >
                  Download
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
