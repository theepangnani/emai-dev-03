/**
 * CB-CMCP-001 M3-H 3H-1 (#4663) — Coverage heatmap (strand × grade).
 *
 * Renders a strand-by-grade pivot of artifact counts as a coloured grid:
 *   rows = strand codes (Ontario SE third segment, e.g. "A", "B", "C").
 *   cols = grades (integers).
 *   cells = APPROVED artifact count, coloured by bucket:
 *           0   → red   (no coverage)
 *           1-3 → amber (sparse)
 *           4+  → green (covered).
 *
 * Data shape
 * ----------
 * Accepts a precomputed `coverageMap: Record<strand, Record<grade, count>>`
 * — matches the on-wire dict 3E-2's `coverage_map_service` produces. The
 * page derives this dict from the artifact list returned by 3E-1's REST
 * endpoint (see `derive_coverage_map` in BoardDashboardPage) so the same
 * matrix shape works whether the data comes from the dedicated service or
 * from a downstream rebuild on the catalog payload.
 *
 * Empty state
 * -----------
 * If the map has no strands OR every cell is zero, an explicit
 * `data-testid="coverage-heatmap-empty"` card renders instead of the
 * grid — the dashboard differentiates "no artifacts approved yet" from
 * "loading" / "error" via the parent component.
 *
 * No new tokens — reuses the existing CMCP review page palette.
 */
import './CoverageHeatmap.css';

export type CoverageMap = Record<string, Record<number, number>>;

export interface CoverageHeatmapProps {
  /** strand → grade → count. Empty / all-zero → empty-state card. */
  coverageMap: CoverageMap;
}

/** Bucket per #4663 spec: 0=red, 1-3=amber, 4+=green. */
function bucketFor(count: number): 'empty' | 'sparse' | 'covered' {
  if (count <= 0) return 'empty';
  if (count <= 3) return 'sparse';
  return 'covered';
}

export function CoverageHeatmap({ coverageMap }: CoverageHeatmapProps) {
  const strands = Object.keys(coverageMap).sort();

  // Union of grades across all strands so columns line up even when one
  // strand only has artifacts at a subset of grades.
  const gradeSet = new Set<number>();
  for (const strand of strands) {
    for (const grade of Object.keys(coverageMap[strand] ?? {})) {
      const g = Number(grade);
      if (Number.isFinite(g)) gradeSet.add(g);
    }
  }
  const grades = Array.from(gradeSet).sort((a, b) => a - b);

  const totalCount = strands.reduce((acc, strand) => {
    const row = coverageMap[strand] ?? {};
    return (
      acc +
      Object.values(row).reduce((rowAcc, c) => rowAcc + (c ?? 0), 0)
    );
  }, 0);

  // Empty: no strands, no grades, or every cell zero.
  if (strands.length === 0 || grades.length === 0 || totalCount === 0) {
    return (
      <div
        className="coverage-heatmap-empty"
        data-testid="coverage-heatmap-empty"
        role="status"
      >
        <h3>No coverage yet</h3>
        <p>
          This board has no APPROVED artifacts. Once teachers approve
          generated content, the strand × grade coverage will appear here.
        </p>
      </div>
    );
  }

  return (
    <div
      className="coverage-heatmap"
      data-testid="coverage-heatmap"
      role="table"
      aria-label="Strand-by-grade coverage heatmap"
    >
      <div className="coverage-heatmap-header" role="row">
        <div className="coverage-heatmap-corner" role="columnheader">
          Strand \ Grade
        </div>
        {grades.map((g) => (
          <div
            key={`g-${g}`}
            className="coverage-heatmap-col"
            role="columnheader"
          >
            G{g}
          </div>
        ))}
      </div>
      <div className="coverage-heatmap-body">
        {strands.map((strand) => (
          <div
            key={`row-${strand}`}
            className="coverage-heatmap-row"
            role="row"
          >
            <div className="coverage-heatmap-rowhead" role="rowheader">
              {strand}
            </div>
            {grades.map((g) => {
              const count = coverageMap[strand]?.[g] ?? 0;
              const bucket = bucketFor(count);
              return (
                <div
                  key={`cell-${strand}-${g}`}
                  className={`coverage-heatmap-cell coverage-heatmap-cell-${bucket}`}
                  role="cell"
                  data-testid={`coverage-cell-${strand}-${g}`}
                  data-bucket={bucket}
                  data-count={count}
                  aria-label={`Strand ${strand}, grade ${g}: ${count} artifact${count === 1 ? '' : 's'}`}
                  title={`${strand} · G${g} · ${count}`}
                >
                  {count}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <div className="coverage-heatmap-legend" aria-hidden="true">
        <span className="coverage-heatmap-legend-item">
          <span className="coverage-heatmap-swatch coverage-heatmap-swatch-empty" />
          0 (none)
        </span>
        <span className="coverage-heatmap-legend-item">
          <span className="coverage-heatmap-swatch coverage-heatmap-swatch-sparse" />
          1–3 (sparse)
        </span>
        <span className="coverage-heatmap-legend-item">
          <span className="coverage-heatmap-swatch coverage-heatmap-swatch-covered" />
          4+ (covered)
        </span>
      </div>
    </div>
  );
}
