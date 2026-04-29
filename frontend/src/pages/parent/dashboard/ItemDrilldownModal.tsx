/**
 * E6_PLACEHOLDER (CB-EDIGEST-002 #4594).
 *
 * Placeholder for sibling stripe E4 (`ItemDrilldownModal`). The integration
 * merge into `integrate/cb-edigest-002-mvp` will REPLACE this file with
 * the real implementation. Do NOT add behavior here.
 */
import type { DrilldownItem } from './types';

export interface ItemDrilldownModalProps {
  item: DrilldownItem;
  onClose: () => void;
  onMarkDone: (item: DrilldownItem) => void;
  onSnooze: (item: DrilldownItem) => void;
}

export function ItemDrilldownModal(props: ItemDrilldownModalProps): JSX.Element {
  // Intentionally minimal — see file header.
  void props;
  return <div data-testid="item-drilldown-modal-placeholder" />;
}

export default ItemDrilldownModal;
