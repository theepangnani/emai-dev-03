import { useState, useRef, useCallback, useEffect } from 'react';
import { asgfApi, type IntentClassifyResponse } from '../../api/asgf';
import './ASGFQuestionInput.css';

const MAX_CHARS = 1000;
const DEBOUNCE_MS = 500;
const MIN_CHARS = 15;

export interface ASGFQuestionInputProps {
  value: string;
  onChange: (value: string) => void;
  onIntentClassified?: (result: IntentClassifyResponse | null) => void;
  disabled?: boolean;
}

export function ASGFQuestionInput({
  value,
  onChange,
  onIntentClassified,
  disabled = false,
}: ASGFQuestionInputProps) {
  const [classifyResult, setClassifyResult] = useState<IntentClassifyResponse | null>(null);
  const [isClassifying, setIsClassifying] = useState(false);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const classify = useCallback(
    async (question: string) => {
      // Cancel any in-flight request
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setIsClassifying(true);
      try {
        const result = await asgfApi.classifyIntent(question);
        if (!controller.signal.aborted) {
          setClassifyResult(result);
          onIntentClassified?.(result);
        }
      } catch {
        if (!controller.signal.aborted) {
          setClassifyResult(null);
          onIntentClassified?.(null);
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsClassifying(false);
        }
      }
    },
    [onIntentClassified],
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const text = e.target.value.slice(0, MAX_CHARS);
      onChange(text);

      // Clear previous debounce
      if (debounceTimer.current) clearTimeout(debounceTimer.current);

      if (text.trim().length < MIN_CHARS) {
        setClassifyResult(null);
        onIntentClassified?.(null);
        setIsClassifying(false);
        abortRef.current?.abort();
        return;
      }

      debounceTimer.current = setTimeout(() => classify(text), DEBOUNCE_MS);
    },
    [onChange, classify, onIntentClassified],
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
      abortRef.current?.abort();
    };
  }, []);

  const charCount = value.length;
  const charClass =
    charCount > MAX_CHARS
      ? 'asgf-question-input__char-count--over'
      : charCount > MAX_CHARS * 0.9
        ? 'asgf-question-input__char-count--warn'
        : '';

  const showLabel =
    classifyResult && classifyResult.confidence >= 0.5 && classifyResult.subject;
  const showLowConfidence =
    classifyResult && classifyResult.confidence > 0 && classifyResult.confidence < 0.5;

  return (
    <div className="asgf-question-input">
      <div className="asgf-question-input__textarea-wrapper">
        <textarea
          className="asgf-question-input__textarea"
          placeholder="Ask anything — we'll build a full learning session around your question."
          value={value}
          onChange={handleChange}
          maxLength={MAX_CHARS}
          disabled={disabled}
          rows={4}
        />
      </div>

      <div className="asgf-question-input__footer">
        <div className="asgf-question-input__category">
          {isClassifying && <span className="asgf-question-input__spinner" />}
          {!isClassifying && showLabel && (
            <span>
              Looks like:{' '}
              <span className="asgf-question-input__category-label">
                {classifyResult.grade_level} {classifyResult.subject} &rarr;{' '}
                {classifyResult.topic}
              </span>
            </span>
          )}
          {!isClassifying && showLowConfidence && (
            <span className="asgf-question-input__low-confidence">
              We&rsquo;ll help you refine this in the next step
            </span>
          )}
        </div>
        <span className={`asgf-question-input__char-count ${charClass}`}>
          {charCount}/{MAX_CHARS}
        </span>
      </div>
    </div>
  );
}
