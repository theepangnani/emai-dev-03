import { useState, useRef } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { csvImportApi } from '../api/csvImport';
import type { TemplateInfo, CsvPreviewResult, CsvImportResult } from '../api/csvImport';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import './CsvImportPage.css';

type Step = 'select' | 'upload' | 'preview' | 'done';

export function CsvImportPage() {
  const [step, setStep] = useState<Step>('select');
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<CsvPreviewResult | null>(null);
  const [importResult, setImportResult] = useState<CsvImportResult | null>(null);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const templatesQuery = useQuery({
    queryKey: ['csvTemplates'],
    queryFn: csvImportApi.listTemplates,
  });

  const uploadMutation = useMutation({
    mutationFn: ({ templateType, csvFile, confirm }: { templateType: string; csvFile: File; confirm: boolean }) =>
      csvImportApi.uploadCsv(templateType, csvFile, confirm),
    onSuccess: (data) => {
      setError('');
      if (data.preview) {
        setPreview(data);
        setStep('preview');
      } else {
        setImportResult(data);
        setStep('done');
      }
    },
    onError: (err: unknown) => {
      const axiosErr = err as { response?: { data?: { detail?: string | { message?: string; errors?: string[] } } } };
      const detail = axiosErr?.response?.data?.detail;
      if (typeof detail === 'string') {
        setError(detail);
      } else if (detail && typeof detail === 'object' && 'message' in detail) {
        setError(detail.message || 'Import failed');
      } else {
        setError('Failed to process CSV file');
      }
    },
  });

  const handleTemplateSelect = (type: string) => {
    setSelectedTemplate(type);
    setFile(null);
    setPreview(null);
    setImportResult(null);
    setError('');
    setStep('upload');
  };

  const handleDownload = (e: React.MouseEvent, type: string) => {
    e.stopPropagation();
    csvImportApi.downloadTemplate(type);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      setFile(selected);
      setError('');
    }
  };

  const handleUpload = () => {
    if (!file || !selectedTemplate) return;
    uploadMutation.mutate({ templateType: selectedTemplate, csvFile: file, confirm: false });
  };

  const handleConfirmImport = () => {
    if (!file || !selectedTemplate) return;
    uploadMutation.mutate({ templateType: selectedTemplate, csvFile: file, confirm: true });
  };

  const handleReset = () => {
    setStep('select');
    setSelectedTemplate(null);
    setFile(null);
    setPreview(null);
    setImportResult(null);
    setError('');
  };

  const stepLabels: Record<Step, string> = {
    select: '1. Select Template',
    upload: '2. Upload CSV',
    preview: '3. Preview',
    done: '4. Done',
  };

  const stepOrder: Step[] = ['select', 'upload', 'preview', 'done'];
  const currentIdx = stepOrder.indexOf(step);

  const templateDescriptions: Record<string, string> = {
    students: 'Import student names, emails, and grade levels',
    courses: 'Import course names, descriptions, and subjects',
    assignments: 'Import assignments linked to your courses',
  };

  return (
    <DashboardLayout>
      <div className="csv-import">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'CSV Import' },
        ]} />

        <h1 className="csv-import-title">Import Data</h1>
        <p className="csv-import-subtitle">
          Upload a CSV file to import students, courses, or assignments.
        </p>

        {/* Step indicator */}
        <div className="csv-import-steps">
          {stepOrder.map((s, i) => (
            <div
              key={s}
              className={`csv-import-step${i === currentIdx ? ' active' : ''}${i < currentIdx ? ' done' : ''}`}
            >
              {stepLabels[s]}
            </div>
          ))}
        </div>

        {error && (
          <div className="csv-import-errors">
            <h4>Error</h4>
            <ul><li>{error}</li></ul>
          </div>
        )}

        {/* Step 1: Select template */}
        {step === 'select' && (
          <div className="csv-import-templates">
            {(templatesQuery.data || []).map((t: TemplateInfo) => (
              <div
                key={t.type}
                className={`csv-import-template-card${selectedTemplate === t.type ? ' selected' : ''}`}
                onClick={() => handleTemplateSelect(t.type)}
              >
                <h3>{t.type}</h3>
                <p>{templateDescriptions[t.type] || `Import ${t.type}`}</p>
                <p>
                  Columns: {t.columns.map((c) => c.name).join(', ')}
                </p>
                <button
                  className="csv-import-download-btn"
                  onClick={(e) => handleDownload(e, t.type)}
                >
                  Download blank template
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Step 2: Upload */}
        {step === 'upload' && (
          <>
            <div className="csv-import-upload">
              <p>Upload your filled <strong>{selectedTemplate}</strong> CSV file</p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileChange}
              />
              <button
                className="csv-import-upload-btn"
                onClick={() => fileInputRef.current?.click()}
              >
                Choose CSV File
              </button>
              {file && <div className="csv-import-file-name">{file.name}</div>}
            </div>
            <div className="csv-import-actions">
              <button onClick={handleReset}>Back</button>
              <button
                className="primary"
                disabled={!file || uploadMutation.isPending}
                onClick={handleUpload}
              >
                {uploadMutation.isPending ? 'Processing...' : 'Preview'}
              </button>
            </div>
          </>
        )}

        {/* Step 3: Preview */}
        {step === 'preview' && preview && (
          <>
            <div className="csv-import-preview">
              <h3>Preview</h3>
              <p className="csv-import-preview-summary">
                {preview.valid} valid row{preview.valid !== 1 ? 's' : ''} of {preview.total} total
              </p>

              {preview.errors.length > 0 && (
                <div className="csv-import-errors">
                  <h4>Validation Errors</h4>
                  <ul>
                    {preview.errors.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                </div>
              )}

              {preview.rows.length > 0 && (
                <div className="csv-import-table-wrap">
                  <table className="csv-import-table">
                    <thead>
                      <tr>
                        {Object.keys(preview.rows[0]).map((col) => (
                          <th key={col}>{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {preview.rows.slice(0, 50).map((row, i) => (
                        <tr key={i}>
                          {Object.values(row).map((val, j) => (
                            <td key={j}>{val || '-'}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {preview.rows.length > 50 && (
                    <p className="csv-import-preview-summary" style={{ padding: '0.5rem 0.75rem' }}>
                      Showing first 50 of {preview.rows.length} rows
                    </p>
                  )}
                </div>
              )}
            </div>
            <div className="csv-import-actions">
              <button onClick={() => { setStep('upload'); setPreview(null); }}>Back</button>
              <button
                className="primary"
                disabled={preview.valid === 0 || preview.errors.length > 0 || uploadMutation.isPending}
                onClick={handleConfirmImport}
              >
                {uploadMutation.isPending ? 'Importing...' : `Import ${preview.valid} Row${preview.valid !== 1 ? 's' : ''}`}
              </button>
            </div>
          </>
        )}

        {/* Step 4: Done */}
        {step === 'done' && importResult && (
          <>
            <div className="csv-import-success">
              <h3>Import Complete</h3>
              <p>
                Created: {importResult.created}
                {importResult.skipped > 0 && ` | Skipped (duplicates): ${importResult.skipped}`}
              </p>
              {importResult.errors.length > 0 && (
                <div className="csv-import-errors" style={{ marginTop: '0.75rem', textAlign: 'left' }}>
                  <h4>Some rows had errors</h4>
                  <ul>
                    {importResult.errors.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            <div className="csv-import-actions">
              <button onClick={handleReset}>Import More</button>
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
