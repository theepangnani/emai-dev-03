/**
 * TutorMessage — a single chat bubble in the TutorChat stream.
 *
 * Asymmetric layout:
 *   • user  → right-aligned, subtle warm gradient
 *   • Arc   → left-aligned, generous whitespace, no avatar crowding
 *
 * Markdown renders via react-markdown; safety notices carry their own
 * visual treatment (warm border, iconless headline).
 */
import ReactMarkdown from 'react-markdown';
import type { TutorMessage as TutorMessageType } from './useTutorChat';

export interface TutorMessageProps {
  message: TutorMessageType;
  /** True when this is the most recent message (used for entrance animation). */
  isLatest?: boolean;
}

export function TutorMessage({ message, isLatest = false }: TutorMessageProps) {
  const { role, content, safety, streaming } = message;
  const isUser = role === 'user';

  const classes = [
    'tutor-msg',
    isUser ? 'tutor-msg--user' : 'tutor-msg--arc',
    safety ? 'tutor-msg--safety' : '',
    isLatest ? 'tutor-msg--latest' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <article className={classes} aria-live={!isUser && streaming ? 'polite' : undefined}>
      {!isUser && safety && (
        <span className="tutor-msg__tag" aria-label="Safety notice">
          Heads up
        </span>
      )}
      <div className="tutor-msg__bubble">
        {isUser ? (
          // User input is plain text — skip markdown to avoid injecting
          // formatting into what they typed.
          <p className="tutor-msg__text">{content}</p>
        ) : (
          <div className="tutor-msg__markdown">
            {content ? (
              <ReactMarkdown>{content}</ReactMarkdown>
            ) : streaming ? (
              <TypingDots />
            ) : null}
            {/* Trailing caret while tokens still arriving */}
            {streaming && content && <span className="tutor-msg__caret" aria-hidden="true" />}
          </div>
        )}
      </div>
    </article>
  );
}

function TypingDots() {
  return (
    <span
      className="tutor-msg__typing"
      role="status"
      aria-label="Arc is thinking"
    >
      <span />
      <span />
      <span />
    </span>
  );
}

export default TutorMessage;
