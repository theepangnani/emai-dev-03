import { isValidEmail } from '../utils/validation';

export type EditableRow = {
  class_name: string;
  section: string | null;
  teacher_name: string;
  teacher_email: string | null;
  google_classroom_id: string | null;
  existing?: boolean;
  selected: boolean;
  validationError?: string;
};

type Props = {
  rows: EditableRow[];
  onChange: (rows: EditableRow[]) => void;
  onRemove: (index: number) => void;
  onAdd: () => void;
  busy?: boolean;
  showCheckbox?: boolean;
};

function toTitleCase(s: string): string {
  return s
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function validateRow(row: EditableRow): string | undefined {
  if (!row.class_name.trim()) return 'Class name is required';
  if (!row.teacher_name.trim()) return 'Teacher name is required';
  if (row.teacher_email && row.teacher_email.trim() && !isValidEmail(row.teacher_email.trim())) {
    return 'Invalid teacher email';
  }
  return undefined;
}

export default function ImportReviewTable({ rows, onChange, onRemove, onAdd, busy, showCheckbox = true }: Props) {
  const updateRow = (index: number, patch: Partial<EditableRow>) => {
    const next = rows.map((r, i) => {
      if (i !== index) return r;
      const merged = { ...r, ...patch };
      merged.validationError = validateRow(merged);
      return merged;
    });
    onChange(next);
  };

  const toggleSelected = (index: number, checked: boolean) => {
    updateRow(index, { selected: checked });
  };

  const handleTitleCase = (index: number) => {
    const row = rows[index];
    updateRow(index, {
      class_name: toTitleCase(row.class_name || ''),
      teacher_name: toTitleCase(row.teacher_name || ''),
    });
  };

  return (
    <div className="import-review-table-wrap">
      <table className="import-review-table" aria-label="Import classes review table">
        <thead>
          <tr>
            {showCheckbox && <th className="irt-col-check" scope="col" aria-label="Select row" />}
            <th scope="col">Class name</th>
            <th scope="col">Section</th>
            <th scope="col">Teacher name</th>
            <th scope="col">Teacher email</th>
            <th scope="col" className="irt-col-actions" aria-label="Row actions" />
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={showCheckbox ? 6 : 5} className="irt-empty">
                No rows to review yet.
              </td>
            </tr>
          )}
          {rows.map((row, index) => {
            const error = row.validationError;
            const classInvalid = !row.class_name.trim();
            const teacherInvalid = !row.teacher_name.trim();
            const emailInvalid = !!(row.teacher_email && row.teacher_email.trim() && !isValidEmail(row.teacher_email.trim()));
            return (
              <tr key={index} className={row.existing ? 'irt-row-existing' : undefined}>
                {showCheckbox && (
                  <td className="irt-col-check">
                    <input
                      type="checkbox"
                      aria-label={`Include ${row.class_name || 'row ' + (index + 1)}`}
                      checked={row.selected}
                      onChange={(e) => toggleSelected(index, e.target.checked)}
                      disabled={busy}
                    />
                  </td>
                )}
                <td>
                  <input
                    type="text"
                    className={`irt-input${classInvalid ? ' irt-input-error' : ''}`}
                    value={row.class_name}
                    onChange={(e) => updateRow(index, { class_name: e.target.value })}
                    placeholder="Class name"
                    disabled={busy}
                    aria-invalid={classInvalid}
                    aria-label="Class name"
                  />
                  {row.existing && (
                    <span className="irt-badge" aria-label="Already imported">Already imported</span>
                  )}
                </td>
                <td>
                  <input
                    type="text"
                    className="irt-input"
                    value={row.section ?? ''}
                    onChange={(e) => updateRow(index, { section: e.target.value || null })}
                    placeholder="Section"
                    disabled={busy}
                    aria-label="Section"
                  />
                </td>
                <td>
                  <input
                    type="text"
                    className={`irt-input${teacherInvalid ? ' irt-input-error' : ''}`}
                    value={row.teacher_name}
                    onChange={(e) => updateRow(index, { teacher_name: e.target.value })}
                    placeholder="Teacher name"
                    disabled={busy}
                    aria-invalid={teacherInvalid}
                    aria-label="Teacher name"
                  />
                </td>
                <td>
                  <input
                    type="email"
                    className={`irt-input${emailInvalid ? ' irt-input-error' : ''}`}
                    value={row.teacher_email ?? ''}
                    onChange={(e) => updateRow(index, { teacher_email: e.target.value || null })}
                    placeholder="teacher@school.com"
                    disabled={busy}
                    aria-invalid={emailInvalid}
                    aria-label="Teacher email"
                  />
                </td>
                <td className="irt-col-actions">
                  <button
                    type="button"
                    className="irt-action-btn"
                    title="Title-case names"
                    aria-label="Title-case names"
                    onClick={() => handleTitleCase(index)}
                    disabled={busy}
                  >
                    Aa
                  </button>
                  <button
                    type="button"
                    className="irt-action-btn irt-action-remove"
                    title="Remove row"
                    aria-label={`Remove row ${index + 1}`}
                    onClick={() => onRemove(index)}
                    disabled={busy}
                  >
                    ×
                  </button>
                  {error && <span className="irt-error" role="alert">{error}</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="irt-footer">
        <button
          type="button"
          className="irt-add-row"
          onClick={onAdd}
          disabled={busy}
        >
          + Add row
        </button>
      </div>
    </div>
  );
}
