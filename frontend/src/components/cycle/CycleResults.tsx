/**
 * CycleResults — end-of-session celebration screen (CB-TUTOR-002 #4069).
 *
 * Shows total XP, overall accuracy, a per-chunk mastery grid, and the two
 * next-step CTAs ("Drill this topic more", "New topic"). Arc celebrates on
 * render.
 */
import { ArcMascot } from '../arc';
import { getArcVariant } from '../arc/util';
import { useAuth } from '../../context/AuthContext';
import type { CycleChunkSummary } from './types';

export interface CycleResultsProps {
  topic: string;
  totalXp: number;
  accuracy: number; // 0..1
  chunkSummaries: CycleChunkSummary[];
  onDrillMore: () => void;
  onNewTopic: () => void;
}

function pct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

export function CycleResults({
  topic,
  totalXp,
  accuracy,
  chunkSummaries,
  onDrillMore,
  onNewTopic,
}: CycleResultsProps) {
  const mastered = chunkSummaries.filter((c) => c.mastered).length;
  const { user, isLoading: authLoading } = useAuth();
  const arcVariant = authLoading ? undefined : getArcVariant(user?.id);
  return (
    <section className="cycle-results" aria-labelledby="cycle-results-heading">
      <div className="cycle-results__hero" data-arc={arcVariant}>
        <ArcMascot size={120} mood="celebrating" glow decorative />
        <div>
          <p className="cycle-results__eyebrow">Cycle complete</p>
          <h2 id="cycle-results-heading" className="cycle-results__heading">
            Great work on {topic}
          </h2>
        </div>
      </div>

      <dl className="cycle-results__stats">
        <div className="cycle-results__stat">
          <dt>Total XP</dt>
          <dd>+{totalXp}</dd>
        </div>
        <div className="cycle-results__stat">
          <dt>Accuracy</dt>
          <dd>{pct(accuracy)}</dd>
        </div>
        <div className="cycle-results__stat">
          <dt>Mastery</dt>
          <dd>
            {mastered}/{chunkSummaries.length}
          </dd>
        </div>
      </dl>

      <div className="cycle-results__map" role="list" aria-label="Chunk mastery">
        {chunkSummaries.map((chunk) => {
          const accentIdx = (chunk.order % 4) + 1;
          return (
            <div
              key={chunk.order}
              role="listitem"
              className={`cycle-results__chunk cycle-accent-${accentIdx} ${
                chunk.mastered ? 'cycle-results__chunk--mastered' : ''
              }`}
            >
              <span className="cycle-results__chunk-label">
                Chunk {chunk.order + 1}
              </span>
              <span className="cycle-results__chunk-score">
                {chunk.correctQuestions}/{chunk.totalQuestions}
              </span>
              {chunk.mastered && (
                <span className="cycle-results__chunk-badge" aria-label="Mastered">
                  ✓
                </span>
              )}
            </div>
          );
        })}
      </div>

      <div className="cycle-results__ctas">
        <button
          type="button"
          className="cycle-cta cycle-cta--primary"
          onClick={onDrillMore}
        >
          Drill this topic more
        </button>
        <button
          type="button"
          className="cycle-cta cycle-cta--secondary"
          onClick={onNewTopic}
        >
          New topic
        </button>
      </div>
    </section>
  );
}

export default CycleResults;
