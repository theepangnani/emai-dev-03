/**
 * CycleProgress — horizontal rail of pill-shaped dots, one per chunk
 * (CB-TUTOR-002 #4069).
 *
 * The MasteryRing (lifted from the demo) sits on the right as a compact
 * mastery indicator. Each rail pill maps to a chunk and picks up one of
 * four warm-accent tones so progress is both positional AND chromatic —
 * mirroring the teach block's accent rotation.
 */
import { MasteryRing } from './MasteryRing';

export interface CycleProgressProps {
  /** Total number of chunks in the session. */
  total: number;
  /** Zero-based index of the current chunk. */
  currentIndex: number;
  /** Number of chunks fully completed (user moved past). */
  completed: number;
}

export function CycleProgress({
  total,
  currentIndex,
  completed,
}: CycleProgressProps) {
  const pills = Array.from({ length: total }, (_, i) => i);
  return (
    <div className="cycle-progress" aria-label="Learning cycle progress">
      <ol className="cycle-progress__rail">
        {pills.map((i) => {
          const state =
            i < completed ? 'done' : i === currentIndex ? 'current' : 'upcoming';
          const accentIdx = (i % 4) + 1;
          return (
            <li
              key={i}
              className={`cycle-progress__pill cycle-progress__pill--${state} cycle-accent-${accentIdx}`}
              aria-current={i === currentIndex ? 'step' : undefined}
            >
              <span className="cycle-visually-hidden">
                Chunk {i + 1} {state === 'done' ? 'completed' : state === 'current' ? 'in progress' : 'upcoming'}
              </span>
            </li>
          );
        })}
      </ol>
      <MasteryRing completed={completed} total={total} size={52} strokeWidth={5} />
    </div>
  );
}

export default CycleProgress;
