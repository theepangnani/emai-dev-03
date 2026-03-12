import { useState, useEffect } from 'react';
import { courseContentsApi, type SourceFileItem } from '../../api/client';

interface SourceFilesSectionProps {
  contentId: number;
  sourceFilesCount: number;
  initialExpanded?: boolean;
}

function formatFileSize(bytes: number | null): string {
  if (bytes === null || bytes === 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(fileType: string | null, filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  if (fileType?.startsWith('image/') || ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff'].includes(ext)) {
    return '\uD83D\uDDBC\uFE0F';
  }
  if (fileType === 'application/pdf' || ext === 'pdf') return '\uD83D\uDCC4';
  if (['doc', 'docx'].includes(ext)) return '\uD83D\uDCC3';
  if (['xls', 'xlsx', 'csv'].includes(ext)) return '\uD83D\uDCCA';
  if (['ppt', 'pptx'].includes(ext)) return '\uD83D\uDCCA';
  if (['txt', 'md', 'rtf'].includes(ext)) return '\uD83D\uDCC4';
  return '\uD83D\uDCC1';
}

function canViewInline(fileType: string | null): boolean {
  if (!fileType) return false;
  return fileType.startsWith('image/') || fileType === 'application/pdf';
}

export function SourceFilesSection({ contentId, sourceFilesCount, initialExpanded = false }: SourceFilesSectionProps) {
  const [files, setFiles] = useState<SourceFileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(initialExpanded);
  const [downloading, setDownloading] = useState<number | null>(null);
  const [viewingFile, setViewingFile] = useState<SourceFileItem | null>(null);
  const [viewBlobUrl, setViewBlobUrl] = useState<string | null>(null);
  const [viewLoading, setViewLoading] = useState(false);

  useEffect(() => {
    if (expanded && files.length === 0) {
      setLoading(true);
      courseContentsApi.listSourceFiles(contentId)
        .then(setFiles)
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, [expanded, contentId, files.length]);

  if (sourceFilesCount === 0) return null;

  const handleDownload = async (file: SourceFileItem) => {
    setDownloading(file.id);
    try {
      await courseContentsApi.downloadSourceFile(contentId, file.id, file.filename);
    } catch { /* ignore */ }
    finally { setDownloading(null); }
  };

  const handleView = async (file: SourceFileItem) => {
    setViewingFile(file);
    setViewBlobUrl(null);
    setViewLoading(true);
    try {
      const url = await courseContentsApi.getSourceFileBlobUrl(contentId, file.id, file.file_type || undefined);
      setViewBlobUrl(url);
    } catch {
      /* fall through — shows loading state */
    } finally {
      setViewLoading(false);
    }
  };

  const handleCloseViewer = () => {
    if (viewBlobUrl) URL.revokeObjectURL(viewBlobUrl);
    setViewingFile(null);
    setViewBlobUrl(null);
  };

  return (
    <div className="cm-source-files">
      <button
        className="cm-source-files-toggle"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        <span className="cm-source-files-icon">{'\uD83D\uDCC2'}</span>
        <span>Source Files ({sourceFilesCount})</span>
        <span className={`cm-source-files-chevron${expanded ? ' open' : ''}`}>{'\u25B6'}</span>
      </button>

      {expanded && (
        <div className="cm-source-files-list">
          {loading ? (
            <p className="cm-source-files-loading">Loading files...</p>
          ) : files.length === 0 ? (
            <p className="cm-source-files-empty">No source files found.</p>
          ) : (
            <ul>
              {files.map(file => (
                <li key={file.id} className="cm-source-file-item">
                  <span className="cm-sf-icon">{getFileIcon(file.file_type, file.filename)}</span>
                  <div className="cm-sf-info">
                    <span className="cm-sf-name">{file.filename}</span>
                    <span className="cm-sf-meta">
                      {formatFileSize(file.file_size)}
                      {file.file_type && <> &middot; {file.file_type.split('/').pop()}</>}
                    </span>
                  </div>
                  <div className="cm-sf-actions">
                    {canViewInline(file.file_type) && (
                      <button
                        className="cm-sf-btn"
                        onClick={() => handleView(file)}
                        title="View"
                      >
                        View
                      </button>
                    )}
                    <button
                      className="cm-sf-btn"
                      onClick={() => handleDownload(file)}
                      disabled={downloading === file.id}
                      title="Download"
                    >
                      {downloading === file.id ? '...' : 'Download'}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Inline viewer modal */}
      {viewingFile && (
        <div className="cm-source-file-viewer-overlay" onClick={handleCloseViewer}>
          <div className="cm-source-file-viewer" onClick={e => e.stopPropagation()}>
            <div className="cm-sfv-header">
              <h3>{viewingFile.filename}</h3>
              <button className="cm-sfv-close" onClick={handleCloseViewer} aria-label="Close">&times;</button>
            </div>
            <div className="cm-sfv-body">
              {viewLoading ? (
                <p style={{ textAlign: 'center', padding: '2rem', color: '#888' }}>Loading...</p>
              ) : viewBlobUrl ? (
                viewingFile.file_type?.startsWith('image/') ? (
                  <img
                    src={viewBlobUrl}
                    alt={viewingFile.filename}
                    className="cm-sfv-image"
                  />
                ) : viewingFile.file_type === 'application/pdf' ? (
                  <iframe
                    src={viewBlobUrl}
                    title={viewingFile.filename}
                    className="cm-sfv-pdf"
                  />
                ) : null
              ) : (
                <p style={{ textAlign: 'center', padding: '2rem', color: '#c00' }}>Failed to load file.</p>
              )}
            </div>
            <div className="cm-sfv-footer">
              <button className="cm-action-btn" onClick={() => handleDownload(viewingFile)}>
                Download
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
