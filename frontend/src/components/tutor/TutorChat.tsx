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
import { renderToStaticMarkup } from 'react-dom/server';
import ReactMarkdown from 'react-markdown';
import { ArcMascot } from '../arc';
import { getArcVariant } from '../arc/util';
import { useAuth } from '../../context/AuthContext';
import { TutorMessage } from './TutorMessage';
import { TutorSuggestionChips } from './TutorSuggestionChips';
import { TutorInputBar } from './TutorInputBar';
import { useTutorChat } from './useTutorChat';
import type { TutorMessage as TutorMessageType } from './useTutorChat';
import type { FileUploadResponse } from '../../api/asgf';
import { downloadAsPdf } from '../../utils/exportUtils';
import './TutorChat.css';

export interface TutorChatProps {
  /** First name used in Arc's greeting. Empty string → "friend". */
  firstName?: string;
  /** Called every time files are uploaded through the attach drawer. */
  onFilesUploaded?: (files: FileUploadResponse[]) => void;
  /** Optional externally-controlled messages state. When supplied together
   *  with `setMessages`, the hook uses these instead of its internal state —
   *  this lets the parent hoist chat state above a mode-toggle so it
   *  survives Explain⇄Drill unmounts (#4095 Bug 2). */
  messages?: TutorMessageType[];
  setMessages?: React.Dispatch<React.SetStateAction<TutorMessageType[]>>;
  /** Optional externally-controlled conversation_id state (paired with
   *  `messages`/`setMessages` above). */
  conversationId?: string | null;
  setConversationId?: React.Dispatch<React.SetStateAction<string | null>>;
}

export function TutorChat({
  firstName,
  onFilesUploaded,
  messages: externalMessages,
  setMessages: externalSetMessages,
  conversationId: externalConversationId,
  setConversationId: externalSetConversationId,
}: TutorChatProps) {
  const { messages, sendMessage, requestFull, isStreaming, cancel, error } = useTutorChat({
    externalMessages,
    externalSetMessages,
    externalConversationId,
    externalSetConversationId,
  });
  const [draft, setDraft] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const lastMessageId = messages[messages.length - 1]?.id;
  const { user, isLoading: authLoading } = useAuth();
  const arcVariant = authLoading ? undefined : getArcVariant(user?.id);

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

  const handleDownloadPdf = useCallback(async (message: TutorMessageType) => {
    const ts = message.timestamp instanceof Date ? message.timestamp : new Date();
    const pad = (n: number) => String(n).padStart(2, '0');
    const stamp = `${ts.getFullYear()}${pad(ts.getMonth() + 1)}${pad(ts.getDate())}-${pad(ts.getHours())}${pad(ts.getMinutes())}`;
    const filename = `Arc-tutor-${stamp}.pdf`;

    // Render the markdown to static HTML inside an off-DOM container that
    // html2pdf can consume. We attach it to the body briefly (off-screen)
    // because html2canvas requires an in-DOM element.
    const bodyHtml = renderToStaticMarkup(<ReactMarkdown>{message.content}</ReactMarkdown>);
    const wrapper = document.createElement('div');
    wrapper.style.position = 'fixed';
    wrapper.style.left = '-99999px';
    wrapper.style.top = '0';
    wrapper.style.width = '720px';
    wrapper.innerHTML = `<h1>Arc — ClassBridge tutor reply</h1>${bodyHtml}`;
    document.body.appendChild(wrapper);
    try {
      await downloadAsPdf(wrapper, filename);
    } finally {
      wrapper.remove();
    }
  }, []);

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
            <div className="tutor-chat__empty-mascot" aria-hidden="true" data-arc={arcVariant}>
              <ArcMascot size={96} mood="waving" glow animate decorative />
            </div>
            <p className="tutor-chat__empty-eyebrow">Hey, {greeting}.</p>
            <h2 className="tutor-chat__empty-headline">
              What do you want to <em>actually</em> understand today?
            </h2>
          </div>
        )}

        {!isEmpty &&
          messages.map((m, idx) => (
            <TutorMessage
              key={m.id}
              message={m}
              isLatest={idx === messages.length - 1}
              isStreaming={isStreaming}
              onRequestFull={requestFull}
              onDownloadPdf={handleDownloadPdf}
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
