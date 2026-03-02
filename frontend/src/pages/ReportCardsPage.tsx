import { useState, useEffect, useCallback, useRef } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { useAuth } from '../context/AuthContext';
import { parentApi } from '../api/parent';
import type { ChildSummary } from '../api/parent';
import { reportCardsApi } from '../api/reportCards';
import type { ReportCardSummary, ReportCardDetail, MarkItem } from '../api/reportCards';
import './ReportCardsPage.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function percentageToLetter(pct: number): string {
  if (pct >= 90) return 'A';
  if (pct >= 80) return 'B';
  if (pct >= 70) return 'C';
  if (pct >= 60) return 'D';
  return 'F';
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
}

function gradeColor(pct: number): string {
  if (pct >= 80) return 'green';
  if (pct >= 60) return 'amber';
  return 'red';
}

// ---------------------------------------------------------------------------
// Upload Modal
// ---------------------------------------------------------------------------

interface UploadModalProps {
  open: boolean;
  studentId: number;
  studentName: string;
  onClose: () => void;
  onSuccess: () => void;
}

const MAX_FILE_BYTES = 10 * 1024 * 1024; // 10 MB
const ALLOWED_TYPES = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png'];

function UploadReportCardModal({ open, studentId, studentName, onClose, onSuccess }: UploadModalProps) {
  const [term, setTerm] = useState('');
  const [academicYear, setAcademicYear] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setTerm('');
    setAcademicYear('');
    setFile(null);
    setError('');
    setUploading(false);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const validateFile = (f: File): string => {
    if (!ALLOWED_TYPES.includes(f.type) && !f.name.match(/\.(pdf|jpg|jpeg|png)$/i)) {
      return 'Only PDF, JPG, and PNG files are allowed.';
    }
    if (f.size > MAX_FILE_BYTES) {
      return `File is too large (${(f.size / 1024 / 1024).toFixed(1)} MB). Maximum is 10 MB.`;
    }
    return '';
  };

  const handleFile = (f: File) => {
    const err = validateFile(f);
    if (err) { setError(err); return; }
    setError('');
    setFile(f);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFile(dropped);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) { setError('Please select a file.'); return; }
    if (!term.trim()) { setError('Please enter the term.'); return; }
    setUploading(true);
    setError('');
    try {
      await reportCardsApi.upload({
        student_id: studentId,
        term: term.trim(),
        academic_year: academicYear.trim() || undefined,
        file,
      });
      reset();
      onSuccess();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Upload failed. Please try again.');
      setUploading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Upload Report Card" onClick={handleClose}>
      <div className="modal-content rc-upload-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Upload Report Card</h2>
          <button className="modal-close-btn" onClick={handleClose} aria-label="Close">&times;</button>
        </div>
        <p className="rc-upload-subtitle">For: <strong>{studentName}</strong></p>
        <form onSubmit={handleSubmit} noValidate>
          {/* Drop zone */}
          <div
            className={`rc-dropzone${dragOver ? ' dragover' : ''}${file ? ' has-file' : ''}`}
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={e => e.key === 'Enter' && fileInputRef.current?.click()}
            aria-label="Drop zone for report card file"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
              onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])}
              style={{ display: 'none' }}
            />
            {file ? (
              <div className="rc-dropzone-file">
                <span className="rc-dropzone-file-icon">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                  </svg>
                </span>
                <span className="rc-dropzone-filename">{file.name}</span>
                <span className="rc-dropzone-size">({(file.size / 1024).toFixed(0)} KB)</span>
              </div>
            ) : (
              <div className="rc-dropzone-placeholder">
                <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
                <p>Drop PDF, JPG, or PNG here</p>
                <span>or click to browse (max 10 MB)</span>
              </div>
            )}
          </div>

          <div className="rc-form-row">
            <label htmlFor="rc-term">Term <span aria-hidden="true">*</span></label>
            <input
              id="rc-term"
              type="text"
              value={term}
              onChange={e => setTerm(e.target.value)}
              placeholder="e.g. Fall 2025, Semester 1 2025"
              required
              maxLength={50}
            />
          </div>
          <div className="rc-form-row">
            <label htmlFor="rc-year">Academic Year</label>
            <input
              id="rc-year"
              type="text"
              value={academicYear}
              onChange={e => setAcademicYear(e.target.value)}
              placeholder="e.g. 2025-2026"
              maxLength={20}
            />
          </div>

          {error && <p className="rc-error" role="alert">{error}</p>}

          <div className="rc-modal-actions">
            <button type="button" className="btn-secondary" onClick={handleClose} disabled={uploading}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={uploading || !file || !term.trim()}>
              {uploading ? 'Uploading & Analysing...' : 'Upload'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail Modal
// ---------------------------------------------------------------------------

interface DetailModalProps {
  reportCard: ReportCardDetail | null;
  onClose: () => void;
  allCards: ReportCardSummary[];
}

function renderMarkdown(text: string): string {
  // Minimal markdown: bold, headers, paragraphs, line breaks
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/### (.+)/g, '<h3>$1</h3>')
    .replace(/## (.+)/g, '<h2>$1</h2>')
    .replace(/# (.+)/g, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>')
    .replace(/^/, '<p>')
    .replace(/$/, '</p>');
}

function TrendIndicator({ cards, studentId }: { cards: ReportCardSummary[]; studentId: number }) {
  const studentCards = cards
    .filter(c => c.student_id === studentId && c.status === 'analyzed' && c.overall_average !== null)
    .sort((a, b) => new Date(a.uploaded_at).getTime() - new Date(b.uploaded_at).getTime());

  if (studentCards.length < 2) return null;

  return (
    <div className="rc-trend">
      <h4>Term Trend</h4>
      <div className="rc-trend-list">
        {studentCards.map((c, i) => {
          const prev = i > 0 ? studentCards[i - 1].overall_average! : null;
          const curr = c.overall_average!;
          let arrow = '';
          let arrowClass = '';
          if (prev !== null) {
            if (curr > prev + 0.5) { arrow = ' \u2191'; arrowClass = 'up'; }
            else if (curr < prev - 0.5) { arrow = ' \u2193'; arrowClass = 'down'; }
            else { arrow = ' \u2192'; arrowClass = 'flat'; }
          }
          return (
            <span key={c.id} className="rc-trend-item">
              <span className="rc-trend-term">{c.term}</span>
              <span className="rc-trend-avg">{curr.toFixed(1)}%</span>
              {arrow && <span className={`rc-trend-arrow ${arrowClass}`} aria-label={arrowClass}>{arrow}</span>}
              {i < studentCards.length - 1 && <span className="rc-trend-sep"> &rarr; </span>}
            </span>
          );
        })}
      </div>
    </div>
  );
}

function DetailModal({ reportCard, onClose, allCards }: DetailModalProps) {
  if (!reportCard) return null;

  const marks: MarkItem[] = reportCard.extracted_marks ?? [];

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Report Card Detail" onClick={onClose}>
      <div className="modal-content rc-detail-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{reportCard.student_name ?? 'Report Card'} — {reportCard.term}</h2>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close">&times;</button>
        </div>

        {reportCard.academic_year && (
          <p className="rc-detail-year">Academic Year: {reportCard.academic_year}</p>
        )}

        {reportCard.status === 'processing' && (
          <div className="rc-status-banner processing">
            AI analysis is in progress. Please refresh in a moment.
          </div>
        )}
        {reportCard.status === 'failed' && (
          <div className="rc-status-banner failed">
            Analysis failed: {reportCard.error_message ?? 'Unknown error'}
          </div>
        )}

        {marks.length > 0 && (
          <section className="rc-marks-section">
            <h3>Marks</h3>
            <div className="rc-overall">
              Overall Average: <strong className={`rc-pct-chip ${gradeColor(reportCard.overall_average ?? 0)}`}>
                {reportCard.overall_average?.toFixed(1)}%
              </strong>
            </div>
            <div className="rc-table-wrap">
              <table className="rc-marks-table">
                <thead>
                  <tr>
                    <th>Subject</th>
                    <th>Mark</th>
                    <th>Max</th>
                    <th>%</th>
                    <th>Grade</th>
                  </tr>
                </thead>
                <tbody>
                  {marks.map((m, i) => {
                    const pct = m.percentage ?? (m.max_mark > 0 ? (m.mark / m.max_mark) * 100 : 0);
                    return (
                      <tr key={i}>
                        <td>{m.subject}</td>
                        <td>{m.mark}</td>
                        <td>{m.max_mark}</td>
                        <td>
                          <span className={`rc-pct-chip ${gradeColor(pct)}`}>
                            {pct.toFixed(1)}%
                          </span>
                        </td>
                        <td><span className={`rc-letter-badge ${gradeColor(pct)}`}>{percentageToLetter(pct)}</span></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {(reportCard.ai_strengths?.length ?? 0) > 0 || (reportCard.ai_improvement_areas?.length ?? 0) > 0 ? (
          <section className="rc-insights-section">
            {(reportCard.ai_strengths?.length ?? 0) > 0 && (
              <div className="rc-insights-col">
                <h4>Strengths</h4>
                <div className="rc-badge-list">
                  {reportCard.ai_strengths!.map((s, i) => (
                    <span key={i} className="rc-badge strength">{s}</span>
                  ))}
                </div>
              </div>
            )}
            {(reportCard.ai_improvement_areas?.length ?? 0) > 0 && (
              <div className="rc-insights-col">
                <h4>Areas for Improvement</h4>
                <div className="rc-badge-list">
                  {reportCard.ai_improvement_areas!.map((s, i) => (
                    <span key={i} className="rc-badge improvement">{s}</span>
                  ))}
                </div>
              </div>
            )}
          </section>
        ) : null}

        {reportCard.ai_observations && (
          <section className="rc-observations-section">
            <h3>AI Observations</h3>
            <div
              className="rc-observations-body"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(reportCard.ai_observations) }}
            />
          </section>
        )}

        <TrendIndicator cards={allCards} studentId={reportCard.student_id} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function ReportCardsPage() {
  const { user } = useAuth();
  const isParent = user?.role === 'parent';

  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null);
  const [reportCards, setReportCards] = useState<ReportCardSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [showUploadModal, setShowUploadModal] = useState(false);
  const [detailCard, setDetailCard] = useState<ReportCardDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Load children (parents only)
  useEffect(() => {
    if (!isParent) return;
    parentApi.getChildren()
      .then(kids => {
        setChildren(kids);
        if (kids.length > 0 && selectedStudentId === null) {
          setSelectedStudentId(kids[0].student_id);
        }
      })
      .catch(() => {});
  }, [isParent]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadCards = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = isParent && selectedStudentId ? { student_id: selectedStudentId } : {};
      const data = await reportCardsApi.list(params);
      setReportCards(data);
    } catch {
      setError('Failed to load report cards. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [isParent, selectedStudentId]);

  useEffect(() => {
    if (isParent && selectedStudentId === null) return;
    loadCards();
  }, [loadCards, isParent, selectedStudentId]);

  const handleCardClick = async (id: number) => {
    setDetailLoading(true);
    try {
      const detail = await reportCardsApi.get(id);
      setDetailCard(detail);
    } catch {
      setError('Failed to load report card details.');
    } finally {
      setDetailLoading(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    if (!window.confirm('Delete this report card? This cannot be undone.')) return;
    try {
      await reportCardsApi.delete(id);
      setReportCards(prev => prev.filter(c => c.id !== id));
      if (detailCard?.id === id) setDetailCard(null);
    } catch {
      setError('Failed to delete report card.');
    }
  };

  const selectedChild = children.find(c => c.student_id === selectedStudentId);

  const statusLabel = (status: string) => {
    switch (status) {
      case 'processing': return 'Processing';
      case 'analyzed': return 'Analysed';
      case 'failed': return 'Failed';
      default: return 'Uploaded';
    }
  };

  return (
    <DashboardLayout welcomeSubtitle="Report Cards & AI Analysis">
      <div className="rc-page">
        <div className="rc-page-header">
          <div className="rc-page-title-row">
            <h1 className="rc-page-title">Report Cards</h1>
            {isParent && selectedChild && (
              <button className="btn-primary rc-upload-btn" onClick={() => setShowUploadModal(true)}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
                Upload Report Card
              </button>
            )}
          </div>

          {/* Child selector pills */}
          {isParent && children.length > 0 && (
            <div className="rc-child-selector" role="group" aria-label="Select child">
              {children.map(child => (
                <button
                  key={child.student_id}
                  className={`rc-child-pill${selectedStudentId === child.student_id ? ' active' : ''}`}
                  onClick={() => setSelectedStudentId(child.student_id)}
                >
                  {child.full_name}
                </button>
              ))}
            </div>
          )}
        </div>

        {error && <p className="rc-error" role="alert">{error}</p>}

        {loading ? (
          <div className="rc-loading" aria-busy="true">
            {[1, 2, 3].map(i => <div key={i} className="rc-card-skeleton skeleton" />)}
          </div>
        ) : reportCards.length === 0 ? (
          <div className="rc-empty">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
            </svg>
            <p>No report cards uploaded yet.</p>
            {isParent && selectedChild && (
              <button className="btn-primary" onClick={() => setShowUploadModal(true)}>
                Upload First Report Card
              </button>
            )}
          </div>
        ) : (
          <div className="rc-grid">
            {reportCards.map(rc => (
              <div
                key={rc.id}
                className={`rc-card rc-status-${rc.status}`}
                onClick={() => handleCardClick(rc.id)}
                role="button"
                tabIndex={0}
                onKeyDown={e => e.key === 'Enter' && handleCardClick(rc.id)}
                aria-label={`Report card: ${rc.term}${rc.academic_year ? ', ' + rc.academic_year : ''}`}
              >
                <div className="rc-card-top">
                  <span className={`rc-status-chip status-${rc.status}`}>{statusLabel(rc.status)}</span>
                  {isParent && (
                    <button
                      className="rc-delete-btn"
                      onClick={e => handleDelete(e, rc.id)}
                      aria-label="Delete report card"
                      title="Delete"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                        <path d="M10 11v6M14 11v6"/>
                        <path d="M9 6V4h6v2"/>
                      </svg>
                    </button>
                  )}
                </div>
                <div className="rc-card-body">
                  <div className="rc-card-term">{rc.term}</div>
                  {rc.academic_year && <div className="rc-card-year">{rc.academic_year}</div>}
                  {rc.student_name && <div className="rc-card-student">{rc.student_name}</div>}
                  {rc.overall_average !== null && (
                    <div className={`rc-card-avg rc-pct-chip ${gradeColor(rc.overall_average)}`}>
                      {rc.overall_average.toFixed(1)}% avg
                    </div>
                  )}
                </div>
                <div className="rc-card-footer">
                  <span className="rc-card-date">{formatDate(rc.uploaded_at)}</span>
                  <span className="rc-card-filename" title={rc.file_name}>
                    {rc.file_name.length > 28 ? rc.file_name.slice(0, 25) + '...' : rc.file_name}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        {detailLoading && (
          <div className="modal-overlay" aria-busy="true">
            <div className="modal-content rc-loading-modal">Loading...</div>
          </div>
        )}
      </div>

      {/* Upload Modal */}
      {isParent && selectedChild && (
        <UploadReportCardModal
          open={showUploadModal}
          studentId={selectedChild.student_id}
          studentName={selectedChild.full_name}
          onClose={() => setShowUploadModal(false)}
          onSuccess={() => {
            setShowUploadModal(false);
            loadCards();
          }}
        />
      )}

      {/* Detail Modal */}
      <DetailModal
        reportCard={detailCard}
        onClose={() => setDetailCard(null)}
        allCards={reportCards}
      />
    </DashboardLayout>
  );
}
