/**
 * Email-Digest Dashboard orchestrator (CB-EDIGEST-002 — issue #4594, stripe E6).
 *
 * This is the WIRING component: it fetches the aggregated dashboard payload,
 * routes empty-states to `EmptyStates`, and otherwise composes the building
 * blocks shipped in sibling stripes (DashboardHeader / TodaySection /
 * WeekGrid / ItemDrilldownModal / EmptyStates — E2-E5).
 *
 * NOTE: This file imports sibling components that land in their own PRs.
 * On THIS branch the build will fail until E2-E5 merge into
 * `integrate/cb-edigest-002-mvp`. Tests stub the children via `vi.mock`.
 */
import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import { getDashboard } from '../../../api/parentEmailDigest';
import { emit } from '../../../lib/telemetry';

import { TodaySection } from './TodaySection';
import { WeekGrid } from './WeekGrid';
import { ItemDrilldownModal } from './ItemDrilldownModal';
import { DashboardHeader } from './DashboardHeader';
import { EmptyStates } from './EmptyStates';
import type {
  DashboardResponse,
  DrilldownItem,
  UrgentItem,
  WeekDeadline,
} from './types';

const DASHBOARD_QUERY_KEY = ['parent', 'email-digest', 'dashboard'] as const;

export function DashboardView(): JSX.Element {
  const queryClient = useQueryClient();
  const [selectedItem, setSelectedItem] = useState<DrilldownItem | null>(null);

  const { data, isLoading, isError, refetch, isFetching } = useQuery<DashboardResponse>({
    queryKey: DASHBOARD_QUERY_KEY,
    queryFn: () => getDashboard('today').then((r) => r.data),
  });

  // Fire a single page-view event on mount. This intentionally does NOT
  // include `data` so it doesn't re-fire when the query refetches.
  useEffect(() => {
    emit('dashboard.page_view');
  }, []);

  const closeModal = () => setSelectedItem(null);

  /** Refresh handler wired to DashboardHeader's "Refresh" button. */
  const handleRefresh = () => {
    emit('dashboard.refresh_clicked');
    refetch();
  };

  /** TodaySection click → open drilldown modal pre-populated with the item. */
  const handleItemClick = (item: UrgentItem) => {
    setSelectedItem({ ...item });
    emit('dashboard.item_clicked', { id: item.id });
  };

  /** WeekGrid cell click → open drilldown modal. */
  const handleCellClick = (item: WeekDeadline) => {
    setSelectedItem({
      ...item,
      due_date: null, // WeekGrid bucket carries the day; drilldown shows it via source-email.
    });
    emit('dashboard.cell_clicked', { id: item.id });
  };

  /**
   * Stubs for modal "Mark done" / "Snooze". Real wiring lands in a later
   * stripe — for MVP the modal closes locally and the dashboard query is
   * invalidated so any side-effect (when those endpoints exist) refreshes
   * the view.
   * TODO(CB-EDIGEST-002 Phase 2): wire to backend mutation endpoints.
   */
  const handleMarkDone = (item: DrilldownItem) => {
    emit('dashboard.mark_done', { id: item.id });
    queryClient.invalidateQueries({ queryKey: DASHBOARD_QUERY_KEY });
    closeModal();
  };

  const handleSnooze = (item: DrilldownItem) => {
    emit('dashboard.snooze', { id: item.id });
    queryClient.invalidateQueries({ queryKey: DASHBOARD_QUERY_KEY });
    closeModal();
  };

  if (isLoading) {
    return (
      <div data-testid="dashboard-loading" className="dashboard-loading">
        Loading…
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div data-testid="dashboard-error" className="dashboard-error">
        <p>Couldn't load the dashboard. Please try again.</p>
        <button type="button" onClick={() => refetch()}>
          Retry
        </button>
      </div>
    );
  }

  // Empty-state branch: server-decided variant takes over the whole view.
  if (data.empty_state !== null) {
    return (
      <div data-testid="dashboard-empty" className="dashboard-view">
        <EmptyStates kind={data.empty_state} />
      </div>
    );
  }

  return (
    <div data-testid="dashboard-view" className="dashboard-view">
      <DashboardHeader
        refreshedAt={data.refreshed_at}
        lastDigestAt={data.last_digest_at}
        onRefresh={handleRefresh}
        isRefreshing={isFetching}
      />
      <TodaySection kids={data.kids} onItemClick={handleItemClick} />
      <WeekGrid kids={data.kids} onCellClick={handleCellClick} />
      {selectedItem ? (
        <ItemDrilldownModal
          item={selectedItem}
          onClose={closeModal}
          onMarkDone={handleMarkDone}
          onSnooze={handleSnooze}
        />
      ) : null}
    </div>
  );
}

export default DashboardView;
