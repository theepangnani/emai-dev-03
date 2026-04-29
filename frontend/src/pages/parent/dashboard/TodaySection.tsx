/**
 * E6_PLACEHOLDER (CB-EDIGEST-002 #4594).
 *
 * This file exists ONLY so the E6 wiring stripe can build + test on its own
 * branch via `vi.mock('./TodaySection', ...)`. The real implementation ships
 * in sibling stripe E2; the integration merge into
 * `integrate/cb-edigest-002-mvp` will REPLACE this file with the real one.
 *
 * Do NOT add behavior here — see E2 PR for the real component.
 */
import type { KidSection, UrgentItem } from './types';

export interface TodaySectionProps {
  kids: KidSection[];
  onItemClick: (item: UrgentItem) => void;
}

export function TodaySection(props: TodaySectionProps): JSX.Element {
  // Intentionally minimal — see file header.
  void props;
  return <div data-testid="today-section-placeholder" />;
}

export default TodaySection;
