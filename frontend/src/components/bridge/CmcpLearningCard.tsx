/**
 * CB-CMCP-001 M3-C 3C-4 (#4587) — Bridge "What [child] is learning" card.
 *
 * Renders up to 5 recent CMCP artifacts (APPROVED + SELF_STUDY) for the
 * currently selected kid. Each item shows a subject chip, content-type
 * marker, topic title, and a clickable affordance:
 *
 * - When ``parent_companion_available`` is true, "Open" routes to the
 *   Parent Companion page (``/parent/companion/:artifact_id``).
 * - Otherwise the click is a no-op (M3α minimum) — the generic detail
 *   route lands in M3β / a follow-up stripe.
 *
 * SELF_STUDY rows render the shared ``<SelfStudyBadge />`` (sibling
 * stripe 3B-2) inline so parents see the "AI-generated, not
 * teacher-approved" warning.
 *
 * Visual treatment uses the existing CB-BRIDGE-001 ``.bridge-card`` /
 * ``.bridge-item-list`` shells defined in ``BridgePage.css`` so the card
 * matches the rest of the My Hub grid without introducing new tokens.
 */
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  bridgeCmcpCardApi,
  type BridgeCmcpCardItem,
} from '../../api/bridgeCmcpCard';
import { SelfStudyBadge } from '../cmcp/SelfStudyBadge';

interface CmcpLearningCardProps {
  /** ``students.id`` of the currently selected kid. */
  kidId: number;
  /** First-name display for the empty + header copy. */
  kidName: string;
}

const ARTIFACT_TYPE_LABELS: Record<string, string> = {
  study_guide: 'Guide',
  quiz: 'Quiz',
  flashcards: 'Cards',
  worksheet: 'Worksheet',
  weak_area_analysis: 'Weak areas',
  high_level_summary: 'Summary',
  answer_key: 'Answer key',
};

function contentTypeLabel(value: string): string {
  return ARTIFACT_TYPE_LABELS[value] ?? value.replace(/_/g, ' ');
}

export function CmcpLearningCard({ kidId, kidName }: CmcpLearningCardProps) {
  const navigate = useNavigate();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['bridge', 'cmcp-card', kidId],
    queryFn: () => bridgeCmcpCardApi.list(kidId),
    // Only fetch when we have a real kid id selected.
    enabled: Number.isFinite(kidId) && kidId > 0,
    staleTime: 60_000,
  });

  const items: BridgeCmcpCardItem[] = data?.items ?? [];

  const handleOpen = (item: BridgeCmcpCardItem) => {
    if (item.parent_companion_available) {
      navigate(`/parent/companion/${item.artifact_id}`);
    }
    // M3α: when the parent-companion view is not available we leave the
    // click a no-op rather than navigating to a placeholder. A later
    // stripe (or M3β) will land the generic detail route; until then a
    // soft no-op keeps the card honest about what is reachable.
  };

  return (
    <article
      className="bridge-card bridge-card--cmcp-learning"
      data-testid="bridge-cmcp-learning-card"
    >
      <header className="bridge-card-head">
        <div className="bridge-card-title-wrap">
          <span className="bridge-card-kicker">Learning · recent</span>
          <h3>What {kidName} is learning</h3>
          <p className="bridge-card-desc">
            Recent curriculum-aligned guides, quizzes, and parent companions.
          </p>
        </div>
      </header>

      {isLoading ? (
        <div className="bridge-empty-hint">Loading recent learning…</div>
      ) : isError ? (
        <div className="bridge-empty-hint">
          Couldn’t load recent learning right now. Try again in a moment.
        </div>
      ) : items.length === 0 ? (
        <div className="bridge-empty-hint">
          No recent learning to review for {kidName} yet.
        </div>
      ) : (
        <ul className="bridge-item-list" role="list">
          {items.map((item) => {
            const isSelfStudy = item.state === 'SELF_STUDY';
            const clickable = item.parent_companion_available;
            return (
              <li
                key={item.artifact_id}
                className={clickable ? 'is-clickable' : undefined}
                onClick={clickable ? () => handleOpen(item) : undefined}
                data-testid={`bridge-cmcp-item-${item.artifact_id}`}
              >
                <div
                  className={`bridge-mat-type bridge-mat-type--${
                    isSelfStudy ? 'doc' : 'pdf'
                  }`}
                >
                  {contentTypeLabel(item.content_type).toUpperCase()}
                </div>
                <div>
                  <div className="bridge-item-title">{item.topic}</div>
                  <div className="bridge-item-meta">
                    {item.subject ? <span>{item.subject}</span> : <span>—</span>}
                    {isSelfStudy && (
                      <>
                        {' · '}
                        <SelfStudyBadge size="sm" />
                      </>
                    )}
                  </div>
                </div>
                {clickable && (
                  <span className="bridge-item-chev" aria-hidden="true">
                    ›
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </article>
  );
}

export default CmcpLearningCard;
