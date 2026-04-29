/**
 * E6_PLACEHOLDER (CB-EDIGEST-002 #4594).
 *
 * Placeholder for sibling stripe E5 (`EmptyStates`). The integration merge
 * into `integrate/cb-edigest-002-mvp` will REPLACE this file with the real
 * implementation. Do NOT add behavior here.
 */
import type { EmptyStateKind } from './types';

export interface EmptyStatesProps {
  kind: EmptyStateKind;
}

export function EmptyStates(props: EmptyStatesProps): JSX.Element {
  // Intentionally minimal — see file header.
  void props;
  return <div data-testid="empty-states-placeholder" />;
}

export default EmptyStates;
