/**
 * E6_PLACEHOLDER (CB-EDIGEST-002 #4594).
 *
 * Placeholder for sibling stripe E3 (`WeekGrid`). The integration merge into
 * `integrate/cb-edigest-002-mvp` will REPLACE this file with the real
 * implementation. Do NOT add behavior here.
 */
import type { KidSection, WeekDeadline } from './types';

export interface WeekGridProps {
  kids: KidSection[];
  onCellClick: (item: WeekDeadline) => void;
}

export function WeekGrid(props: WeekGridProps): JSX.Element {
  // Intentionally minimal — see file header.
  void props;
  return <div data-testid="week-grid-placeholder" />;
}

export default WeekGrid;
