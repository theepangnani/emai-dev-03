import { useState, useRef, useEffect } from 'react';
import { csvImportApi } from '../api/csvImport';
import type { CSVTemplateType, CSVImportResult } from '../api/csvImport';
import { useFocusTrap } from '../hooks/useFocusTrap';
import './CSVImportModal.css';

interface CSVImportModalProps {
  open: boolean;
  onClose: () => void;
  onImported?: () => void;
}

const TEMPLATE_OPTIONS: { value: CSVTemplateType; label: string }[] = [
  { value: 'courses', label: 'Courses' },
  { value: 'students', label: 'Students' },
  { value: 'assignments', label: 'Assignments' },
];

export default function CSVImportModal({ open, onClose, onImported }: CSVImportModalProps) {
  const [templateType, setTemplateType] = useState<CSVTemplateType>('courses');
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string[][]>([]);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<CSVImportResult | null>(null);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const modalRef = useFocusTrap<HTMLDivElement>(open);
  const prevOpenRef = useRef(false);

  useEffect(() => {
    const wasOpen = prevOpenRef.current;
    prevOpenRef.current = open;
    if (!open || wasOpen) return;
    setTemplateType('courses');
    setFile(null);
    setPreview([]);
    setImporting(false);
    setResult(null);
    setError('');
  }, [open]);

  if (!open) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null;
    setFile(selected);
    setResult(null);
    setError('');

    if (selected) {
      const reader = new FileReader();
      reader.onload = (ev) => {
        const text = ev.target?.result as string;
        const lines = text.split('\n').filter((l) => l.trim());
        const rows = lines.slice(0, 6).map((line) => {
          // Simple CSV split (handles basic cases)
          const result: string[] = [];
          let current = '';
          let inQuotes = false;
          for (const ch of line) {
            if (ch === '"') { inQuotes = !inQuotes; continue; }
            if (ch === ',' && !inQuotes) { result.push(current.trim()); current = ''; continue; }
            current += ch;
          }
          result.push(current.trim());
          return result;
        });
        setPreview(rows);
      };
      reader.readAsText(selected);
    } else {
      setPreview([]);
    }
  };

  const handleDownloadTemplate = async () => {
    try {
      const blob = await csvImportApi.downloadTemplate(templateType);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${templateType}_template.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError('Failed to download template');
    }
  };

  const handleImport = async () => {
    if (!file) return;
    setImporting(true);
    setError('');
    setResult(null);
    try {
      const res = await csvImportApi.uploadCSV(templateType, file);
      setResult(res);
      if (res.imported > 0) {
        onImported?.();
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Import failed';
      setError(msg);
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal modal-lg"
        role="dialog"
        aria-modal="true"
        aria-label="Import CSV"
        ref={modalRef}
        onClick={(e) => e.stopPropagation()}
      >
        <h2>Import CSV</h2>

        <div className="csv-import-field">
          <label htmlFor="csv-template-type">Template Type</label>
          <select
            id="csv-template-type"
            value={templateType}
            onChange={(e) => {
              setTemplateType(e.target.value as CSVTemplateType);
              setFile(null);
              setPreview([]);
              setResult(null);
              setError('');
              if (fileInputRef.current) fileInputRef.current.value = '';
            }}
          >
            {TEMPLATE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        <div className="csv-import-actions">
          <button type="button" className="btn btn-secondary" onClick={handleDownloadTemplate}>
            Download Template
          </button>
        </div>

        <div className="csv-import-field">
          <label htmlFor="csv-file-input">Upload CSV File</label>
          <input
            id="csv-file-input"
            ref={fileInputRef}
            type="file"
            accept=".csv"
            onChange={handleFileChange}
          />
        </div>

        {preview.length > 0 && (
          <div className="csv-import-preview">
            <h4>Preview (first 5 rows)</h4>
            <div className="csv-import-table-wrapper">
              <table className="csv-import-table">
                <thead>
                  <tr>
                    {preview[0].map((header, i) => (
                      <th key={i}>{header}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.slice(1).map((row, ri) => (
                    <tr key={ri}>
                      {row.map((cell, ci) => (
                        <td key={ci}>{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {error && <p className="csv-import-error">{error}</p>}

        {result && (
          <div className="csv-import-result">
            <p className="csv-import-success">
              Successfully imported {result.imported} {templateType}.
            </p>
            {result.errors.length > 0 && (
              <div className="csv-import-row-errors">
                <h4>Errors ({result.errors.length})</h4>
                <ul>
                  {result.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <div className="modal-buttons">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!file || importing}
            onClick={handleImport}
          >
            {importing ? 'Importing...' : 'Import'}
          </button>
        </div>
      </div>
    </div>
  );
}
