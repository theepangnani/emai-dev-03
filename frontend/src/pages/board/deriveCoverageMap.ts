/**
 * CB-CMCP-001 M3-H 3H-1 (#4663) — strand × grade coverage map derivation.
 *
 * Pure helper extracted out of `BoardDashboardPage` so the page module
 * exports only React components (satisfies `react-refresh/only-export-components`).
 *
 * Mirrors `coverage_map_service._extract_strand_and_grade` on the backend
 * (M3-E 3E-2 / PR #4668): Ontario SE codes are namespaced
 * `<SUBJECT>.<GRADE>.<STRAND>.<...>`, and the strand identity is lifted
 * from the third dotted segment of `se_codes[0]`.
 */
import type { BoardCatalogArtifact } from '../../api/boardCatalog';
import type { CoverageMap } from '../../components/board/CoverageHeatmap';

/**
 * Lift `(strand, grade)` off the first SE code per row.
 *
 * Returns `(null, null)` for rows with no SE codes / malformed shape /
 * non-int grade segment so a single bad row never poisons the map.
 *
 * Prefers the typed `grade` column on the artifact (3E-1 surfaces it
 * derived from the same SE code on the backend) and falls back to the
 * SE-code parse if absent.
 */
function extractStrandAndGrade(
  artifact: BoardCatalogArtifact,
): { strand: string | null; grade: number | null } {
  const seFirst = artifact.se_codes?.[0];
  if (typeof seFirst !== 'string') {
    return { strand: null, grade: null };
  }
  const parts = seFirst.split('.');
  if (parts.length < 3) {
    return { strand: null, grade: null };
  }
  let grade: number | null = null;
  if (typeof artifact.grade === 'number' && Number.isFinite(artifact.grade)) {
    grade = artifact.grade;
  } else {
    const parsed = Number.parseInt(parts[1], 10);
    if (Number.isFinite(parsed)) grade = parsed;
  }
  const strand = parts[2]?.trim() || null;
  if (!strand || grade === null) return { strand: null, grade: null };
  return { strand, grade };
}

/**
 * Build the strand × grade × count map from a list of catalog artifacts.
 *
 * Returns `{}` when no artifact yields a valid (strand, grade) pair.
 */
export function deriveCoverageMap(
  artifacts: BoardCatalogArtifact[],
): CoverageMap {
  const map: CoverageMap = {};
  for (const artifact of artifacts) {
    const { strand, grade } = extractStrandAndGrade(artifact);
    if (strand === null || grade === null) continue;
    if (!map[strand]) map[strand] = {};
    map[strand][grade] = (map[strand][grade] ?? 0) + 1;
  }
  return map;
}
