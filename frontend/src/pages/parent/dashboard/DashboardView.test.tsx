/**
 * Tests for DashboardView orchestrator (CB-EDIGEST-002 — #4594, stripe E6).
 *
 * Sibling components (TodaySection, WeekGrid, ItemDrilldownModal,
 * DashboardHeader, EmptyStates) ship in their own stripes — we stub them
 * here via `vi.mock` so this stripe is independently verifiable.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../../test/helpers';
import type { DashboardResponse } from './types';

/* ── Mock useAuth (DashboardView reads parent name for greeting) ── */

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, full_name: 'Test Parent', role: 'parent' },
  }),
}));

/* ── Mock the API module ─────────────────────────────────── */

const mockGetDashboard = vi.fn();

// Use `vi.importActual` + spread (mock-shadow guard, #4277): mocking the
// whole module would shadow every other export to `undefined` the moment a
// future stripe imports a second symbol from `parentEmailDigest` here.
vi.mock('../../../api/parentEmailDigest', async () => {
  const actual = await vi.importActual<typeof import('../../../api/parentEmailDigest')>(
    '../../../api/parentEmailDigest',
  );
  return {
    ...actual,
    getDashboard: (...args: unknown[]) => mockGetDashboard(...args),
  };
});

/* ── Stub sibling components (E2-E5 ship in parallel PRs) ── */

vi.mock('./TodaySection', () => ({
  TodaySection: ({
    kids,
    onItemClick,
  }: {
    kids: { id: number; first_name: string; urgent_items: { id: string; title: string }[] }[];
    onItemClick: (kid_id: number, item: { id: string; title: string } | null) => void;
  }) => (
    <div data-testid="mock-today">
      {kids.map((k) =>
        k.urgent_items.map((it) => (
          <button
            key={it.id}
            type="button"
            data-testid={`mock-today-item-${it.id}`}
            onClick={() => onItemClick(k.id, it as never)}
          >
            {it.title}
          </button>
        )),
      )}
    </div>
  ),
}));

vi.mock('./WeekGrid', () => ({
  WeekGrid: () => <div data-testid="mock-week" />,
}));

vi.mock('./DashboardHeader', () => ({
  DashboardHeader: ({ onRefresh }: { onRefresh: () => void }) => (
    <div data-testid="mock-header">
      <button type="button" data-testid="mock-refresh" onClick={onRefresh}>
        Refresh
      </button>
    </div>
  ),
}));

vi.mock('./ItemDrilldownModal', () => ({
  ItemDrilldownModal: ({
    open,
    item,
    onClose,
    onMarkDone,
  }: {
    open: boolean;
    item: { id: string; title: string } | null;
    onClose: () => void;
    onMarkDone: (item_id: string) => Promise<void>;
  }) => {
    if (!open || !item) return null;
    return (
      <div data-testid="mock-modal" data-item-id={item.id}>
        <span data-testid="mock-modal-title">{item.title}</span>
        <button type="button" data-testid="mock-modal-close" onClick={onClose}>
          Close
        </button>
        <button
          type="button"
          data-testid="mock-modal-mark-done"
          onClick={() => onMarkDone(item.id)}
        >
          Mark done
        </button>
      </div>
    );
  },
}));

vi.mock('./EmptyStates', () => ({
  EmptyStates: ({ kind }: { kind: string }) => (
    <div data-testid="mock-empty" data-kind={kind} />
  ),
}));

/* Pull in DashboardView AFTER vi.mock declarations so the mocks bind. */
import { DashboardView } from './DashboardView';

/* ── Fixtures ────────────────────────────────────────────── */

function makeResponse(overrides: Partial<DashboardResponse> = {}): DashboardResponse {
  return {
    kids: [
      {
        id: 1,
        first_name: 'Alex',
        urgent_items: [
          {
            id: 'u1',
            title: 'Math homework due',
            due_date: '2026-04-29',
            course_or_context: 'Math 7',
            source_email_id: 'e1',
          },
        ],
        weekly_deadlines: [],
        all_clear: false,
      },
    ],
    empty_state: null,
    refreshed_at: '2026-04-28T12:00:00Z',
    last_digest_at: '2026-04-28T07:00:00Z',
    ...overrides,
  };
}

/* ── Tests ───────────────────────────────────────────────── */

describe('DashboardView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    if (typeof window !== 'undefined') {
      window.__cb_telemetry__ = [];
    }
  });

  it('shows a loading state then renders the kid grid', async () => {
    mockGetDashboard.mockReturnValue(
      new Promise((resolve) => {
        setTimeout(() => resolve({ data: makeResponse() }), 0);
      }),
    );

    renderWithProviders(<DashboardView />);

    expect(screen.getByTestId('dashboard-loading')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-view')).toBeInTheDocument();
    });
    expect(screen.getByTestId('mock-header')).toBeInTheDocument();
    expect(screen.getByTestId('mock-today')).toBeInTheDocument();
    expect(screen.getByTestId('mock-week')).toBeInTheDocument();
    expect(mockGetDashboard).toHaveBeenCalledWith('today');
  });

  it('renders EmptyStates with the server-provided kind when empty_state is non-null', async () => {
    mockGetDashboard.mockResolvedValue({
      data: makeResponse({ empty_state: 'calm', kids: [] }),
    });

    renderWithProviders(<DashboardView />);

    await waitFor(() => {
      expect(screen.getByTestId('mock-empty')).toBeInTheDocument();
    });
    expect(screen.getByTestId('mock-empty').getAttribute('data-kind')).toBe('calm');
    expect(screen.queryByTestId('mock-today')).not.toBeInTheDocument();
    expect(screen.queryByTestId('mock-week')).not.toBeInTheDocument();
  });

  it('opens the drilldown modal when an item is clicked in TodaySection', async () => {
    mockGetDashboard.mockResolvedValue({ data: makeResponse() });

    renderWithProviders(<DashboardView />);

    await waitFor(() => {
      expect(screen.getByTestId('mock-today-item-u1')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('mock-today-item-u1'));

    expect(screen.getByTestId('mock-modal')).toBeInTheDocument();
    expect(screen.getByTestId('mock-modal').getAttribute('data-item-id')).toBe('u1');
    expect(screen.getByTestId('mock-modal-title')).toHaveTextContent('Math homework due');
  });

  it('Mark done in the modal closes it and invalidates the dashboard query', async () => {
    mockGetDashboard.mockResolvedValue({ data: makeResponse() });

    const { queryClient } = renderWithProviders(<DashboardView />);
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    await waitFor(() => {
      expect(screen.getByTestId('mock-today-item-u1')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('mock-today-item-u1'));
    expect(screen.getByTestId('mock-modal')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('mock-modal-mark-done'));

    await waitFor(() => {
      expect(screen.queryByTestId('mock-modal')).not.toBeInTheDocument();
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ['parent', 'email-digest', 'dashboard'],
    });
  });

  it('emits dashboard.page_view on mount', async () => {
    mockGetDashboard.mockResolvedValue({ data: makeResponse() });

    renderWithProviders(<DashboardView />);

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-view')).toBeInTheDocument();
    });

    const events = window.__cb_telemetry__ ?? [];
    expect(events.some((e) => e.event === 'dashboard.page_view')).toBe(true);
    // Mutation-test guard: `page_view` must fire exactly once per mount, not
    // re-fire on refetch. Catches regressions where the emit() is moved out
    // of the empty-deps effect and accidentally double-fires.
    const pageViewEvents = events.filter((e) => e.event === 'dashboard.page_view');
    expect(pageViewEvents).toHaveLength(1);
  });

  it('renders an error state when the request fails', async () => {
    mockGetDashboard.mockRejectedValue(new Error('boom'));

    renderWithProviders(<DashboardView />);

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-error')).toBeInTheDocument();
    });
  });
});
