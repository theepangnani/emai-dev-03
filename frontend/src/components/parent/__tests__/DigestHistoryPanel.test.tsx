import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { DigestHistoryPanel } from '../DigestHistoryPanel';
import type { DigestDeliveryLog } from '../../../api/parentEmailDigest';

const mockGetLogs = vi.fn();

vi.mock('../../../api/parentEmailDigest', async () => {
  const actual = await vi.importActual<typeof import('../../../api/parentEmailDigest')>(
    '../../../api/parentEmailDigest',
  );
  return {
    ...actual,
    getLogs: (...args: unknown[]) => mockGetLogs(...args),
  };
});

function makeLog(overrides: Partial<DigestDeliveryLog> = {}): DigestDeliveryLog {
  return {
    id: 1,
    parent_id: 100,
    integration_id: 200,
    email_count: 3,
    digest_content: '<p>Sample digest content</p>',
    digest_length_chars: 27,
    delivered_at: '2026-04-25T08:00:00Z',
    channels_used: 'email,in_app',
    status: 'delivered',
    ...overrides,
  };
}

function renderPanel(
  props: Parameters<typeof DigestHistoryPanel>[0] = {},
  client?: QueryClient,
) {
  const queryClient =
    client ??
    new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return {
    queryClient,
    ...render(<DigestHistoryPanel {...props} />, { wrapper: Wrapper }),
  };
}

describe('DigestHistoryPanel', () => {
  beforeEach(() => {
    mockGetLogs.mockReset();
  });

  it('renders loading state initially', () => {
    // Pending promise — never resolves during this test.
    mockGetLogs.mockReturnValue(new Promise(() => {}));
    renderPanel();
    expect(screen.getByText(/loading history/i)).toBeInTheDocument();
    // S-2: ASCII dots, not unicode ellipsis.
    expect(screen.getByText('Loading history...')).toBeInTheDocument();
  });

  it('renders empty state when API returns []', async () => {
    mockGetLogs.mockResolvedValue({ data: [] });
    renderPanel();
    await waitFor(() => {
      expect(screen.getByText(/no digests delivered yet/i)).toBeInTheDocument();
    });
  });

  it('renders custom emptyState when provided', async () => {
    mockGetLogs.mockResolvedValue({ data: [] });
    renderPanel({ emptyState: 'Custom empty copy here' });
    await waitFor(() => {
      expect(screen.getByText('Custom empty copy here')).toBeInTheDocument();
    });
    expect(screen.queryByText(/no digests delivered yet/i)).not.toBeInTheDocument();
  });

  it('renders 5 log rows when API returns 5 logs (verify limit=5 was passed)', async () => {
    const logs = [1, 2, 3, 4, 5].map((i) =>
      makeLog({ id: i, email_count: i, delivered_at: `2026-04-2${i}T08:00:00Z` }),
    );
    mockGetLogs.mockResolvedValue({ data: logs });
    renderPanel();
    await waitFor(() => {
      expect(screen.getAllByRole('button', { expanded: false })).toHaveLength(5);
    });
    expect(mockGetLogs).toHaveBeenCalledWith({ limit: 5 });
  });

  it('clicking a row header expands it, showing sanitized digest_content', async () => {
    const log = makeLog({
      id: 42,
      digest_content: '<p>Hello <script>alert("xss")</script>world</p>',
    });
    mockGetLogs.mockResolvedValue({ data: [log] });
    renderPanel();
    await waitFor(() => {
      expect(screen.getByRole('button', { expanded: false })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { expanded: false }));
    await waitFor(() => {
      expect(screen.getByRole('button', { expanded: true })).toBeInTheDocument();
    });
    // S-12: DOMPurify is lazy-loaded — sanitized output appears once the import resolves.
    await waitFor(() => {
      expect(screen.getByText(/hello/i)).toBeInTheDocument();
      expect(screen.getByText(/world/i)).toBeInTheDocument();
    });
    expect(document.querySelector('script')).toBeNull();
    // Channels line surfaced.
    expect(screen.getByText(/delivered via:/i)).toBeInTheDocument();
  });

  it('clicking the expanded row again collapses it', async () => {
    const log = makeLog({ id: 7 });
    mockGetLogs.mockResolvedValue({ data: [log] });
    renderPanel();
    await waitFor(() => {
      expect(screen.getByRole('button', { expanded: false })).toBeInTheDocument();
    });
    const header = screen.getByRole('button', { expanded: false });
    fireEvent.click(header);
    await waitFor(() => {
      expect(screen.getByRole('button', { expanded: true })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { expanded: true }));
    await waitFor(() => {
      expect(screen.getByRole('button', { expanded: false })).toBeInTheDocument();
    });
  });

  it('when collapsible + defaultCollapsed=true, list is hidden initially; clicking heading expands it', async () => {
    mockGetLogs.mockResolvedValue({ data: [makeLog({ id: 1 })] });
    renderPanel({ collapsible: true, defaultCollapsed: true, heading: 'Digest History' });
    // Heading button rendered.
    const headingBtn = screen.getByRole('button', { name: /digest history/i });
    expect(headingBtn).toHaveAttribute('aria-expanded', 'false');
    // List should NOT render — even with logs available — because collapsed.
    expect(screen.queryByText(/loading history/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/no digests delivered/i)).not.toBeInTheDocument();
    // Expand.
    fireEvent.click(headingBtn);
    await waitFor(() => {
      expect(headingBtn).toHaveAttribute('aria-expanded', 'true');
    });
    // Log row now visible.
    await waitFor(() => {
      expect(screen.getAllByRole('button').length).toBeGreaterThan(1);
    });
  });

  it('when collapsible=true the heading button toggles aria-expanded correctly', async () => {
    mockGetLogs.mockResolvedValue({ data: [] });
    renderPanel({ collapsible: true, heading: 'Digest History' });
    expect(screen.getByRole('heading', { level: 2, name: /digest history/i })).toBeInTheDocument();
    const headingBtn = screen.getByRole('button', { name: /digest history/i });
    // defaultCollapsed defaults to false → expanded.
    expect(headingBtn).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(headingBtn);
    expect(headingBtn).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(headingBtn);
    expect(headingBtn).toHaveAttribute('aria-expanded', 'true');
  });

  it('StatusBadge renders delivered with green class, partial/failed with red class', async () => {
    const logs = [
      makeLog({ id: 1, status: 'delivered' }),
      makeLog({ id: 2, status: 'partial' }),
      makeLog({ id: 3, status: 'failed' }),
    ];
    mockGetLogs.mockResolvedValue({ data: logs });
    renderPanel();
    await waitFor(() => {
      expect(screen.getByText('delivered')).toBeInTheDocument();
    });
    expect(screen.getByText('delivered')).toHaveClass('dhp-status--delivered');
    expect(screen.getByText('partial')).toHaveClass('dhp-status--failed');
    expect(screen.getByText('failed')).toHaveClass('dhp-status--failed');
  });

  // S-6: description prop
  it('renders description below heading when description prop is provided', async () => {
    mockGetLogs.mockResolvedValue({ data: [] });
    renderPanel({ description: 'These digests cover all your kids.' });
    expect(
      screen.getByText('These digests cover all your kids.'),
    ).toBeInTheDocument();
  });

  it('does not render description when prop omitted', async () => {
    mockGetLogs.mockResolvedValue({ data: [] });
    const { container } = renderPanel();
    expect(container.querySelector('.dhp-description')).toBeNull();
  });

  // S-7: stale expandedLogId reset
  it('resets expandedLogId when the expanded row disappears after a refetch (S-7)', async () => {
    const log42 = makeLog({ id: 42, email_count: 42, digest_content: '<p>Forty-two</p>' });
    const log99 = makeLog({ id: 99, email_count: 99 });
    mockGetLogs.mockResolvedValueOnce({ data: [log42] });
    const { queryClient } = renderPanel();
    await waitFor(() => {
      expect(screen.getByRole('button', { expanded: false })).toBeInTheDocument();
    });
    // Expand id=42.
    fireEvent.click(screen.getByRole('button', { expanded: false }));
    await waitFor(() => {
      expect(screen.getByRole('button', { expanded: true })).toBeInTheDocument();
    });

    // Stage 2: refetch returns logs WITHOUT id=42. Without S-7, expandedLogId
    // stays as 42 (invisible — log42 isn't in the list to render).
    mockGetLogs.mockResolvedValueOnce({ data: [log99] });
    await queryClient.invalidateQueries({ queryKey: ['email-digest', 'logs', 'panel'] });
    await waitFor(() => {
      expect(screen.getByText(/99 emails/i)).toBeInTheDocument();
    });

    // Stage 3: refetch RE-ADDS id=42. WITHOUT S-7, expandedLogId is still 42 →
    // log42 auto-expands (visible regression). WITH S-7, expandedLogId was
    // reset to null when log42 disappeared → log42 renders collapsed.
    mockGetLogs.mockResolvedValueOnce({ data: [log42, log99] });
    await queryClient.invalidateQueries({ queryKey: ['email-digest', 'logs', 'panel'] });
    await waitFor(() => {
      expect(screen.getAllByRole('button', { expanded: false })).toHaveLength(2);
    });
    expect(screen.queryByRole('button', { expanded: true })).not.toBeInTheDocument();
  });

  // S-9: aria-controls on heading button matches list id
  it('aria-controls on heading button matches list element id (S-9)', async () => {
    mockGetLogs.mockResolvedValue({ data: [makeLog({ id: 1 })] });
    renderPanel({ collapsible: true, heading: 'Digest History' });
    const headingBtn = screen.getByRole('button', { name: /digest history/i });
    const controlsId = headingBtn.getAttribute('aria-controls');
    expect(controlsId).toBeTruthy();
    await waitFor(() => {
      const listEl = document.getElementById(controlsId!);
      expect(listEl).not.toBeNull();
      expect(listEl).toHaveClass('dhp-log-list');
    });
  });

  it('aria-controls points to a real element in loading + empty + list states', async () => {
    // Loading state.
    mockGetLogs.mockReturnValueOnce(new Promise(() => {}));
    const { unmount } = renderPanel({ collapsible: true, heading: 'Digest History' });
    const loadingBtn = screen.getByRole('button', { name: /digest history/i });
    const loadingId = loadingBtn.getAttribute('aria-controls')!;
    expect(document.getElementById(loadingId)).not.toBeNull();
    expect(document.getElementById(loadingId)).toHaveClass('dhp-loading');
    unmount();

    // Empty state.
    mockGetLogs.mockResolvedValueOnce({ data: [] });
    renderPanel({ collapsible: true, heading: 'Digest History' });
    const emptyBtn = await screen.findByRole('button', { name: /digest history/i });
    const emptyId = emptyBtn.getAttribute('aria-controls')!;
    await waitFor(() => {
      const el = document.getElementById(emptyId);
      expect(el).not.toBeNull();
      expect(el).toHaveClass('dhp-empty');
    });
  });

  // S-1: staleTime caches results across mounts within the same QueryClient
  it('staleTime caches the query — second mount within window does NOT refetch (S-1)', async () => {
    mockGetLogs.mockResolvedValue({ data: [makeLog({ id: 1 })] });
    const sharedClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 0 }, mutations: { retry: false } },
    });
    const { unmount } = renderPanel({}, sharedClient);
    await waitFor(() => {
      expect(mockGetLogs).toHaveBeenCalledTimes(1);
    });
    unmount();
    // Second mount within staleTime window — no refetch.
    renderPanel({}, sharedClient);
    // Give RQ a tick to potentially refetch.
    await new Promise((r) => setTimeout(r, 50));
    expect(mockGetLogs).toHaveBeenCalledTimes(1);
  });

  // S-12: lazy DOMPurify — Loading content placeholder MUST appear synchronously
  // before the dynamic import resolves. With eager DOMPurify, purify would be
  // set on first render and the placeholder would never appear — making this
  // assertion fail. That's the intended mutation-test guard.
  it('does NOT load DOMPurify until first row expand (S-12 contract)', async () => {
    const log = makeLog({ id: 5, digest_content: '<p>lazy-content</p>' });
    mockGetLogs.mockResolvedValue({ data: [log] });
    renderPanel();
    await waitFor(() => {
      expect(screen.getByRole('button', { expanded: false })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { expanded: false }));

    // Synchronously after click — purify state is still null because dynamic
    // import hasn't resolved yet. The placeholder MUST be visible.
    expect(screen.getByText('Loading content...')).toBeInTheDocument();
    expect(screen.queryByText(/lazy-content/)).not.toBeInTheDocument();

    // Then DOMPurify resolves and the sanitized content replaces the placeholder.
    await waitFor(() => {
      expect(screen.getByText(/lazy-content/)).toBeInTheDocument();
    });
    expect(screen.queryByText('Loading content...')).not.toBeInTheDocument();
  });
});
