import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../test/helpers';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, full_name: 'Student User', role: 'student', roles: ['student'] },
    logout: vi.fn(),
    switchRole: vi.fn(),
  }),
}));

const mockGetTimeline = vi.fn();
const mockGetRecent = vi.fn();
const mockCoursesList = vi.fn();

vi.mock('../api/activity', () => ({
  activityApi: {
    getTimeline: (...args: unknown[]) => mockGetTimeline(...args),
    getRecent: (...args: unknown[]) => mockGetRecent(...args),
  },
}));

vi.mock('../api/courses', () => ({
  coursesApi: {
    list: (...args: unknown[]) => mockCoursesList(...args),
  },
}));

vi.mock('../api/client', () => ({
  messagesApi: { getUnreadCount: vi.fn().mockResolvedValue({ total_unread: 0 }) },
  inspirationApi: { getRandom: vi.fn().mockResolvedValue(null) },
  api: { get: vi.fn(), post: vi.fn() },
}));

vi.mock('../api/studyRequests', () => ({
  studyRequestsApi: { pendingCount: vi.fn().mockResolvedValue(0) },
}));

describe('StudyTimelinePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCoursesList.mockResolvedValue([]);
  });

  it('renders timeline entries', async () => {
    mockGetTimeline.mockResolvedValue({
      items: [
        { type: 'upload', title: 'Chapter 5 Notes', course: 'Math', date: '2026-03-20T10:00:00Z', xp: 10, score: null, badge_id: null },
        { type: 'quiz', title: 'Quiz: Chapter 5', course: 'Math', date: '2026-03-19T14:00:00Z', xp: 15, score: 85, badge_id: null },
        { type: 'badge', title: 'First Upload', course: null, date: '2026-03-18T09:00:00Z', xp: null, score: null, badge_id: 'first_upload' },
      ],
      total: 3,
    });

    const { StudyTimelinePage } = await import('./StudyTimelinePage');
    renderWithProviders(<StudyTimelinePage />);

    await waitFor(() => {
      expect(screen.getByText('Chapter 5 Notes')).toBeInTheDocument();
    }, { timeout: 10000 });

    expect(screen.getByText('Quiz: Chapter 5')).toBeInTheDocument();
    expect(screen.getByText('First Upload')).toBeInTheDocument();
    expect(screen.getByText('+10 XP')).toBeInTheDocument();
    expect(screen.getByText('85%')).toBeInTheDocument();
  }, 15000);

  it('shows empty state when no activities', async () => {
    mockGetTimeline.mockResolvedValue({ items: [], total: 0 });

    const { StudyTimelinePage } = await import('./StudyTimelinePage');
    renderWithProviders(<StudyTimelinePage />);

    await waitFor(() => {
      expect(screen.getByText('No activity yet')).toBeInTheDocument();
    });
  });

  it('renders filter controls', async () => {
    mockGetTimeline.mockResolvedValue({ items: [], total: 0 });

    const { StudyTimelinePage } = await import('./StudyTimelinePage');
    renderWithProviders(<StudyTimelinePage />);

    await waitFor(() => {
      expect(screen.getByLabelText('Date range')).toBeInTheDocument();
    });

    expect(screen.getByLabelText('Filter by course')).toBeInTheDocument();
    expect(screen.getByText('Upload')).toBeInTheDocument();
    expect(screen.getByText('Study Guide')).toBeInTheDocument();
    expect(screen.getByText('Quiz')).toBeInTheDocument();
    expect(screen.getByText('Badge')).toBeInTheDocument();
    expect(screen.getByText('Level Up')).toBeInTheDocument();
  });
});
