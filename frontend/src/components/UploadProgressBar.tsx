import { useState, useEffect, useRef } from 'react';
import './UploadProgressBar.css';

export type UploadStatus = 'uploading' | 'complete' | 'error' | 'cancelled';

export interface UploadProgressBarProps {
  /** File name to display */
  fileName: string;
  /** File size in bytes */
  fileSize: number;
  /** Upload progress percentage (0-100) */
  progress: number;
  /** Current status */
  status: UploadStatus;
  /** Error message when status is 'error' */
  errorMessage?: string;
  /** Called when the user clicks cancel */
  onCancel?: () => void;
  /** Called when the user clicks retry after an error */
  onRetry?: () => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatTimeRemaining(seconds: number): string {
  if (seconds < 1) return 'finishing...';
  if (seconds < 60) return `${Math.ceil(seconds)}s remaining`;
  const min = Math.floor(seconds / 60);
  const sec = Math.ceil(seconds % 60);
  return `${min}m ${sec}s remaining`;
}

export function UploadProgressBar({
  fileName,
  fileSize,
  progress,
  status,
  errorMessage,
  onCancel,
  onRetry,
}: UploadProgressBarProps) {
  const [etaText, setEtaText] = useState('calculating...');
  const startTimeRef = useRef<number>(0);

  // Track ETA via an interval timer while uploading
  useEffect(() => {
    if (status !== 'uploading') {
      startTimeRef.current = 0;
      return;
    }

    if (startTimeRef.current === 0) {
      startTimeRef.current = performance.now();
    }

    const timer = setInterval(() => {
      if (progress <= 0) {
        setEtaText('calculating...');
        return;
      }
      const elapsed = (performance.now() - startTimeRef.current) / 1000;
      if (elapsed < 1) {
        setEtaText('calculating...');
        return;
      }
      const rate = progress / elapsed;
      if (rate <= 0) {
        setEtaText('calculating...');
        return;
      }
      const remaining = (100 - progress) / rate;
      setEtaText(formatTimeRemaining(remaining));
    }, 1000);

    return () => clearInterval(timer);
  }, [status, progress]);

  const clampedProgress = Math.min(100, Math.max(0, progress));

  return (
    <div className={`upload-progress-bar upload-progress-bar--${status}`}>
      <div className="upload-progress-bar__header">
        <div className="upload-progress-bar__file-info">
          <span className="upload-progress-bar__file-icon">
            {status === 'complete' ? '\u2705' : status === 'error' ? '\u274C' : status === 'cancelled' ? '\u23F9' : '\uD83D\uDCC4'}
          </span>
          <div className="upload-progress-bar__file-details">
            <span className="upload-progress-bar__file-name" title={fileName}>
              {fileName}
            </span>
            <span className="upload-progress-bar__file-size">
              {formatFileSize(fileSize)}
            </span>
          </div>
        </div>
        <div className="upload-progress-bar__actions">
          {status === 'uploading' && onCancel && (
            <button
              className="upload-progress-bar__cancel-btn"
              onClick={onCancel}
              title="Cancel upload"
              type="button"
            >
              Cancel
            </button>
          )}
          {status === 'error' && onRetry && (
            <button
              className="upload-progress-bar__retry-btn"
              onClick={onRetry}
              title="Retry upload"
              type="button"
            >
              Retry
            </button>
          )}
        </div>
      </div>

      <div className="upload-progress-bar__track">
        <div
          className="upload-progress-bar__fill"
          style={{ width: `${clampedProgress}%` }}
        />
      </div>

      <div className="upload-progress-bar__footer">
        {status === 'uploading' && (
          <>
            <span className="upload-progress-bar__percent">{clampedProgress}%</span>
            <span className="upload-progress-bar__eta">{etaText}</span>
          </>
        )}
        {status === 'complete' && (
          <span className="upload-progress-bar__status-text">Upload complete</span>
        )}
        {status === 'error' && (
          <span className="upload-progress-bar__status-text upload-progress-bar__status-text--error">
            {errorMessage || 'Upload failed'}
          </span>
        )}
        {status === 'cancelled' && (
          <span className="upload-progress-bar__status-text">Upload cancelled</span>
        )}
      </div>
    </div>
  );
}
