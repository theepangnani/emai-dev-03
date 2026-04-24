/**
 * TutorInputBar — bottom-anchored composer for TutorChat.
 *
 * Reuses `ASGFUploadZone` for attachments (opens in a drawer above the bar,
 * not inline). Enter submits, Shift+Enter newlines, and the send button
 * flips to a Cancel button while a stream is in-flight.
 */
import { useEffect, useRef, useState } from 'react';
import ASGFUploadZone from '../asgf/ASGFUploadZone';
import type { FileUploadResponse } from '../../api/asgf';

export interface TutorInputBarProps {
  onSend: (text: string) => void;
  onCancel?: () => void;
  isStreaming?: boolean;
  disabled?: boolean;
  /** External value (for suggestion-chip prefill). When present, the bar
   *  becomes controlled — clearing after send also goes through the parent. */
  value?: string;
  onChange?: (text: string) => void;
  onFilesUploaded?: (files: FileUploadResponse[]) => void;
  placeholder?: string;
}

export function TutorInputBar({
  onSend,
  onCancel,
  isStreaming = false,
  disabled = false,
  value,
  onChange,
  onFilesUploaded,
  placeholder = 'Ask Arc anything — or shift+enter for a new line',
}: TutorInputBarProps) {
  const [internal, setInternal] = useState('');
  const [attachOpen, setAttachOpen] = useState(false);
  const taRef = useRef<HTMLTextAreaElement>(null);

  const controlled = typeof value === 'string';
  const text = controlled ? (value as string) : internal;
  const setText = (t: string) => {
    if (controlled) onChange?.(t);
    else setInternal(t);
  };

  // Auto-grow textarea — capped by CSS max-height.
  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const submit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled || isStreaming) return;
    onSend(trimmed);
    setText('');
  };

  return (
    <div className="tutor-input-wrap">
      {attachOpen && (
        <div className="tutor-input-drawer" role="region" aria-label="Attach materials">
          <ASGFUploadZone onFilesUploaded={onFilesUploaded} />
        </div>
      )}
      <div className="tutor-input-bar">
        <button
          type="button"
          className={`tutor-input-attach ${attachOpen ? 'tutor-input-attach--open' : ''}`}
          onClick={() => setAttachOpen((v) => !v)}
          aria-pressed={attachOpen}
          aria-label="Attach class materials"
          disabled={disabled}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M21 11.5l-8.5 8.5a5 5 0 1 1-7-7L14 4.5a3.5 3.5 0 1 1 4.9 5L10 18.5a2 2 0 0 1-2.8-2.8l7.8-7.8"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>

        <textarea
          ref={taRef}
          className="tutor-input-field"
          value={text}
          placeholder={placeholder}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={disabled}
          aria-label="Message Arc"
        />

        {isStreaming ? (
          <button
            type="button"
            className="tutor-input-send tutor-input-send--cancel"
            onClick={onCancel}
            aria-label="Cancel response"
          >
            <span className="tutor-input-send__stop" aria-hidden="true" />
          </button>
        ) : (
          <button
            type="button"
            className="tutor-input-send"
            onClick={submit}
            disabled={!text.trim() || disabled}
            aria-label="Send message"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M4 12l16-8-6 18-3-8-7-2z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

export default TutorInputBar;
