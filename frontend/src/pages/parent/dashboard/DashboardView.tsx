/**
 * Email-Digest Dashboard orchestrator (CB-EDIGEST-002 — issue #4594, stripe E6).
 *
 * This is the WIRING component: it fetches the aggregated dashboard payload,
 * routes empty-states to `EmptyStates`, and otherwise composes the building
 * blocks shipped in sibling stripes (DashboardHeader / TodaySection /
 * WeekGrid / ItemDrilldownModal / EmptyStates — E2-E5).
 *
 * Tests stub the children via `vi.mock`.
 */
import { useEffect, useMemo, useState } from 'react';
import type { JSX } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import { getDashboard } from '../../../api/parentEmailDigest';
import { emit } from '../../../lib/telemetry';
import { useAuth } from '../../../context/AuthContext';

import { TodaySection } from './TodaySection';
import { WeekGrid } from './WeekGrid';
import { ItemDrilldownModal } from './ItemDrilldownModal';
import { DashboardHeader } from './DashboardHeader';
import { EmptyStates } from './EmptyStates';
import type {
  DashboardResponse,
  DrilldownItem,
  KidSection,
  UrgentItem,
} from './types';

const DASHBOARD_QUERY_KEY = ['parent', 'email-digest', 'dashboard'] as const;

export function DashboardView(): JSX.Element {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [selectedItem, setSelectedItem] = useState<DrilldownItem | null>(null);

  const { data, isLoading, isError, refetch, isFetching } = useQuery<DashboardResponse>({
    queryKey: DASHBOARD_QUERY_KEY,
    queryFn: () => getDashboard('today').then((r) => r.data),
  });

  // Fire a single page-view event on mount.
  useEffect(() => {
    emit('dashboard.page_view');
  }, []);

  // Adapt KidSection[] → KidWeekRow[] shape that <WeekGrid> expects.
  // (KidSection has `weekly_deadlines`; KidWeekRow uses `days` for the same data.)
  const weekGridKids = useMemo(() => {
    if (!data) return [];
    return data.kids.map((k: KidSection) => ({
      id: k.id,
      first_name: k.first_name,
      days: k.weekly_deadlines,
    }));
  }, [data]);

  const closeModal = () => setSelectedItem(null);

  const handleRefresh = () => {
    emit('dashboard.refresh_clicked');
    refetch();
  };

  // TodaySection: (kid_id, item|null). null fires when "And N more →" CTA clicked.
  const handleItemClick = (_kidId: number, item: UrgentItem | null) => {
    if (item === null) return; // "And N more" — Phase 2 will navigate to a list view.
    setSelectedItem({ ...item });
    emit('dashboard.item_clicked', { id: item.id });
  };

  // WeekGrid: (kid_id, day). Day-bucket click — Phase 2 will open a per-day list.
  const handleCellClick = (kidId: number, day: { day: string; items: { id: string }[] }) => {
    if (day.items.length === 0) return;
    emit('dashboard.cell_clicked', { kid_id: kidId, day: day.day });
    // For MVP, open the first item in the day bucket.
    // Phase 2: drilldown modal handles a list view.
    const first = day.items[0];
    setSelectedItem({
      id: first.id,
      title: (first as { title?: string }).title ?? '',
      due_date: day.day,
      course_or_context: (first as { course_or_context?: string | null }).course_or_context ?? null,
      source_email_id: (first as { source_email_id?: string }).source_email_id ?? '',
    });
  };

  // Modal Mark done / Snooze — wire to backend in Phase 2 (#4603).
  // For MVP, close modal locally + invalidate query so a future endpoint refresh works.
  const handleMarkDone = async (itemId: string): Promise<void> => {
    emit('dashboard.mark_done', { id: itemId });
    queryClient.invalidateQueries({ queryKey: DASHBOARD_QUERY_KEY });
    closeModal();
  };

  const handleSnooze = async (itemId: string, days: number): Promise<void> => {
    emit('dashboard.snooze', { id: itemId, days });
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
        <EmptyStates kind={data.empty_state} onRefresh={handleRefresh} />
      </div>
    );
  }

  const parentFirstName = user?.full_name?.split(' ')[0] ?? '';

  return (
    <div data-testid="dashboard-view" className="dashboard-view">
      <DashboardHeader
        parentName={parentFirstName}
        lastRefreshedAt={data.refreshed_at}
        isRefreshing={isFetching}
        onRefresh={handleRefresh}
      />
      <TodaySection kids={data.kids} onItemClick={handleItemClick} />
      <WeekGrid kids={weekGridKids} onCellClick={handleCellClick} />
      <ItemDrilldownModal
        open={selectedItem !== null}
        item={selectedItem}
        onClose={closeModal}
        onMarkDone={handleMarkDone}
        onSnooze={handleSnooze}
      />
    </div>
  );
}

export default DashboardView;
