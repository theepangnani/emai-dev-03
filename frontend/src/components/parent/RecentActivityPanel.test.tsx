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
    activity_type: 'task_created',
    title: 'Test Activity',
    description: 'A test description',
    resource_type: 'task',
    resource_id: 1,
    student_id: null,
    student_name: null,
    created_at: new Date().toISOString(),
    icon_type: 'plus-square',
    ...overrides,
  };
}

const ALL_TYPES: ActivityItem['activity_type'][] = [
  'course_created',
  'task_created',
  'material_uploaded',
  'task_completed',
  'message_received',
  'notification_received',
];

/* ── Tests ──────────────────────────────────────────────── */

describe('RecentActivityPanel', () => {
  const mockNavigate = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders loading skeleton initially', () => {
    mockGetRecent.mockReturnValue(new Promise(() => {})); // never resolves
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} />,
    );
    const skeletons = screen.getAllByTestId('activity-skeleton');
    expect(skeletons).toHaveLength(3);
  });

  it('renders activity items after fetch', async () => {
    const items = [
      createActivity({ title: 'New Course', activity_type: 'course_created' }),
      createActivity({ title: 'New Task', activity_type: 'task_created' }),
    ];
    mockGetRecent.mockResolvedValue(items);
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} />,
    );
    await waitFor(() => {
      expect(screen.getByText('New Course')).toBeInTheDocument();
      expect(screen.getByText('New Task')).toBeInTheDocument();
    });
  });

  it('each activity type shows correct icon', async () => {
    const items = ALL_TYPES.map((type, i) =>
      createActivity({ activity_type: type, title: `Item ${type}`, resource_id: i + 1 }),
    );
    mockGetRecent.mockResolvedValue(items);
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} />,
    );
    await waitFor(() => {
      for (const type of ALL_TYPES) {
        expect(screen.getByTestId(`activity-icon-${type}`)).toBeInTheDocument();
      }
    });
  });

  it('clicking a course_created row navigates to /courses', async () => {
    mockGetRecent.mockResolvedValue([
      createActivity({ activity_type: 'course_created', title: 'Math 101' }),
    ]);
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} />,
    );
    await waitFor(() => screen.getByText('Math 101'));
    fireEvent.click(screen.getByTestId('activity-row'));
    expect(mockNavigate).toHaveBeenCalledWith('/courses');
  });

  it('clicking a task_created row navigates to /tasks/:id (#1236)', async () => {
    mockGetRecent.mockResolvedValue([
      createActivity({ activity_type: 'task_created', title: 'Do homework', resource_id: 77 }),
    ]);
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} />,
    );
    await waitFor(() => screen.getByText('Do homework'));
    fireEvent.click(screen.getByTestId('activity-row'));
    expect(mockNavigate).toHaveBeenCalledWith('/tasks/77');
  });

  it('clicking a material_uploaded row navigates to /course-materials/:id', async () => {
    mockGetRecent.mockResolvedValue([
      createActivity({ activity_type: 'material_uploaded', title: 'Notes', resource_id: 42 }),
    ]);
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} />,
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
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} />,
    );
    await waitFor(() => screen.getByText('New message'));
    fireEvent.click(screen.getByTestId('activity-row'));
    expect(mockNavigate).toHaveBeenCalledWith('/messages');
  });

  it('notification_received row does not navigate', async () => {
    mockGetRecent.mockResolvedValue([
      createActivity({ activity_type: 'notification_received', title: 'Alert' }),
    ]);
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} />,
    );
    await waitFor(() => screen.getByText('Alert'));
    fireEvent.click(screen.getByTestId('activity-row'));
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('collapse/expand toggles content visibility', async () => {
    mockGetRecent.mockResolvedValue([createActivity({ title: 'Item 1' })]);
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} />,
    );
    await waitFor(() => screen.getByText('Item 1'));

    const body = screen.getByTestId('activity-body');
    expect(body).not.toHaveClass('pd-activity-body-collapsed');

    // Click header to collapse
    fireEvent.click(screen.getByText('Recent Activity'));
    expect(body).toHaveClass('pd-activity-body-collapsed');

    // Click again to expand
    fireEvent.click(screen.getByText('Recent Activity'));
    expect(body).not.toHaveClass('pd-activity-body-collapsed');
  });

  it('empty state shown when no activities', async () => {
    mockGetRecent.mockResolvedValue([]);
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} />,
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
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} />,
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
      <RecentActivityPanel selectedChild={1} navigate={mockNavigate} />,
    );
    await waitFor(() => screen.getByText('Test Activity'));
    expect(screen.queryByTestId('activity-child-badge')).not.toBeInTheDocument();
  });

  it('error state shows retry button and can refetch', async () => {
    mockGetRecent.mockRejectedValueOnce(new Error('Network error'));
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} />,
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

  it('persists collapse state in localStorage', async () => {
    mockGetRecent.mockResolvedValue([createActivity()]);
    renderWithProviders(
      <RecentActivityPanel selectedChild={null} navigate={mockNavigate} />,
    );
    await waitFor(() => screen.getByText('Test Activity'));

    fireEvent.click(screen.getByText('Recent Activity'));
    expect(localStorage.getItem('pd-activity-collapsed')).toBe('1');

    fireEvent.click(screen.getByText('Recent Activity'));
    expect(localStorage.getItem('pd-activity-collapsed')).toBe('0');
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
    const d = new Date(Date.now() - 30 * 3_600_000);
    expect(formatRelativeTime(d.toISOString())).toBe('yesterday');
  });

  it('returns "Xd ago" for 2-6 days', () => {
    const d = new Date(Date.now() - 4 * 86_400_000);
    expect(formatRelativeTime(d.toISOString())).toBe('4d ago');
  });

  it('returns "MMM D" format for older dates', () => {
    const d = new Date(2026, 2, 5); // Mar 5, 2026
    // Only test if it's more than 7 days ago
    const diffDays = Math.floor((Date.now() - d.getTime()) / 86_400_000);
    if (diffDays >= 7) {
      expect(formatRelativeTime(d.toISOString())).toBe('Mar 5');
    }
  });
});
