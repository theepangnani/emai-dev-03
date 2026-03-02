import { useState, useRef, useCallback } from 'react';
import { classroomImportApi } from '../api/classroomImport';
import './CSVImporter.css';

interface CSVImporterProps {
  studentId?: number;
  onSessionCreated: (sessionId: number) => void;
  onCancel?: () => void;
}

type TemplateType = 'assignments' | 'materials' | 'grades';

interface TemplateInfo {
  label: string;
  description: string;
  columns: string[];
  rows: string[][];
}

const TEMPLATES: Record<TemplateType, TemplateInfo> = {
  assignments: {
    label: 'Assignments',
    description:
      'Import homework, projects, and other assignments with due dates and point values.',
    columns: ['Course Name', 'Assignment Title', 'Description', 'Due Date', 'Points', 'Status'],
    rows: [
      ['Grade 10 Math', 'Unit 5 Review', 'Review ch 10-12', '2026-03-15', '100', 'assigned'],
      ['Grade 10 Science', 'Lab Report 4', 'Photosynthesis experiment', '2026-03-20', '50', 'assigned'],
    ],
  },
  materials: {
    label: 'Materials',
    description:
      'Import course materials such as notes, readings, and resource links.',
    columns: ['Course Name', 'Material Title', 'Description', 'Type', 'URL'],
    rows: [
      ['Grade 10 Math', 'Chapter 10 Notes', 'Linear equations intro', 'notes', ''],
      ['Grade 10 Science', 'Lab Safety Guide', 'Required reading before labs', 'readings', 'https://example.com/safety'],
    ],
  },
  grades: {
    label: 'Grades',
    description:
      'Import scores for completed assignments to track academic progress.',
    columns: ['Course Name', 'Assignment Title', 'Score', 'Max Score'],
    rows: [
      ['Grade 10 Math', 'Quiz 3', '85', '100'],
      ['Grade 10 Science', 'Midterm Exam', '42', '50'],
    ],
  },
};

const TEMPLATE_TABS: TemplateType[] = ['assignments', 'materials', 'grades'];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function CSVImporter({ studentId, onSessionCreated, onCancel }: CSVImporterProps) {
  const [selectedTab, setSelectedTab] = useState<TemplateType>('assignments');
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const template = TEMPLATES[selectedTab];

  const handleDownloadTemplate = useCallback(async () => {
    try {
      const response = await classroomImportApi.downloadCSVTemplate(selectedTab);
      const blob = new Blob([response.data], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${selectedTab}_template.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch {
      setError('Failed to download template. Please try again.');
    }
  }, [selectedTab]);

  const handleFileChange = useCallback((selectedFile: File | null) => {
    setError('');
    if (selectedFile) {
      const ext = selectedFile.name.split('.').pop()?.toLowerCase();
      if (ext !== 'csv' && ext !== 'tsv') {
        setError('Please select a .csv or .tsv file.');
        return;
      }
    }
    setFile(selectedFile);
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] || null;
    handleFileChange(selected);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files?.[0] || null;
    handleFileChange(dropped);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  };

  const handleImport = async () => {
    if (!file) return;
    setLoading(true);
    setError('');
    try {
      const response = await classroomImportApi.importCSV(file, selectedTab, studentId);
      onSessionCreated(response.data.session_id);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'Failed to import CSV. Please check the file format and try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    onCancel?.();
  };

  return (
    <div className="csv-importer">
      {/* Header */}
      <div className="csvi-header">
        <h3 className="csvi-title">Import from CSV</h3>
        <p className="csvi-description">
          Download a template, fill it in with your classroom data, and upload it back.
        </p>
      </div>

      {/* Template selector tabs */}
      <div className="csvi-tabs">
        {TEMPLATE_TABS.map((tab) => (
          <button
            key={tab}
            className={`csvi-tab${selectedTab === tab ? ' active' : ''}`}
            onClick={() => setSelectedTab(tab)}
            type="button"
          >
            {TEMPLATES[tab].label}
          </button>
        ))}
      </div>

      {/* Template details */}
      <div className="csvi-template-panel">
        <p className="csvi-template-desc">{template.description}</p>

        {/* Preview table */}
        <div className="csvi-preview-wrapper">
          <table className="csvi-preview-table">
            <thead>
              <tr>
                {template.columns.map((col) => (
                  <th key={col}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {template.rows.map((row, rowIdx) => (
                <tr key={rowIdx}>
                  {row.map((cell, cellIdx) => (
                    <td key={cellIdx}>{cell || <span className="csvi-empty-cell">(empty)</span>}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Download template button */}
        <button
          className="csvi-download-btn"
          onClick={handleDownloadTemplate}
          type="button"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M8 1v10M8 11L4.5 7.5M8 11l3.5-3.5M2 13h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Download Template
        </button>
      </div>

      {/* File upload area */}
      <div
        className={`csvi-drop-zone${dragOver ? ' drag-over' : ''}${file ? ' has-file' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            fileInputRef.current?.click();
          }
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.tsv"
          style={{ display: 'none' }}
          onChange={handleInputChange}
        />
        {file ? (
          <div className="csvi-file-info">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="csvi-file-icon">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <div className="csvi-file-details">
              <span className="csvi-file-name">{file.name}</span>
              <span className="csvi-file-size">{formatFileSize(file.size)}</span>
            </div>
            <button
              className="csvi-file-remove"
              onClick={(e) => {
                e.stopPropagation();
                setFile(null);
                if (fileInputRef.current) fileInputRef.current.value = '';
              }}
              type="button"
              aria-label="Remove file"
            >
              x
            </button>
          </div>
        ) : (
          <div className="csvi-drop-content">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" className="csvi-upload-icon">
              <path d="M16 22V8M16 8l-5 5M16 8l5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M6 20v4a2 2 0 002 2h16a2 2 0 002-2v-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <p className="csvi-drop-text">Drop your filled CSV here, or click to browse</p>
            <span className="csvi-drop-hint">Accepts .csv and .tsv files</span>
          </div>
        )}
      </div>

      {/* Error message */}
      {error && <div className="csvi-error">{error}</div>}

      {/* Action buttons */}
      <div className="csvi-actions">
        <button className="cancel-btn" onClick={handleCancel} type="button" disabled={loading}>
          Cancel
        </button>
        <button
          className="generate-btn"
          onClick={handleImport}
          type="button"
          disabled={!file || loading}
        >
          {loading ? (
            <span className="csvi-loading">
              <span className="csvi-spinner" />
              Parsing CSV...
            </span>
          ) : (
            'Import CSV'
          )}
        </button>
      </div>
    </div>
  );
}
