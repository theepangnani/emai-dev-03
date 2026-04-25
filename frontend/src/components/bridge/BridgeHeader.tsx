/**
 * CB-BRIDGE-001 — Bridge re-skin header (#4105).
 *
 * PR 1: presentational header for the My Kids page. Stats are passed in
 * by the parent so this component is pure. Subsequent PRs add the kid
 * rail, hero, and management grid under the same `.bridge-page` scope.
 */
interface BridgeHeaderProps {
  kidsLinked: number;
  classesTracked: number;
  activeTasks: number;
}

export function BridgeHeader({ kidsLinked, classesTracked, activeTasks }: BridgeHeaderProps) {
  const linkedLabel = kidsLinked === 1 ? '1 kid linked' : `${kidsLinked} kids linked`;

  return (
    <section className="bridge-header" aria-labelledby="bridge-title">
      <div>
        <span className="bridge-kicker">Parent Hub · {linkedLabel}</span>
        <h1 id="bridge-title" className="bridge-title">
          Bridge<em>.</em>
        </h1>
        <svg className="bridge-arch" viewBox="0 0 320 40" aria-hidden="true">
          <path
            d="M2 36 Q160 -16 318 36"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinecap="round"
          />
          <circle cx="2" cy="36" r="2.5" fill="currentColor" />
          <circle cx="80" cy="20" r="2" fill="currentColor" />
          <circle cx="160" cy="12" r="2.5" fill="currentColor" />
          <circle cx="240" cy="20" r="2" fill="currentColor" />
          <circle cx="318" cy="36" r="2.5" fill="currentColor" />
        </svg>
        <p className="bridge-lede">
          Where you meet every class, teacher, digest, and update — one hub, one structure, per kid.
        </p>
      </div>

      <div className="bridge-stats" role="list">
        <div className="bridge-stat" role="listitem">
          <span className="bridge-stat-num">{kidsLinked}</span>
          <span className="bridge-stat-label">Kids linked</span>
        </div>
        <div className="bridge-stat" role="listitem">
          <span className="bridge-stat-num">{classesTracked}</span>
          <span className="bridge-stat-label">Classes tracked</span>
        </div>
        <div className="bridge-stat" role="listitem">
          <span className="bridge-stat-num">{activeTasks}</span>
          <span className="bridge-stat-label">Active tasks</span>
        </div>
      </div>
    </section>
  );
}
