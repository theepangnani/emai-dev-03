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
        <span className="bridge-kicker">{linkedLabel}</span>
        <h1 id="bridge-title" className="bridge-title">
          My Hub
        </h1>
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
