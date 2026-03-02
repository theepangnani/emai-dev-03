import { useState, useRef, useCallback } from 'react';
import { classroomImportApi } from '../api/classroomImport';
import './ICSImporter.css';

interface ICSImporterProps {
  studentId?: number;
  onSessionCreated: (sessionId: number) => void;
  onCancel?: () => void;
}

const ACCEPTED_EXTENSIONS = ['.ics', '.ical'];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function isValidICSFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some(ext => name.endsWith(ext));
}

export function ICSImporter({ studentId, onSessionCreated, onCancel }: ICSImporterProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [showInstructions, setShowInstructions] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [dragging, setDragging] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = useCallback((file: File) => {
    setError('');
    if (!isValidICSFile(file)) {
      setError('Invalid file type. Please select a .ics or .ical file.');
      return;
    }
    setSelectedFile(file);
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
    // Reset input so the same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    setError('');
  };

  const handleImport = async () => {
    if (!selectedFile) return;

    setLoading(true);
    setError('');

    try {
      const response = await classroomImportApi.importICS(selectedFile, studentId);
      onSessionCreated(response.data.session_id);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'Failed to import calendar file. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ics-importer">
      {/* Header */}
      <div className="ics-header">
        <h3 className="ics-title">Import from Google Calendar</h3>
        <p className="ics-description">
          Google Classroom creates calendar events for assignment due dates.
          Export your calendar and upload the .ics file.
        </p>
      </div>

      {/* Collapsible instructions */}
      <div className="ics-instructions-section">
        <button
          className="ics-instructions-toggle"
          onClick={() => setShowInstructions(!showInstructions)}
          type="button"
        >
          <svg
            className={`ics-chevron${showInstructions ? ' open' : ''}`}
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
          >
            <path
              d="M6 4l4 4-4 4"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span>How to export from Google Calendar</span>
        </button>
        {showInstructions && (
          <ol className="ics-steps">
            <li>
              Go to Google Calendar (
              <a href="https://calendar.google.com" target="_blank" rel="noopener noreferrer">
                calendar.google.com
              </a>
              )
            </li>
            <li>Click the gear icon, then select <strong>Settings</strong></li>
            <li>Under <strong>Import &amp; export</strong>, click <strong>Export</strong></li>
            <li>Download the .ics file</li>
            <li>Upload it below</li>
          </ol>
        )}
      </div>

      {/* File upload area */}
      <div
        className={`ics-drop-zone${dragging ? ' dragging' : ''}${selectedFile ? ' has-file' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !selectedFile && fileInputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            if (!selectedFile) fileInputRef.current?.click();
          }
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".ics,.ical"
          style={{ display: 'none' }}
          onChange={handleInputChange}
        />

        {selectedFile ? (
          <div className="ics-file-selected">
            <svg className="ics-file-icon" width="32" height="32" viewBox="0 0 24 24" fill="none">
              <rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" strokeWidth="1.5" />
              <path d="M3 10h18" stroke="currentColor" strokeWidth="1.5" />
              <path d="M8 4V2M16 4V2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              <path d="M7 14h2M11 14h2M15 14h2M7 17h2M11 17h2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <div className="ics-file-info">
              <span className="ics-file-name">{selectedFile.name}</span>
              <span className="ics-file-size">{formatFileSize(selectedFile.size)}</span>
            </div>
            <button
              className="ics-file-remove"
              onClick={(e) => {
                e.stopPropagation();
                handleRemoveFile();
              }}
              type="button"
              aria-label="Remove file"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        ) : (
          <div className="ics-drop-content">
            <svg className="ics-calendar-icon" width="40" height="40" viewBox="0 0 24 24" fill="none">
              <rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" strokeWidth="1.5" />
              <path d="M3 10h18" stroke="currentColor" strokeWidth="1.5" />
              <path d="M8 4V2M16 4V2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              <path d="M7 14h2M11 14h2M15 14h2M7 17h2M11 17h2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <p className="ics-drop-text">Drop your .ics file here, or click to browse</p>
            <p className="ics-drop-hint">Accepts .ics and .ical files</p>
          </div>
        )}
      </div>

      {/* Error message */}
      {error && <div className="ics-error">{error}</div>}

      {/* Limitation notice */}
      <div className="ics-info-box">
        <svg className="ics-info-icon" width="18" height="18" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.5" />
          <path d="M12 8v0M12 12v4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <p>
          <strong>Note:</strong> Calendar import captures assignment titles and due dates only.
          Descriptions, materials, and grades are not included. Use Copy &amp; Paste or
          Screenshot import for complete data.
        </p>
      </div>

      {/* Action buttons */}
      <div className="ics-actions">
        {onCancel && (
          <button
            className="ics-btn-cancel"
            onClick={onCancel}
            type="button"
            disabled={loading}
          >
            Cancel
          </button>
        )}
        <button
          className="ics-btn-import"
          onClick={handleImport}
          disabled={!selectedFile || loading}
          type="button"
        >
          {loading ? (
            <>
              <span className="ics-spinner" />
              Parsing calendar...
            </>
          ) : (
            'Import Calendar'
          )}
        </button>
      </div>
    </div>
  );
}
