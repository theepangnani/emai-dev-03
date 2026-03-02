import { useState } from 'react';
import { classroomImportApi } from '../api/classroomImport';
import './CopyPasteImporter.css';

interface CopyPasteImporterProps {
  studentId?: number;
  onSessionCreated: (sessionId: number) => void;
  onCancel?: () => void;
}

const SOURCE_OPTIONS = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'assignment_list', label: 'Assignment List (Classwork page)' },
  { value: 'assignment_detail', label: 'Single Assignment Detail' },
  { value: 'stream', label: 'Class Stream' },
  { value: 'people', label: 'People Page' },
] as const;

const MAX_CHARACTERS = 100_000;

export function CopyPasteImporter({
  studentId,
  onSessionCreated,
  onCancel,
}: CopyPasteImporterProps) {
  const [text, setText] = useState('');
  const [sourceHint, setSourceHint] = useState('auto');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const characterCount = text.length;
  const isOverLimit = characterCount > MAX_CHARACTERS;
  const canSubmit = text.trim().length > 0 && !isOverLimit && !isSubmitting;

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    if (errorMessage) {
      setErrorMessage('');
    }
  };

  const handleSubmit = async () => {
    if (!canSubmit) return;

    setIsSubmitting(true);
    setErrorMessage('');

    try {
      const response = await classroomImportApi.importCopyPaste({
        text: text.trim(),
        source_hint: sourceHint,
        student_id: studentId,
      });
      onSessionCreated(response.data.session_id);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail;
      setErrorMessage(
        detail || 'Failed to analyze the pasted content. Please try again.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="cpi-container">
      {/* Header */}
      <div className="cpi-header">
        <h2 className="cpi-title">Paste from Google Classroom</h2>
        <p className="cpi-description">
          Copy all text from your Google Classroom page (Ctrl+A, Ctrl+C) and
          paste it below.
        </p>
      </div>

      {/* Source hint dropdown */}
      <div className="cpi-field">
        <label className="cpi-label" htmlFor="cpi-source-hint">
          What page did you copy from?
        </label>
        <select
          id="cpi-source-hint"
          className="cpi-select"
          value={sourceHint}
          onChange={(e) => setSourceHint(e.target.value)}
          disabled={isSubmitting}
        >
          {SOURCE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Textarea */}
      <div className="cpi-field">
        <div className="cpi-textarea-wrapper">
          <textarea
            className={`cpi-textarea${isOverLimit ? ' cpi-textarea--error' : ''}`}
            value={text}
            onChange={handleTextChange}
            placeholder={
              'Paste your Google Classroom content here...\n\nTip: Go to your Google Classroom page, press Ctrl+A to select all, then Ctrl+C to copy, and Ctrl+V to paste here.'
            }
            disabled={isSubmitting}
            spellCheck={false}
          />
          <div className="cpi-char-count-row">
            <span
              className={`cpi-char-count${isOverLimit ? ' cpi-char-count--error' : ''}`}
            >
              {characterCount.toLocaleString()} / {MAX_CHARACTERS.toLocaleString()}
            </span>
          </div>
        </div>
      </div>

      {/* Error message */}
      {errorMessage && (
        <div className="cpi-error" role="alert">
          {errorMessage}
        </div>
      )}

      {/* Action buttons */}
      <div className="cpi-actions">
        {onCancel && (
          <button
            type="button"
            className="cancel-btn"
            onClick={onCancel}
            disabled={isSubmitting}
          >
            Cancel
          </button>
        )}
        <button
          type="button"
          className="generate-btn"
          onClick={handleSubmit}
          disabled={!canSubmit}
        >
          {isSubmitting ? (
            <span className="cpi-btn-loading">
              <span className="cpi-spinner" />
              Analyzing...
            </span>
          ) : (
            'Analyze & Import'
          )}
        </button>
      </div>
    </div>
  );
}
