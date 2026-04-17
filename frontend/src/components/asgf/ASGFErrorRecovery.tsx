import { useState } from 'react';
import type { IntentAlternative, FileUploadResponse } from '../../api/asgf';
import './ASGFErrorRecovery.css';

/* ------------------------------------------------------------------ */
/* OCR Failure Recovery                                                */
/* ------------------------------------------------------------------ */

export interface OCRFailureRecoveryProps {
  file: FileUploadResponse;
  onManualText: (fileId: string, text: string) => void;
}

export function OCRFailureRecovery({ file, onManualText }: OCRFailureRecoveryProps) {
  const [text, setText] = useState('');

  return (
    <div className="asgf-error-recovery asgf-error-recovery--ocr">
      <div className="asgf-error-recovery__header">
        <span className="asgf-error-recovery__icon">&#x1F4C4;</span>
        <div>
          <p className="asgf-error-recovery__message">
            We couldn't read this document — you can type key points instead
          </p>
          <p className="asgf-error-recovery__filename">{file.filename}</p>
        </div>
      </div>
      <textarea
        className="asgf-error-recovery__textarea"
        placeholder="Type the key points, formulas, or questions from this document..."
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={4}
      />
      <button
        type="button"
        className="asgf-error-recovery__btn asgf-error-recovery__btn--primary"
        disabled={text.trim().length === 0}
        onClick={() => onManualText(file.file_id, text.trim())}
      >
        Use this text
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Low Confidence Recovery                                             */
/* ------------------------------------------------------------------ */

export interface LowConfidenceRecoveryProps {
  detected: { subject: string; topic: string };
  alternatives: IntentAlternative[];
  onSelect: (alternative: IntentAlternative) => void;
}

export function LowConfidenceRecovery({
  detected,
  alternatives,
  onSelect,
}: LowConfidenceRecoveryProps) {
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  const allOptions: IntentAlternative[] = [
    { subject: detected.subject, topic: detected.topic, confidence: 0 },
    ...alternatives,
  ];

  return (
    <div className="asgf-error-recovery asgf-error-recovery--low-confidence">
      <p className="asgf-error-recovery__message">
        We detected a few possible subjects — please confirm
      </p>
      <div className="asgf-error-recovery__chips" role="radiogroup" aria-label="Subject alternatives">
        {allOptions.map((alt, i) => (
          <button
            key={`${alt.subject}-${alt.topic}-${i}`}
            type="button"
            role="radio"
            aria-checked={selectedIdx === i}
            className={`asgf-error-recovery__chip ${selectedIdx === i ? 'asgf-error-recovery__chip--selected' : ''}`}
            onClick={() => {
              setSelectedIdx(i);
              onSelect(alt);
            }}
          >
            <span className="asgf-error-recovery__chip-subject">{alt.subject}</span>
            {alt.topic && (
              <span className="asgf-error-recovery__chip-topic">{alt.topic}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Generation Failure Recovery                                         */
/* ------------------------------------------------------------------ */

export interface GenerationFailureRecoveryProps {
  attemptCount: number;
  onRetry: () => void;
  onFallback: () => void;
}

export function GenerationFailureRecovery({
  attemptCount,
  onRetry,
  onFallback,
}: GenerationFailureRecoveryProps) {
  const showFallback = attemptCount >= 2;

  return (
    <div className="asgf-error-recovery asgf-error-recovery--generation">
      <span className="asgf-error-recovery__icon">&#x26A0;</span>
      <p className="asgf-error-recovery__message">
        {showFallback
          ? "We're having trouble generating slides — would you like a text summary instead?"
          : "Something went wrong — let's try again"}
      </p>
      <div className="asgf-error-recovery__actions">
        {!showFallback && (
          <button
            type="button"
            className="asgf-error-recovery__btn asgf-error-recovery__btn--primary"
            onClick={onRetry}
          >
            Try again
          </button>
        )}
        {showFallback && (
          <>
            <button
              type="button"
              className="asgf-error-recovery__btn asgf-error-recovery__btn--primary"
              onClick={onFallback}
            >
              Get text summary
            </button>
            <button
              type="button"
              className="asgf-error-recovery__btn asgf-error-recovery__btn--secondary"
              onClick={onRetry}
            >
              Try slides again
            </button>
          </>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Vague Question Recovery                                             */
/* ------------------------------------------------------------------ */

export interface VagueQuestionRecoveryProps {
  alternatives: IntentAlternative[];
  onSelect: (alternative: IntentAlternative) => void;
}

export function VagueQuestionRecovery({
  alternatives,
  onSelect,
}: VagueQuestionRecoveryProps) {
  return (
    <div className="asgf-error-recovery asgf-error-recovery--vague">
      <p className="asgf-error-recovery__message">
        Your question is broad — want to focus on one of these?
      </p>
      <div className="asgf-error-recovery__chips" role="list" aria-label="Topic suggestions">
        {alternatives.map((alt, i) => (
          <button
            key={`${alt.subject}-${alt.topic}-${i}`}
            type="button"
            role="listitem"
            className="asgf-error-recovery__chip"
            onClick={() => onSelect(alt)}
          >
            <span className="asgf-error-recovery__chip-subject">{alt.subject}</span>
            {alt.topic && (
              <span className="asgf-error-recovery__chip-topic">{alt.topic}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
