import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../test/helpers';
import { RecentActivityPanel, formatRelativeTime } from './RecentActivityPanel';
import type { ActivityItem } from '../../api/activity';

/* ── Mock the activity API ──────────────────────────────── */

const mockGetRecent = vi.fn<(studentId?: number, limit?: number) => Promise<ActivityItem[]>>();

vi.mock('../../api/activity', () => ({
  activityApi: {
    getRecent: (...args: any[]) => mockGetRecent(...args),
  },
}));

/* ── Fixtures ───────────────────────────────────────────── */

function createActivity(overrides: Partial<ActivityItem> = {}): ActivityItem {
  return {
    activity_type: 'material_uploaded',
    title: 'Test Activity',
    description: 'A test description',
    resource_type: 'course_content',
    resource_id: 1,
    student_id: null,
    student_name: null,
    created_at: new Date().toISOString(),
    icon_type: 'file-text',
    ...overrides,
  };
}

/* Only material_uploaded and message_received are shown after filter */
const VISIBLE_TYPES: ActivityItem['activity_type'][] = [
  'material_uploaded',
  'message_received',
];

/* ── Tests ──────────────────────────────────────────────── */

describe('RecentActivityPanel', () => {
  const mockNavigate = vi.fn();
  const mockOnToggle = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders loading skeleton initially', () => {
    mockGetRecent.mockReturnValue(new Promise(() => {})); // never resolves
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} collapsed={false} onToggle={mockOnToggle} />,
    );
    const skeletons = screen.getAllByTestId('activity-skeleton');
    expect(skeletons).toHaveLength(3);
  });

  it('renders activity items after fetch', async () => {
    const items = [
      createActivity({ title: 'New Notes', activity_type: 'material_uploaded' }),
      createActivity({ title: 'New message', activity_type: 'message_received' }),
    ];
    mockGetRecent.mockResolvedValue(items);
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} collapsed={false} onToggle={mockOnToggle} />,
    );
    await waitFor(() => {
      expect(screen.getByText('New Notes')).toBeInTheDocument();
      expect(screen.getByText('New message')).toBeInTheDocument();
    });
  });

  it('visible activity types show correct icons', async () => {
    const items = VISIBLE_TYPES.map((type, i) =>
      createActivity({ activity_type: type, title: `Item ${type}`, resource_id: i + 1 }),
    );
    mockGetRecent.mockResolvedValue(items);
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} collapsed={false} onToggle={mockOnToggle} />,
    );
    await waitFor(() => {
      for (const type of VISIBLE_TYPES) {
        expect(screen.getByTestId(`activity-icon-${type}`)).toBeInTheDocument();
      }
    });
  });

  it('filters out non-visible activity types', async () => {
    const items = [
      createActivity({ activity_type: 'course_created', title: 'Should Hide' }),
      createActivity({ activity_type: 'material_uploaded', title: 'Should Show' }),
    ];
    mockGetRecent.mockResolvedValue(items);
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} collapsed={false} onToggle={mockOnToggle} />,
    );
    await waitFor(() => screen.getByText('Should Show'));
    expect(screen.queryByText('Should Hide')).not.toBeInTheDocument();
  });

  it('clicking a material_uploaded row navigates to /course-materials/:id', async () => {
    mockGetRecent.mockResolvedValue([
      createActivity({ activity_type: 'material_uploaded', title: 'Notes', resource_id: 42 }),
    ]);
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} collapsed={false} onToggle={mockOnToggle} />,
    );
    await waitFor(() => screen.getByText('Notes'));
    fireEvent.click(screen.getByTestId('activity-row'));
    expect(mockNavigate).toHaveBeenCalledWith('/course-materials/42');
  });

  it('clicking a message_received row navigates to /messages', async () => {
    mockGetRecent.mockResolvedValue([
      createActivity({ activity_type: 'message_received', title: 'New message' }),
    ]);
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} collapsed={false} onToggle={mockOnToggle} />,
    );
    await waitFor(() => screen.getByText('New message'));
    fireEvent.click(screen.getByTestId('activity-row'));
    expect(mockNavigate).toHaveBeenCalledWith('/messages');
  });

  it('collapsed prop controls content visibility', async () => {
    mockGetRecent.mockResolvedValue([createActivity({ title: 'Item 1' })]);
    const { rerender } = renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} collapsed={true} onToggle={mockOnToggle} />,
    );

    const body = screen.getByTestId('activity-body');
    expect(body).toHaveClass('pd-activity-body-collapsed');

    rerender(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} collapsed={false} onToggle={mockOnToggle} />,
    );
    expect(body).not.toHaveClass('pd-activity-body-collapsed');
  });

  it('clicking header calls onToggle', async () => {
    mockGetRecent.mockResolvedValue([createActivity({ title: 'Item 1' })]);
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} collapsed={false} onToggle={mockOnToggle} />,
    );
    fireEvent.click(screen.getByText(/Recent Activity/));
    expect(mockOnToggle).toHaveBeenCalledTimes(1);
  });

  it('empty state shown when no activities', async () => {
    mockGetRecent.mockResolvedValue([]);
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} collapsed={false} onToggle={mockOnToggle} />,
    );
    await waitFor(() => {
      expect(screen.getByText('No recent activity')).toBeInTheDocument();
    });
  });

  it('child name badge shown when selectedChild is null', async () => {
    mockGetRecent.mockResolvedValue([
      createActivity({ student_name: 'Alice', student_id: 1 }),
    ]);
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} collapsed={false} onToggle={mockOnToggle} />,
    );
    await waitFor(() => {
      expect(screen.getByTestId('activity-child-badge')).toHaveTextContent('Alice');
    });
  });

  it('child name badge hidden when selectedChild is set', async () => {
    mockGetRecent.mockResolvedValue([
      createActivity({ student_name: 'Alice', student_id: 1 }),
    ]);
    renderWithProviders(
      <RecentActivityPanel selectedChild={1} navigate={mockNavigate} collapsed={false} onToggle={mockOnToggle} />,
    );
    await waitFor(() => screen.getByText('Test Activity'));
    expect(screen.queryByTestId('activity-child-badge')).not.toBeInTheDocument();
  });

  it('error state shows retry button and can refetch', async () => {
    mockGetRecent.mockRejectedValueOnce(new Error('Network error'));
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} collapsed={false} onToggle={mockOnToggle} />,
    );
    await waitFor(() => {
      expect(screen.getByText('Unable to load activity')).toBeInTheDocument();
    });
    expect(screen.getByText('Retry')).toBeInTheDocument();

    // Retry succeeds
    mockGetRecent.mockResolvedValueOnce([createActivity({ title: 'After retry' })]);
    fireEvent.click(screen.getByText('Retry'));
    await waitFor(() => {
      expect(screen.getByText('After retry')).toBeInTheDocument();
    });
  });
});

/* ── formatRelativeTime unit tests ──────────────────────── */

describe('formatRelativeTime', () => {
  it('returns "just now" for less than 1 minute ago', () => {
    const now = new Date();
    expect(formatRelativeTime(now.toISOString())).toBe('just now');
  });

  it('returns "Xm ago" for minutes', () => {
    const d = new Date(Date.now() - 5 * 60_000);
    expect(formatRelativeTime(d.toISOString())).toBe('5m ago');
  });

  it('returns "Xh ago" for hours', () => {
    const d = new Date(Date.now() - 3 * 3_600_000);
    expect(formatRelativeTime(d.toISOString())).toBe('3h ago');
  });

  it('returns "yesterday" for 1 day ago', () => {
    const d = new Date(Date.now() - 36 * 3_600_000);
    expect(formatRelativeTime(d.toISOString())).toBe('yesterday');
  });

  it('returns "Xd ago" for 2-6 days', () => {
    const d = new Date(Date.now() - 3 * 86_400_000);
    expect(formatRelativeTime(d.toISOString())).toBe('3d ago');
  });

  it('returns "Mon DD" for 7+ days', () => {
    const d = new Date(Date.now() - 10 * 86_400_000);
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const expected = `${months[d.getMonth()]} ${d.getDate()}`;
    expect(formatRelativeTime(d.toISOString())).toBe(expected);
  });
});
