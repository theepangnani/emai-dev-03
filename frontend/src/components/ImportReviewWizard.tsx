import { useState, useEffect, useCallback, useRef } from 'react';
import {
  classroomImportApi,
  type ImportSession,
  type ParsedImportData,
  type ParsedCourse,
  type ParsedAssignment,
  type ParsedMaterial,
  type ParsedAnnouncement,
  type ParsedGrade,
  type ImportCommitResult,
} from '../api/classroomImport';
import './ImportReviewWizard.css';

// ---------------------------------------------------------------------------
// Props & types
// ---------------------------------------------------------------------------

export interface ImportReviewWizardProps {
  sessionId: number;
  onComplete: () => void;
  onCancel: () => void;
}

type WizardStep = 'processing' | 'review' | 'confirm' | 'summary';

type ReviewTab = 'courses' | 'assignments' | 'materials' | 'announcements' | 'grades';

const STEP_LABELS: { key: WizardStep; label: string }[] = [
  { key: 'processing', label: 'Processing' },
  { key: 'review', label: 'Review' },
  { key: 'confirm', label: 'Confirm' },
  { key: 'summary', label: 'Summary' },
];

const TAB_LABELS: { key: ReviewTab; label: string }[] = [
  { key: 'courses', label: 'Courses' },
  { key: 'assignments', label: 'Assignments' },
  { key: 'materials', label: 'Materials' },
  { key: 'announcements', label: 'Announcements' },
  { key: 'grades', label: 'Grades' },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function generateId(): string {
  return Math.random().toString(36).slice(2, 10);
}

/** Ensure every item has an _id and _included flag. */
function normalizeData(data: ParsedImportData): ParsedImportData {
  const norm = <T extends { _id?: string; _included?: boolean }>(arr: T[]): T[] =>
    arr.map((item) => ({
      ...item,
      _id: item._id || generateId(),
      _included: item._included !== false,
    }));

  return {
    courses: norm(data.courses),
    assignments: norm(data.assignments),
    materials: norm(data.materials),
    announcements: norm(data.announcements),
    grades: norm(data.grades),
  };
}

// ---------------------------------------------------------------------------
// Inline editable cell
// ---------------------------------------------------------------------------

interface EditableCellProps {
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
  type?: 'text' | 'number' | 'date';
}

function EditableCell({ value, onChange, readOnly, type = 'text' }: EditableCellProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  if (readOnly || !editing) {
    return (
      <span
        className={`irw-cell-value${readOnly ? '' : ' irw-cell-editable'}`}
        onClick={() => !readOnly && setEditing(true)}
        title={readOnly ? undefined : 'Click to edit'}
      >
        {value || '\u2014'}
      </span>
    );
  }

  const commit = () => {
    setEditing(false);
    if (draft !== value) onChange(draft);
  };

  return (
    <input
      ref={inputRef}
      className="irw-cell-input"
      type={type}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === 'Enter') commit();
        if (e.key === 'Escape') {
          setDraft(value);
          setEditing(false);
        }
      }}
    />
  );
}

// ---------------------------------------------------------------------------
// DuplicateBadge
// ---------------------------------------------------------------------------

function DuplicateBadge({ isDuplicate }: { isDuplicate?: boolean }) {
  if (!isDuplicate) return null;
  return <span className="irw-badge-duplicate">Duplicate</span>;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ImportReviewWizard({ sessionId, onComplete, onCancel }: ImportReviewWizardProps) {
  const [step, setStep] = useState<WizardStep>('processing');
  const [session, setSession] = useState<ImportSession | null>(null);
  const [data, setData] = useState<ParsedImportData | null>(null);
  const [activeTab, setActiveTab] = useState<ReviewTab>('courses');
  const [error, setError] = useState<string | null>(null);
  const [commitResult, setCommitResult] = useState<ImportCommitResult | null>(null);
  const [committing, setCommitting] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Step 1: Poll for processing completion ─────────────────────────────

  const pollSession = useCallback(async () => {
    try {
      const sess = await classroomImportApi.getSession(sessionId);
      setSession(sess);

      if (sess.status === 'ready_for_review' && sess.parsed_data) {
        // Stop polling and move to review
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
        const normalized = normalizeData(sess.parsed_data);
        setData(normalized);

        // Auto-select the first non-empty tab
        const tabOrder: ReviewTab[] = ['courses', 'assignments', 'materials', 'announcements', 'grades'];
        for (const tab of tabOrder) {
          if (normalized[tab].length > 0) {
            setActiveTab(tab);
            break;
          }
        }

        setStep('review');
      } else if (sess.status === 'failed') {
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
        setError(sess.error_message || 'Import processing failed. Please try again.');
      }
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'Failed to fetch import session.');
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }
  }, [sessionId]);

  useEffect(() => {
    // Initial fetch
    pollSession();
    // Start polling every 2 seconds
    pollRef.current = setInterval(pollSession, 2000);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [pollSession]);

  // ── Data editing helpers ───────────────────────────────────────────────

  const updateItem = <K extends keyof ParsedImportData>(
    category: K,
    itemId: string,
    field: string,
    value: unknown,
  ) => {
    if (!data) return;
    setData({
      ...data,
      [category]: (data[category] as Array<{ _id?: string }>).map((item) =>
        item._id === itemId ? { ...item, [field]: value } : item,
      ),
    });
  };

  const toggleItem = (category: keyof ParsedImportData, itemId: string) => {
    if (!data) return;
    setData({
      ...data,
      [category]: (data[category] as Array<{ _id?: string; _included?: boolean }>).map((item) =>
        item._id === itemId ? { ...item, _included: !item._included } : item,
      ),
    });
  };

  const toggleAll = (category: keyof ParsedImportData, included: boolean) => {
    if (!data) return;
    setData({
      ...data,
      [category]: (data[category] as Array<{ _included?: boolean }>).map((item) => ({
        ...item,
        _included: included,
      })),
    });
  };

  // ── Counts ─────────────────────────────────────────────────────────────

  const getIncludedCount = (category: keyof ParsedImportData): number => {
    if (!data) return 0;
    return (data[category] as Array<{ _included?: boolean }>).filter((i) => i._included !== false).length;
  };

  const getTotalCount = (category: keyof ParsedImportData): number => {
    if (!data) return 0;
    return data[category].length;
  };

  // ── Step 3: Confirm & commit ───────────────────────────────────────────

  const handleCommit = async () => {
    if (!data) return;

    setCommitting(true);
    setError(null);

    try {
      // First, send the reviewed data
      await classroomImportApi.updateReviewedData(sessionId, data);
      // Then commit
      const result = await classroomImportApi.commitSession(sessionId);
      setCommitResult(result);
      setStep('summary');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'Failed to commit import. Please try again.');
    } finally {
      setCommitting(false);
    }
  };

  // ── Step indicator ─────────────────────────────────────────────────────

  const stepIndex = STEP_LABELS.findIndex((s) => s.key === step);

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="irw-overlay" onClick={onCancel}>
      <div className="irw-wizard" onClick={(e) => e.stopPropagation()}>
        {/* Header & step indicator */}
        <div className="irw-header">
          <h2 className="irw-title">Import Review</h2>
          <div className="irw-steps">
            {STEP_LABELS.map((s, i) => (
              <div key={s.key} className="irw-step-group">
                <div
                  className={`irw-step-dot${step === s.key ? ' active' : ''}${
                    i < stepIndex ? ' done' : ''
                  }`}
                >
                  {i < stepIndex ? '\u2713' : i + 1}
                </div>
                <span
                  className={`irw-step-label${step === s.key ? ' active' : ''}${
                    i < stepIndex ? ' done' : ''
                  }`}
                >
                  {s.label}
                </span>
                {i < STEP_LABELS.length - 1 && <div className="irw-step-connector" />}
              </div>
            ))}
          </div>
          <button className="irw-close-btn" onClick={onCancel} title="Cancel import">
            &times;
          </button>
        </div>

        {/* Global error */}
        {error && step !== 'summary' && (
          <div className="irw-error">{error}</div>
        )}

        {/* Step 1: Processing */}
        {step === 'processing' && (
          <div className="irw-content irw-processing">
            <div className="irw-spinner" />
            <h3>AI is analyzing your data...</h3>
            <p className="irw-processing-sub">
              This usually takes a few seconds. We are extracting courses, assignments, materials, and
              grades from your import.
            </p>
            <div className="irw-actions">
              <button className="cancel-btn" onClick={onCancel}>
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Review & Edit */}
        {step === 'review' && data && (
          <div className="irw-content">
            <p className="irw-description">
              Review the extracted data below. Click any cell to edit. Uncheck items you do not want to
              import.
            </p>

            {/* Tab navigation */}
            <div className="irw-tabs">
              {TAB_LABELS.map((tab) => {
                const count = getTotalCount(tab.key);
                return (
                  <button
                    key={tab.key}
                    className={`irw-tab${activeTab === tab.key ? ' active' : ''}${
                      count === 0 ? ' empty' : ''
                    }`}
                    onClick={() => setActiveTab(tab.key)}
                  >
                    {tab.label}
                    <span className="irw-tab-badge">{count}</span>
                  </button>
                );
              })}
            </div>

            {/* Select / deselect all */}
            <div className="irw-select-all">
              <button className="irw-link-btn" onClick={() => toggleAll(activeTab, true)}>
                Select All
              </button>
              <button className="irw-link-btn" onClick={() => toggleAll(activeTab, false)}>
                Deselect All
              </button>
              <span className="irw-selected-count">
                {getIncludedCount(activeTab)} of {getTotalCount(activeTab)} selected
              </span>
            </div>

            {/* Tables */}
            <div className="irw-table-wrapper">
              {activeTab === 'courses' && (
                <CoursesTable
                  items={data.courses}
                  onToggle={(id) => toggleItem('courses', id)}
                  onUpdate={(id, field, value) => updateItem('courses', id, field, value)}
                />
              )}
              {activeTab === 'assignments' && (
                <AssignmentsTable
                  items={data.assignments}
                  onToggle={(id) => toggleItem('assignments', id)}
                  onUpdate={(id, field, value) => updateItem('assignments', id, field, value)}
                />
              )}
              {activeTab === 'materials' && (
                <MaterialsTable
                  items={data.materials}
                  onToggle={(id) => toggleItem('materials', id)}
                  onUpdate={(id, field, value) => updateItem('materials', id, field, value)}
                />
              )}
              {activeTab === 'announcements' && (
                <AnnouncementsTable
                  items={data.announcements}
                  onToggle={(id) => toggleItem('announcements', id)}
                />
              )}
              {activeTab === 'grades' && (
                <GradesTable
                  items={data.grades}
                  onToggle={(id) => toggleItem('grades', id)}
                  onUpdate={(id, field, value) => updateItem('grades', id, field, value)}
                />
              )}
              {getTotalCount(activeTab) === 0 && (
                <div className="irw-empty-tab">No {activeTab} found in this import.</div>
              )}
            </div>

            <div className="irw-actions">
              <button className="cancel-btn" onClick={onCancel}>
                Cancel
              </button>
              <button className="generate-btn" onClick={() => setStep('confirm')}>
                Next: Confirm Import
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Confirm */}
        {step === 'confirm' && data && (
          <div className="irw-content irw-confirm">
            <h3>Confirm Import</h3>
            <p className="irw-description">
              The following items will be created in your account:
            </p>

            <div className="irw-confirm-summary">
              <SummaryRow label="Courses" count={getIncludedCount('courses')} />
              <SummaryRow label="Assignments" count={getIncludedCount('assignments')} />
              <SummaryRow label="Materials" count={getIncludedCount('materials')} />
              <SummaryRow label="Announcements" count={getIncludedCount('announcements')} />
              <SummaryRow label="Grades" count={getIncludedCount('grades')} />
            </div>

            {error && <div className="irw-error">{error}</div>}

            <div className="irw-actions">
              <button className="cancel-btn" onClick={() => setStep('review')}>
                Back to Review
              </button>
              <button
                className="generate-btn irw-import-btn"
                onClick={handleCommit}
                disabled={committing}
              >
                {committing ? 'Importing...' : 'Import Now'}
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Summary */}
        {step === 'summary' && commitResult && (
          <div className="irw-content irw-summary">
            <div className="irw-summary-header">
              <div className="irw-success-icon">&#10003;</div>
              <h3>Import Complete</h3>
            </div>

            <div className="irw-summary-stats">
              <StatBlock label="Courses" count={commitResult.courses_created} />
              <StatBlock label="Assignments" count={commitResult.assignments_created} />
              <StatBlock label="Materials" count={commitResult.materials_created} />
              <StatBlock label="Announcements" count={commitResult.announcements_created} />
              <StatBlock label="Grades" count={commitResult.grades_created} />
            </div>

            {commitResult.errors.length > 0 && (
              <div className="irw-summary-errors">
                <h4>Errors ({commitResult.errors.length})</h4>
                <ul>
                  {commitResult.errors.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="irw-actions irw-summary-actions">
              <button className="generate-btn" onClick={onComplete}>
                View Imported Data
              </button>
              <button className="cancel-btn" onClick={onCancel}>
                Import More
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components: Confirm summary row
// ---------------------------------------------------------------------------

function SummaryRow({ label, count }: { label: string; count: number }) {
  return (
    <div className="irw-confirm-row">
      <span className="irw-confirm-label">{label}</span>
      <span className={`irw-confirm-count${count > 0 ? ' has-items' : ''}`}>{count}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components: Summary stat block
// ---------------------------------------------------------------------------

function StatBlock({ label, count }: { label: string; count: number }) {
  return (
    <div className="irw-stat">
      <span className="irw-stat-number">{count}</span>
      <span className="irw-stat-label">{label}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components: Table renderers
// ---------------------------------------------------------------------------

interface TableProps<T> {
  items: T[];
  onToggle: (id: string) => void;
  onUpdate?: (id: string, field: string, value: string) => void;
}

function CoursesTable({ items, onToggle, onUpdate }: TableProps<ParsedCourse>) {
  return (
    <table className="irw-table">
      <thead>
        <tr>
          <th className="irw-th-check" />
          <th>Name</th>
          <th>Teacher</th>
          <th>Section</th>
          <th className="irw-th-status" />
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item._id} className={item._included === false ? 'irw-row-excluded' : ''}>
            <td>
              <input
                type="checkbox"
                checked={item._included !== false}
                onChange={() => onToggle(item._id!)}
              />
            </td>
            <td>
              <EditableCell
                value={item.name || ''}
                onChange={(v) => onUpdate?.(item._id!, 'name', v)}
              />
              <DuplicateBadge isDuplicate={item._is_duplicate} />
            </td>
            <td>
              <EditableCell
                value={item.teacher || ''}
                onChange={(v) => onUpdate?.(item._id!, 'teacher', v)}
              />
            </td>
            <td>
              <EditableCell
                value={item.section || ''}
                onChange={(v) => onUpdate?.(item._id!, 'section', v)}
              />
            </td>
            <td>
              <CourseMappingSelect
                value={item._course_mapping}
                onChange={(v) => onUpdate?.(item._id!, '_course_mapping', v)}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AssignmentsTable({ items, onToggle, onUpdate }: TableProps<ParsedAssignment>) {
  return (
    <table className="irw-table">
      <thead>
        <tr>
          <th className="irw-th-check" />
          <th>Title</th>
          <th>Course</th>
          <th>Due Date</th>
          <th>Points</th>
          <th>Status</th>
          <th className="irw-th-status" />
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item._id} className={item._included === false ? 'irw-row-excluded' : ''}>
            <td>
              <input
                type="checkbox"
                checked={item._included !== false}
                onChange={() => onToggle(item._id!)}
              />
            </td>
            <td>
              <EditableCell
                value={item.title || ''}
                onChange={(v) => onUpdate?.(item._id!, 'title', v)}
              />
              <DuplicateBadge isDuplicate={item._is_duplicate} />
            </td>
            <td>
              <EditableCell
                value={item.course || ''}
                onChange={(v) => onUpdate?.(item._id!, 'course', v)}
              />
            </td>
            <td>
              <EditableCell
                value={item.due_date || ''}
                onChange={(v) => onUpdate?.(item._id!, 'due_date', v)}
                type="date"
              />
            </td>
            <td>
              <EditableCell
                value={item.points != null ? String(item.points) : ''}
                onChange={(v) => onUpdate?.(item._id!, 'points', v)}
                type="number"
              />
            </td>
            <td>
              <EditableCell
                value={item.status || ''}
                onChange={(v) => onUpdate?.(item._id!, 'status', v)}
              />
            </td>
            <td>
              <CourseMappingSelect
                value={item._course_mapping}
                onChange={(v) => onUpdate?.(item._id!, '_course_mapping', v)}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function MaterialsTable({ items, onToggle, onUpdate }: TableProps<ParsedMaterial>) {
  return (
    <table className="irw-table">
      <thead>
        <tr>
          <th className="irw-th-check" />
          <th>Title</th>
          <th>Course</th>
          <th>Type</th>
          <th>URL</th>
          <th className="irw-th-status" />
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item._id} className={item._included === false ? 'irw-row-excluded' : ''}>
            <td>
              <input
                type="checkbox"
                checked={item._included !== false}
                onChange={() => onToggle(item._id!)}
              />
            </td>
            <td>
              <EditableCell
                value={item.title || ''}
                onChange={(v) => onUpdate?.(item._id!, 'title', v)}
              />
              <DuplicateBadge isDuplicate={item._is_duplicate} />
            </td>
            <td>
              <EditableCell
                value={item.course || ''}
                onChange={(v) => onUpdate?.(item._id!, 'course', v)}
              />
            </td>
            <td>
              <EditableCell
                value={item.type || ''}
                onChange={(v) => onUpdate?.(item._id!, 'type', v)}
              />
            </td>
            <td>
              <EditableCell
                value={item.url || ''}
                onChange={(v) => onUpdate?.(item._id!, 'url', v)}
              />
            </td>
            <td>
              <CourseMappingSelect
                value={item._course_mapping}
                onChange={(v) => onUpdate?.(item._id!, '_course_mapping', v)}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AnnouncementsTable({
  items,
  onToggle,
}: Omit<TableProps<ParsedAnnouncement>, 'onUpdate'>) {
  return (
    <table className="irw-table">
      <thead>
        <tr>
          <th className="irw-th-check" />
          <th>Title</th>
          <th>Author</th>
          <th>Date</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item._id} className={item._included === false ? 'irw-row-excluded' : ''}>
            <td>
              <input
                type="checkbox"
                checked={item._included !== false}
                onChange={() => onToggle(item._id!)}
              />
            </td>
            <td>
              <span className="irw-cell-value">{item.title || '\u2014'}</span>
            </td>
            <td>
              <span className="irw-cell-value">{item.author || '\u2014'}</span>
            </td>
            <td>
              <span className="irw-cell-value">{item.date || '\u2014'}</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function GradesTable({ items, onToggle, onUpdate }: TableProps<ParsedGrade>) {
  return (
    <table className="irw-table">
      <thead>
        <tr>
          <th className="irw-th-check" />
          <th>Assignment</th>
          <th>Course</th>
          <th>Score</th>
          <th>Max Score</th>
          <th className="irw-th-status" />
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item._id} className={item._included === false ? 'irw-row-excluded' : ''}>
            <td>
              <input
                type="checkbox"
                checked={item._included !== false}
                onChange={() => onToggle(item._id!)}
              />
            </td>
            <td>
              <EditableCell
                value={item.assignment || ''}
                onChange={(v) => onUpdate?.(item._id!, 'assignment', v)}
              />
              <DuplicateBadge isDuplicate={item._is_duplicate} />
            </td>
            <td>
              <EditableCell
                value={item.course || ''}
                onChange={(v) => onUpdate?.(item._id!, 'course', v)}
              />
            </td>
            <td>
              <EditableCell
                value={item.score != null ? String(item.score) : ''}
                onChange={(v) => onUpdate?.(item._id!, 'score', v)}
                type="number"
              />
            </td>
            <td>
              <EditableCell
                value={item.max_score != null ? String(item.max_score) : ''}
                onChange={(v) => onUpdate?.(item._id!, 'max_score', v)}
                type="number"
              />
            </td>
            <td>
              <CourseMappingSelect
                value={item._course_mapping}
                onChange={(v) => onUpdate?.(item._id!, '_course_mapping', v)}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------------------
// Course mapping dropdown
// ---------------------------------------------------------------------------

function CourseMappingSelect({
  value,
  onChange,
}: {
  value?: number | 'new';
  onChange?: (value: string) => void;
}) {
  return (
    <select
      className="irw-course-mapping"
      value={value != null ? String(value) : 'new'}
      onChange={(e) => onChange?.(e.target.value)}
      title="Map to existing course"
    >
      <option value="new">Create New</option>
      {/* Existing courses would be populated dynamically in a real integration */}
    </select>
  );
}
