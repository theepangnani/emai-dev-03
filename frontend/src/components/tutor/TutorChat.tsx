/**
 * TutorChat — chat-first Explain-mode shell for /tutor (CB-TUTOR-002 Phase 1).
 *
 * Layout philosophy:
 *   • Not another Intercom clone — asymmetric, with Arc anchored left and
 *     deliberate whitespace before each assistant turn.
 *   • Conversation state + last-3-turn memory via `useTutorChat`.
 *   • Suggestion chips render under the MOST RECENT assistant message only.
 *   • Input bar is bottom-anchored within this shell (the page provides the
 *     outer chrome via DashboardLayout).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ArcMascot } from '../arc';
import { TutorMessage } from './TutorMessage';
import { TutorSuggestionChips } from './TutorSuggestionChips';
import { TutorInputBar } from './TutorInputBar';
import { useTutorChat } from './useTutorChat';
import type { FileUploadResponse } from '../../api/asgf';
import './TutorChat.css';

export interface TutorChatProps {
  /** First name used in Arc's greeting. Empty string → "friend". */
  firstName?: string;
  /** Called every time files are uploaded through the attach drawer. */
  onFilesUploaded?: (files: FileUploadResponse[]) => void;
}

const DEFAULT_STARTERS = [
  'Explain photosynthesis like I\'m in grade 7',
  'Help me with a tricky fraction problem',
  'Summarize my history notes on WWII',
];

export function TutorChat({ firstName, onFilesUploaded }: TutorChatProps) {
  const { messages, sendMessage, isStreaming, cancel, error } = useTutorChat();
  const [draft, setDraft] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const lastMessageId = messages[messages.length - 1]?.id;

  // Auto-scroll to bottom whenever a new message lands or tokens stream in.
  // During active streaming, use instant scroll to avoid interrupt-smooth
  // jank (each token kicks off a new smooth animation that cancels the
  // previous one). On settled state, use smooth for the final scroll.
  // `scrollTo` isn't always available (e.g. jsdom), so fall back to assigning
  // scrollTop directly.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const behavior: ScrollBehavior = isStreaming ? 'auto' : 'smooth';
    if (typeof el.scrollTo === 'function') {
      el.scrollTo({ top: el.scrollHeight, behavior });
    } else {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages.length, lastMessageId, isStreaming]);

  const handleSend = useCallback(
    (text: string) => {
      setDraft('');
      void sendMessage(text);
    },
    [sendMessage],
  );

  const handleChipSelect = useCallback(
    (text: string) => {
      // Drop the chip text directly into the draft so the user can edit
      // before sending — less jarring than an auto-send.
      setDraft(text);
    },
    [],
  );

  const handleStarter = useCallback(
    (text: string) => {
      setDraft(text);
    },
    [],
  );

  const greeting = useMemo(() => {
    const name = firstName?.trim() ? firstName.split(' ')[0] : 'friend';
    return name;
  }, [firstName]);

  // Suggestion chips attach to the LAST assistant message only.
  const lastAssistant = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant') return messages[i];
    }
    return null;
  }, [messages]);

  const showChips =
    lastAssistant &&
    !lastAssistant.streaming &&
    Array.isArray(lastAssistant.suggestions) &&
    lastAssistant.suggestions.length > 0;

  const isEmpty = messages.length === 0;

  return (
    <div className="tutor-chat" data-testid="tutor-chat">
      <div className="tutor-chat__stream" ref={scrollRef}>
        {isEmpty && (
          <div className="tutor-chat__empty">
            <div className="tutor-chat__empty-mascot" aria-hidden="true">
              <ArcMascot size={96} mood="waving" glow animate decorative />
            </div>
            <p className="tutor-chat__empty-eyebrow">Hey, {greeting}.</p>
            <h2 className="tutor-chat__empty-headline">
              What do you want to <em>actually</em> understand today?
            </h2>
            <p className="tutor-chat__empty-sub">
              Ask me anything, paste a worksheet, or pick a starter below. I'll keep
              things concise — and we can go deeper if you want.
            </p>
            <div className="tutor-chat__starters" role="list" aria-label="Starter prompts">
              {DEFAULT_STARTERS.map((s, i) => (
                <button
                  key={s}
                  type="button"
                  role="listitem"
                  className="tutor-chat__starter"
                  onClick={() => handleStarter(s)}
                  style={{ animationDelay: `${120 + i * 80}ms` }}
                >
                  <span className="tutor-chat__starter-num">0{i + 1}</span>
                  <span className="tutor-chat__starter-text">{s}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {!isEmpty &&
          messages.map((m, idx) => (
            <TutorMessage
              key={m.id}
              message={m}
              isLatest={idx === messages.length - 1}
            />
          ))}

        {showChips && lastAssistant && (
          <TutorSuggestionChips
            suggestions={lastAssistant.suggestions ?? []}
            onSelect={handleChipSelect}
            disabled={isStreaming}
          />
        )}

        {error && (
          <div className="tutor-chat__error" role="alert">
            <span className="tutor-chat__error-title">Arc hit a snag.</span>
            <span className="tutor-chat__error-body">{error}</span>
          </div>
        )}
      </div>

      <div className="tutor-chat__dock">
        <TutorInputBar
          value={draft}
          onChange={setDraft}
          onSend={handleSend}
          onCancel={cancel}
          isStreaming={isStreaming}
          onFilesUploaded={onFilesUploaded}
        />
      </div>
    </div>
  );
}

export default TutorChat;
