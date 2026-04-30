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

import {
  getDashboard,
  listIntegrations,
  triggerSync,
} from '../../../api/parentEmailDigest';
import { emit } from '../../../lib/telemetry';
import { useAuth } from '../../../context/AuthContext';

import { TodaySection } from './TodaySection';
import { WeekGrid } from './WeekGrid';
import { ItemDrilldownModal } from './ItemDrilldownModal';
import { DashboardHeader } from './DashboardHeader';
import { EmptyStates } from './EmptyStates';
import type {
  DashboardResponse,
  DayBucket,
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
  // #4628: backend currently returns `{day, items}` only — derive `weekday`
  // and `is_past` client-side so WeekGrid styles past days correctly. ISO
  // date string comparison works because both `day` and `todayKey` are
  // YYYY-MM-DD lexicographically sortable.
  const weekGridKids = useMemo(() => {
    if (!data) return [];
    const todayKey = new Date().toISOString().slice(0, 10);
    return data.kids.map((k: KidSection) => ({
      id: k.id,
      first_name: k.first_name,
      days: k.weekly_deadlines.map((d) => {
        // Defensive: types declare `weekday` + `is_past` required, but the
        // backend ships `{day, items}` only today (#4628). Fill in client-side.
        const raw = d as Partial<DayBucket> & Pick<DayBucket, 'day' | 'items'>;
        const weekday =
          raw.weekday && raw.weekday.trim()
            ? raw.weekday
            : new Date(raw.day + 'T00:00').toLocaleDateString('en-US', {
                weekday: 'short',
              });
        const is_past =
          typeof raw.is_past === 'boolean' ? raw.is_past : raw.day < todayKey;
        return {
          day: raw.day,
          items: raw.items,
          weekday,
          is_past,
        };
      }),
    }));
  }, [data]);

  const closeModal = () => setSelectedItem(null);

  const handleRefresh = async () => {
    emit('dashboard.refresh_clicked');
    // #4629 / PRD §F4: refresh must pull Gmail before re-rendering the
    // snapshot, otherwise we just re-read the same DB rows. Trigger a sync
    // for every active (non-paused) integration first; sync failures must
    // NOT block the refetch — fall back to whatever's already in the DB.
    try {
      const { data: integrations } = await listIntegrations();
      const now = new Date();
      const activeIntegrations = integrations.filter(
        (i) =>
          i.is_active && (!i.paused_until || new Date(i.paused_until) <= now),
      );
      await Promise.all(
        activeIntegrations.map((i) =>
          triggerSync(i.id).catch((err) => {
            // Per-integration failure shouldn't take down the whole refresh.
            console.warn('refresh: triggerSync failed', i.id, err);
          }),
        ),
      );
    } catch (e) {
      console.warn('refresh: listIntegrations failed', e);
    }
    await refetch();
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
