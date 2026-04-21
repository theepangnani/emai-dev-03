/**
 * Flash Tutor panel (#3786).
 *
 * Replaces the static 5-card deck with a 3-card **Short Learning Cycle**:
 *   card front → tap to reveal back → self-grade → next card
 *
 * On completion a confetti burst fires and an in-panel waitlist upsell
 * replaces the grade controls. All state lives in this component (no
 * backend writes) — `useDemoGameState` is driven via `gameActions` props
 * for XP, streak, and achievement side-effects. See §6.135.6 in
 * requirements/features-part7.md.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { PanelFrame } from './panelShared';
import type { DemoPanelProps, PanelStreamState } from './panelTypes';
import { FlashcardDeck, parseFlashcardsFromRaw } from '../FlashcardDeck';
import { FlashCycleCard } from './flash/FlashCycleCard';
import { GradeButtons, type GradeValue } from './flash/GradeButtons';
import { MasteryRing } from './flash/MasteryRing';
import { IconArrowRight } from '../icons';
import type { DemoGameActions } from '../gamification/useDemoGameState';

interface CycleRunnerProps {
  state: PanelStreamState;
  gameActions?: DemoGameActions;
}

const GRADE_XP: Record<GradeValue, number> = {
  missed: 5,
  almost: 10,
  got_it: 15,
};

const GRADE_DOT_CLASS: Record<GradeValue, string> = {
  missed: 'demo-flash-trail-dot--missed',
  almost: 'demo-flash-trail-dot--almost',
  got_it: 'demo-flash-trail-dot--got-it',
};

const GRADE_LABEL: Record<GradeValue, string> = {
  missed: 'Missed',
  almost: 'Almost',
  got_it: 'Got it',
};

const CONFETTI_COUNT = 40;
const CONFETTI_DURATION_MS = 1600;
const ADVANCE_DELAY_MS = 500;

const CONFETTI_COLORS = [
  'var(--color-accent)',
  'var(--color-accent-warm)',
  'var(--color-success)',
  'var(--color-danger)',
] as const;

interface ConfettiParticle {
  id: number;
  left: number;
  delay: number;
  duration: number;
  rotate: number;
  color: string;
}

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false;
  }
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function buildConfetti(): ConfettiParticle[] {
  const particles: ConfettiParticle[] = [];
  for (let i = 0; i < CONFETTI_COUNT; i += 1) {
    particles.push({
      id: i,
      left: Math.random() * 100,
      delay: Math.random() * 300,
      duration: 900 + Math.random() * 700,
      rotate: Math.random() * 360,
      color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
    });
  }
  return particles;
}

/**
 * Inner runner — owns card index / flip / grades / completion UI.
 * Extracted from FlashTutorPanel so it remounts cleanly on each new
 * generation (keyed on state.output so a fresh generation resets all
 * cycle state).
 */
function CycleRunner({ state, gameActions }: CycleRunnerProps) {
  const cards = useMemo(() => {
    if (state.status === 'streaming') return null;
    return parseFlashcardsFromRaw(state.output);
  }, [state.output, state.status]);

  const total = cards?.length ?? 0;

  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [grades, setGrades] = useState<GradeValue[]>([]);
  const [advancing, setAdvancing] = useState(false);
  const [confetti, setConfetti] = useState<ConfettiParticle[] | null>(null);
  const hasFiredBullseyeRef = useRef(false);
  const hasMarkedQuestRef = useRef(false);
  const hasFiredWarmupRef = useRef(false);
  const advanceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const confettiTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Clean up any pending timers on unmount.
  useEffect(() => {
    return () => {
      if (advanceTimerRef.current) clearTimeout(advanceTimerRef.current);
      if (confettiTimerRef.current) clearTimeout(confettiTimerRef.current);
    };
  }, []);

  if (state.status === 'streaming') {
    // Reuse the existing streaming placeholder from FlashcardDeck for
    // visual parity with the other panels.
    return <FlashcardDeck rawText={state.output} isStreaming />;
  }

  if (!cards || cards.length === 0) {
    // Fallback: if Haiku returned something unparseable, show the raw
    // block inside the same pre fallback FlashcardDeck uses.
    return <FlashcardDeck rawText={state.output} />;
  }

  const done = grades.length >= total;
  const current = cards[Math.min(index, cards.length - 1)];

  const handleFlip = () => {
    if (flipped || advancing) return;
    setFlipped(true);
  };

  const handleGrade = (grade: GradeValue) => {
    if (advancing || done) return;
    const nextGrades = [...grades, grade];
    setGrades(nextGrades);
    setAdvancing(true);

    // Fire XP + streak side-effects.
    if (gameActions) {
      gameActions.awardXP(GRADE_XP[grade]);
      if (grade === 'got_it') {
        gameActions.incrementStreak();
        if (!hasFiredBullseyeRef.current) {
          hasFiredBullseyeRef.current = true;
          gameActions.earnAchievement('bullseye');
        }
        // Two consecutive got_it grades → Warming Up achievement (fires
        // once per session). §6.135.8 also defines Warming Up at the
        // tabs-touched layer; follow-up #3795 reconciles the two.
        const last = nextGrades[nextGrades.length - 1];
        const prev = nextGrades[nextGrades.length - 2];
        if (
          !hasFiredWarmupRef.current &&
          last === 'got_it' &&
          prev === 'got_it'
        ) {
          hasFiredWarmupRef.current = true;
          gameActions.earnAchievement('warmup');
        }
      } else {
        gameActions.resetStreak();
      }
    }

    if (nextGrades.length >= total) {
      // Cycle complete.
      if (gameActions && !hasMarkedQuestRef.current) {
        hasMarkedQuestRef.current = true;
        gameActions.markQuest('flash_tutor');
      }
      // Confetti (skip when reduced motion).
      if (!prefersReducedMotion()) {
        const particles = buildConfetti();
        setConfetti(particles);
        confettiTimerRef.current = setTimeout(() => {
          setConfetti(null);
        }, CONFETTI_DURATION_MS);
      }
      setAdvancing(false);
      return;
    }

    // Advance to next card after a short pause.
    advanceTimerRef.current = setTimeout(() => {
      setIndex((i) => i + 1);
      setFlipped(false);
      setAdvancing(false);
    }, ADVANCE_DELAY_MS);
  };

  const gotItCount = grades.filter((g) => g === 'got_it').length;

  return (
    <div className="demo-flash-cycle">
      <div className="demo-flash-cycle-header">
        <MasteryRing completed={grades.length} total={total} />
        <div
          className="demo-flash-trail"
          role="list"
          aria-label="Mastery trail"
        >
          {Array.from({ length: total }).map((_, i) => {
            const grade = grades[i];
            const cls = grade
              ? `demo-flash-trail-dot ${GRADE_DOT_CLASS[grade]}`
              : 'demo-flash-trail-dot demo-flash-trail-dot--empty';
            return (
              <span
                key={i}
                role="listitem"
                className={cls}
                aria-label={
                  grade
                    ? `Card ${i + 1}: ${GRADE_LABEL[grade]}`
                    : `Card ${i + 1}: pending`
                }
              />
            );
          })}
        </div>
      </div>

      {!done && (
        <>
          <FlashCycleCard
            key={index}
            front={current.front}
            back={current.back}
            flipped={flipped}
            onFlip={handleFlip}
            index={index + 1}
            total={total}
          />

          {flipped && (
            <GradeButtons onGrade={handleGrade} disabled={advancing} />
          )}
        </>
      )}

      {confetti && (
        <div className="demo-flash-confetti" aria-hidden="true">
          {confetti.map((p) => (
            <span
              key={p.id}
              className="demo-flash-confetti__piece"
              style={{
                left: `${p.left}%`,
                background: p.color,
                animationDelay: `${p.delay}ms`,
                animationDuration: `${p.duration}ms`,
                transform: `rotate(${p.rotate}deg)`,
              }}
            />
          ))}
        </div>
      )}

      {done && (
        <div
          className="demo-flash-completion"
          role="status"
        >
          <h4 className="demo-flash-completion__headline">
            Nice run — you mastered {gotItCount} of {total}.
          </h4>
          <p className="demo-flash-completion__body">
            Save your streak and unlock adaptive Flash Tutor sessions —
            join the waitlist for early access.
          </p>
          <a className="demo-flash-completion__cta" href="/waitlist">
            <span>Join the waitlist</span>
            <IconArrowRight size={16} aria-hidden />
          </a>
        </div>
      )}
    </div>
  );
}

export function FlashTutorPanel({
  state,
  onGenerate,
  generateDisabled,
  gameActions,
}: DemoPanelProps) {
  // Key the runner on the done-output identity so a fresh generation
  // resets cycle state, but streaming token arrivals do NOT remount the
  // runner (which would clobber grade progress). While streaming, all
  // tokens collapse to the same "streaming" key.
  const runnerKey =
    state.status === 'done' ? `done:${state.output.length}` : `live:${state.status}`;

  return (
    <PanelFrame
      demoType="flash_tutor"
      state={state}
      onGenerate={onGenerate}
      generateDisabled={generateDisabled}
      renderOutput={(s) => (
        <CycleRunner key={runnerKey} state={s} gameActions={gameActions} />
      )}
    />
  );
}

export default FlashTutorPanel;
