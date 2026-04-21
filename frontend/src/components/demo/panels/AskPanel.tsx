import {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from 'react';
import {
  streamGenerate,
  type DemoHistoryTurn,
  type DemoType,
} from '../../../api/demo';
import { DemoMascot } from '../DemoMascot';
import { StreamingMarkdown } from '../../StreamingMarkdown';
import { GatedActionBar } from '../GatedActionBar';
import { IconSend } from '../icons';
import { GATED_ACTIONS } from '../instantTrialHelpers';
import type { DemoGameActions } from '../gamification/useDemoGameState';

/**
 * Ask panel (§6.135.5, #3785) — multi-turn conversational chatbox.
 *
 * The panel owns its own conversation thread and streaming state so output
 * survives tab-switches (per-tab cache, #3762). The orchestrator stays
 * ignorant of turn-level state — it only learns "a turn completed" via
 * ``onTurnComplete`` (used to light up tab chips + the conversion card).
 *
 * Rules:
 *   - Empty state shows 3 hard-coded starter chips.
 *   - 3 assistant-turn cap. Turn 4+ is gated behind the waitlist.
 *   - Turn 1 awards 15 XP + marks the `ask` quest + first-spark achievement
 *     (when no XP has been earned yet in the session).
 *   - Turns 2–3 award 10 XP.
 *
 * Reset contract:
 *   - The orchestrator clears all streams on source change; it passes
 *     ``resetKey`` so the panel can drop its thread in lockstep. The full
 *     demo reset simply remounts the modal.
 */

export type AskTurnRole = 'user' | 'assistant';

export interface AskTurn {
  id: string;
  role: AskTurnRole;
  content: string;
  status: 'streaming' | 'done' | 'error';
  error?: string;
}

const MAX_ASSISTANT_TURNS = 3;

const STARTER_CHIPS: string[] = [
  'Explain photosynthesis simply',
  'What caused World War I?',
  'How does gravity work?',
];

export interface AskPanelProps {
  sessionJwt: string;
  /** Bumped by the orchestrator to clear the thread on source change. */
  resetKey?: number;
  /** Fires after each successful assistant turn so the orchestrator can
   *  light up tab chips / show the conversion card / mark gamification. */
  onTurnComplete?: (demoType: DemoType, turnNumber: number) => void;
  /** Subset of game-state actions actually used by the Ask panel. */
  gameActions?: Pick<DemoGameActions, 'awardXP' | 'markQuest' | 'earnAchievement'>;
  /** Is the session currently at 0 XP? Drives the first-spark achievement. */
  isFirstXpOfSession?: boolean;
}

function nextTurnId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `t-${Math.random().toString(36).slice(2)}-${Date.now()}`;
}

export function AskPanel({
  sessionJwt,
  resetKey,
  onTurnComplete,
  gameActions,
  isFirstXpOfSession,
}: AskPanelProps) {
  const [turns, setTurns] = useState<AskTurn[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const threadEndRef = useRef<HTMLDivElement | null>(null);

  // `isFirstXpOfSession` is a render prop that may change between turns;
  // we need the value at the moment onTurnComplete fires, not from the
  // closure, so mirror it into a ref.
  const isFirstXpRef = useRef<boolean>(isFirstXpOfSession ?? false);
  useEffect(() => {
    isFirstXpRef.current = isFirstXpOfSession ?? false;
  }, [isFirstXpOfSession]);

  // Orchestrator source-change reset (preserves per-tab-cache contract).
  // The ESLint rule `react-hooks/set-state-in-effect` flags this because a
  // setState inside an effect normally cascades renders, but here it is
  // intentional: the external ``resetKey`` is the "dependency change" the
  // effect is responding to, and we need to abort any in-flight stream
  // before clearing state.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => {
    if (resetKey === undefined) return;
    abortRef.current?.abort();
    setTurns([]);
    setInput('');
    setIsStreaming(false);
  }, [resetKey]);

  // Cleanup on unmount.
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  // Auto-scroll the thread to the bottom on new tokens. Guarded because
  // JSDOM (test env) does not implement ``scrollIntoView``.
  useEffect(() => {
    const el = threadEndRef.current;
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'end', behavior: 'auto' });
    }
  }, [turns]);

  const assistantTurnCount = useMemo(
    () => turns.filter((t) => t.role === 'assistant' && t.status !== 'error').length,
    [turns],
  );

  const capReached = assistantTurnCount >= MAX_ASSISTANT_TURNS;
  const lastAssistantDone =
    turns.length > 0 &&
    turns[turns.length - 1].role === 'assistant' &&
    turns[turns.length - 1].status === 'done';

  // ``sendTurn`` relies on its closure's ``isStreaming`` + ``capReached``
  // snapshots being fresh — both are in the useCallback deps below. A
  // future refactor that moves them behind a ref must keep the early
  // return guard valid, or the cap can be bypassed.
  const sendTurn = useCallback(
    (questionText: string) => {
      const question = questionText.trim();
      if (!question || isStreaming || capReached) return;

      // Build the capped history from prior turns (≤2 turns =
      // last user + last assistant so the total prompt stays ≤3 msgs).
      const history: DemoHistoryTurn[] = turns
        .filter((t) => t.status === 'done')
        .slice(-2)
        .map((t) => ({ role: t.role, content: t.content.slice(0, 500) }));

      const userTurn: AskTurn = {
        id: nextTurnId(),
        role: 'user',
        content: question,
        status: 'done',
      };
      const assistantTurn: AskTurn = {
        id: nextTurnId(),
        role: 'assistant',
        content: '',
        status: 'streaming',
      };

      setTurns((prev) => [...prev, userTurn, assistantTurn]);
      setInput('');
      setIsStreaming(true);

      abortRef.current?.abort();
      const controller = streamGenerate(
        sessionJwt,
        {
          demo_type: 'ask',
          question,
          history: history.length > 0 ? history : undefined,
        },
        {
          onToken: (chunk: string) => {
            setTurns((prev) =>
              prev.map((t) =>
                t.id === assistantTurn.id
                  ? { ...t, content: t.content + chunk }
                  : t,
              ),
            );
          },
          onDone: () => {
            setTurns((prev) =>
              prev.map((t) =>
                t.id === assistantTurn.id ? { ...t, status: 'done' } : t,
              ),
            );
            setIsStreaming(false);

            // Count assistant turns *after* this turn lands.
            const nextTurnNumber = assistantTurnCount + 1;

            // Gamification: XP + quest + first-spark achievement. The
            // cap guard in sendTurn already prevents turn 4+ from
            // reaching onDone, but keep a belt-and-braces check so a
            // future refactor can't accidentally let XP overflow.
            if (gameActions && nextTurnNumber <= MAX_ASSISTANT_TURNS) {
              if (nextTurnNumber === 1) {
                gameActions.awardXP(15);
                gameActions.markQuest('ask');
                if (isFirstXpRef.current) {
                  gameActions.earnAchievement('first-spark');
                }
              } else {
                gameActions.awardXP(10);
              }
            }

            onTurnComplete?.('ask', nextTurnNumber);
          },
          onError: (message: string) => {
            setTurns((prev) =>
              prev.map((t) =>
                t.id === assistantTurn.id
                  ? { ...t, status: 'error', error: message }
                  : t,
              ),
            );
            setIsStreaming(false);
          },
        },
      );
      abortRef.current = controller;
    },
    [
      sessionJwt,
      turns,
      isStreaming,
      capReached,
      assistantTurnCount,
      gameActions,
      onTurnComplete,
    ],
  );

  const handleChipClick = (text: string) => {
    // sendTurn clears the input itself; no need to pre-fill it.
    sendTurn(text);
  };

  const handleSubmit = (e?: React.FormEvent<HTMLFormElement>) => {
    e?.preventDefault();
    sendTurn(input);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Send on Enter, allow Shift+Enter for newline.
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendTurn(input);
    }
  };

  const isEmpty = turns.length === 0;
  const placeholder = capReached
    ? 'Demo limit reached — continue on the waitlist'
    : 'Ask a question…';

  return (
    <div className="demo-ask-chat">
      <div
        className="demo-ask-thread"
        role="log"
        // Mute live-region announcements while tokens are arriving so
        // VoiceOver/JAWS don't re-announce the bubble on every chunk;
        // re-enable on turn completion so the final reply gets a clean
        // pass.
        aria-live={isStreaming ? 'off' : 'polite'}
        aria-busy={isStreaming}
        aria-label="Conversation with ClassBridge Demo Tutor"
      >
        {isEmpty ? (
          <div className="demo-ask-empty">
            <div className="demo-ask-empty__mascot" aria-hidden="true">
              <DemoMascot size={56} mood="greeting" />
            </div>
            <p className="demo-ask-empty__title">Ask me anything</p>
            <p className="demo-ask-empty__sub">
              Start a conversation — I'll stream an answer and you can keep
              asking follow-ups.
            </p>
            <div
              className="demo-ask-starter-chips"
              role="group"
              aria-label="Starter suggestions"
            >
              {STARTER_CHIPS.map((chip) => (
                <button
                  key={chip}
                  type="button"
                  className="demo-chip demo-ask-starter-chip"
                  onClick={() => handleChipClick(chip)}
                  // Mirror the Send-button predicate so future refactors
                  // can't let a chip bypass the cap.
                  disabled={isStreaming || capReached}
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {turns.map((turn) => (
              <ChatBubble key={turn.id} turn={turn} />
            ))}
            <div ref={threadEndRef} aria-hidden="true" />
          </>
        )}
      </div>

      <form
        className="demo-ask-inputbar"
        onSubmit={handleSubmit}
        aria-label="Send a message"
      >
        <textarea
          className="demo-ask-textarea"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          aria-label="Type your question"
          maxLength={500}
          rows={1}
          disabled={isStreaming || capReached}
        />
        <button
          type="submit"
          className="demo-btn-primary demo-ask-send"
          aria-label="Send question"
          disabled={!input.trim() || isStreaming || capReached}
        >
          <IconSend size={18} />
          <span>Send</span>
        </button>
      </form>

      <TurnMeter used={assistantTurnCount} max={MAX_ASSISTANT_TURNS} />

      {capReached && (
        <div className="demo-ask-upsell" role="status">
          <p className="demo-ask-upsell__body">
            Keep the conversation going — join the waitlist for unlimited
            turns.
          </p>
          <a href="/waitlist" className="demo-gated-cta">
            Join the waitlist
          </a>
        </div>
      )}

      {lastAssistantDone && (
        <GatedActionBar actions={GATED_ACTIONS.ask} />
      )}
    </div>
  );
}

interface ChatBubbleProps {
  turn: AskTurn;
}

/**
 * Memoized so that streaming tokens arriving into one bubble don't cause
 * prior finished bubbles to re-render (every `setTurns` returns a new
 * array but the other turn objects are identity-preserved by the
 * `.map(t => t.id === ... ? {...t, content: ...} : t)` pattern).
 */
const ChatBubble = memo(function ChatBubble({ turn }: ChatBubbleProps) {
  const isUser = turn.role === 'user';
  const classes = [
    'demo-ask-bubble',
    isUser ? 'demo-ask-bubble--user' : 'demo-ask-bubble--assistant',
    turn.status === 'streaming' ? 'demo-ask-bubble--streaming' : '',
  ]
    .filter(Boolean)
    .join(' ');
  return (
    <div className={classes}>
      {isUser ? (
        <p className="demo-ask-bubble__text">{turn.content}</p>
      ) : turn.status === 'error' ? (
        <p className="demo-ask-bubble__error" role="alert">
          {turn.error ?? 'Something went wrong. Please try again.'}
        </p>
      ) : (
        <StreamingMarkdown
          content={turn.content}
          isStreaming={turn.status === 'streaming'}
          className="demo-ask-bubble__md"
        />
      )}
    </div>
  );
});

interface TurnMeterProps {
  used: number;
  max: number;
}

function TurnMeter({ used, max }: TurnMeterProps) {
  const pills = Array.from({ length: max }, (_, i) => i < used);
  return (
    <div
      className="demo-ask-turnmeter"
      role="group"
      aria-label={`${used} of ${max} free turns used`}
    >
      {pills.map((filled, i) => (
        <span
          key={i}
          className={`demo-ask-turnmeter__pill${filled ? ' demo-ask-turnmeter__pill--filled' : ''}`}
          aria-hidden="true"
        />
      ))}
      <span className="demo-ask-turnmeter__label">
        {used} / {max} free turns
      </span>
    </div>
  );
}

export default AskPanel;
