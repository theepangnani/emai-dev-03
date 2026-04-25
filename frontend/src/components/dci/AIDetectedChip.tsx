/**
 * AIDetectedChip — shows what the classifier inferred (subject + topic +
 * deadline) for a single artifact, with an inline "tap to correct" affordance.
 *
 * Pure presentational + uncontrolled "edit" toggle. The actual PATCH is
 * performed by the parent via `onCorrect`. The chip itself is the kid's
 * visible affordance: P3 "AI assists, never decides" on the kid side.
 */
import { useState } from 'react';
import type {
  DciClassification,
  DciCorrectionPayload,
} from '../../api/dci';
import './AIDetectedChip.css';

export interface AIDetectedChipProps {
  classification: DciClassification | null;
  /** "loading" stops the chip from rendering "we don't know yet" jitter. */
  loading?: boolean;
  onCorrect?: (next: DciCorrectionPayload) => Promise<void> | void;
}

export function AIDetectedChip({
  classification,
  loading = false,
  onCorrect,
}: AIDetectedChipProps) {
  const [editing, setEditing] = useState(false);
  const [subject, setSubject] = useState(classification?.subject ?? '');
  const [topic, setTopic] = useState(classification?.topic ?? '');

  if (loading) {
    return (
      <div className="ai-detected-chip ai-detected-chip--loading" aria-live="polite">
        <span className="ai-detected-chip__label">AI is reading…</span>
      </div>
    );
  }

  if (!classification) {
    return null;
  }

  const startEdit = () => {
    setSubject(classification.subject ?? '');
    setTopic(classification.topic ?? '');
    setEditing(true);
  };

  const save = async () => {
    if (!onCorrect) {
      setEditing(false);
      return;
    }
    // Only include fields the kid actually changed so PATCH stays a true
    // partial update (M0-4 contract). artifact_type is always required to
    // identify which artifact in the check-in we're correcting.
    const payload: DciCorrectionPayload = {
      artifact_type: classification.artifact_type,
    };
    const trimmedSubject = subject.trim();
    const trimmedTopic = topic.trim();
    if (trimmedSubject !== (classification.subject ?? '')) {
      payload.subject = trimmedSubject || undefined;
    }
    if (trimmedTopic !== (classification.topic ?? '')) {
      payload.topic = trimmedTopic || undefined;
    }
    await onCorrect(payload);
    setEditing(false);
  };

  if (editing) {
    return (
      <div className="ai-detected-chip ai-detected-chip--editing">
        <label className="ai-detected-chip__field">
          <span>Subject</span>
          <input
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            aria-label="Subject"
          />
        </label>
        <label className="ai-detected-chip__field">
          <span>Topic</span>
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            aria-label="Topic"
          />
        </label>
        <div className="ai-detected-chip__edit-actions">
          <button type="button" onClick={save} className="ai-detected-chip__save">
            Save
          </button>
          <button
            type="button"
            onClick={() => setEditing(false)}
            className="ai-detected-chip__cancel"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`ai-detected-chip${
        classification.corrected_by_kid ? ' ai-detected-chip--corrected' : ''
      }`}
    >
      <span className="ai-detected-chip__label">AI detected</span>
      <span className="ai-detected-chip__value">
        {classification.subject ?? 'Unknown subject'}
        {classification.topic ? ` · ${classification.topic}` : ''}
        {classification.deadline_iso ? ` · due ${classification.deadline_iso}` : ''}
      </span>
      {onCorrect && (
        <button
          type="button"
          className="ai-detected-chip__correct"
          onClick={startEdit}
          aria-label="Correct AI detection"
        >
          Not quite — fix it
        </button>
      )}
    </div>
  );
}

export default AIDetectedChip;
