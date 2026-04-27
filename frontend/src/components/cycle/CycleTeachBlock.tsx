/**
 * CycleTeachBlock — the "teach" phase of a short Learning Cycle chunk
 * (CB-TUTOR-002 #4069).
 *
 * Renders the chunk's markdown lesson with Arc pinned to the top-left. Arc
 * transitions from `thinking` → `happy` while the lesson renders in, so the
 * mascot feels alive instead of static. A prominent "Ready for questions"
 * CTA ends the block.
 *
 * Shell-only — no network calls, no prompt fetches.
 */
import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { ArcMascot, type ArcMood } from '../arc';
import { getArcVariant } from '../arc/util';
import { useAuth } from '../../context/AuthContext';
import type { CycleChunk } from './types';

export interface CycleTeachBlockProps {
  chunk: CycleChunk;
  /** 1-indexed chunk label, e.g. "Chunk 2 of 5". */
  index: number;
  total: number;
  onReady: () => void;
  /**
   * Accent class applied to the block — cycles through four warm tones so
   * each chunk feels visually distinct without adding palette tokens.
   */
  accentClass: string;
}

export function CycleTeachBlock({
  chunk,
  index,
  total,
  onReady,
  accentClass,
}: CycleTeachBlockProps) {
  // Simulate a "teach-in": Arc thinks for a beat, then celebrates once the
  // lesson has rendered. Purely visual — replaces the quick render-flash
  // that felt abrupt on fast machines.
  const [mood, setMood] = useState<ArcMood>('thinking');
  useEffect(() => {
    const t = window.setTimeout(() => setMood('happy'), 900);
    return () => window.clearTimeout(t);
  }, [chunk.order]);

  const { user, isLoading: authLoading } = useAuth();
  const arcVariant = authLoading ? undefined : getArcVariant(user?.id);

  return (
    <section
      className={`cycle-teach ${accentClass}`}
      aria-labelledby={`cycle-teach-heading-${chunk.order}`}
    >
      <div className="cycle-teach__mascot" data-arc={arcVariant}>
        <ArcMascot size={96} mood={mood} glow decorative />
      </div>

      <div className="cycle-teach__body">
        <p className="cycle-teach__eyebrow">
          Chunk {index} of {total}
        </p>
        <h2 id={`cycle-teach-heading-${chunk.order}`} className="cycle-teach__heading">
          Let&apos;s learn this part
        </h2>

        <div className="cycle-teach__markdown">
          <ReactMarkdown>{chunk.teach_content_md}</ReactMarkdown>
        </div>

        <div className="cycle-teach__footer">
          <button
            type="button"
            className="cycle-cta cycle-cta--primary"
            onClick={onReady}
          >
            Ready for questions
            <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path
                d="M6 4l4 4-4 4"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
      </div>
    </section>
  );
}

export default CycleTeachBlock;
