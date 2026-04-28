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

function renderPanel(props: Parameters<typeof DigestHistoryPanel>[0] = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return render(<DigestHistoryPanel {...props} />, { wrapper: Wrapper });
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
    // Sanitized — script removed but text preserved.
    expect(screen.getByText(/hello/i)).toBeInTheDocument();
    expect(screen.getByText(/world/i)).toBeInTheDocument();
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
});
