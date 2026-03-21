import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PomodoroTimer } from '../PomodoroTimer';

// Mock the api client
vi.mock('../../api/client', () => ({
  api: {
    post: vi.fn().mockResolvedValue({ data: { id: 1, completed: false, duration_seconds: 0 } }),
    get: vi.fn().mockResolvedValue({ data: [] }),
  },
}));

const mockCourses = [
  { id: 1, name: 'Math 101', subject: 'Mathematics' },
  { id: 2, name: 'Science 201', subject: 'Science' },
];

describe('PomodoroTimer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders setup form initially', () => {
    render(<PomodoroTimer courses={mockCourses} />);
    expect(screen.getByText('Start Study Session')).toBeInTheDocument();
    expect(screen.getByText('Class (optional)')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('e.g. Math Chapter 5')).toBeInTheDocument();
  });

  it('renders course options', () => {
    render(<PomodoroTimer courses={mockCourses} />);
    expect(screen.getByText('Math 101')).toBeInTheDocument();
    expect(screen.getByText('Science 201')).toBeInTheDocument();
  });

  it('starts timer on button click', async () => {
    const { api } = await import('../../api/client');
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: { id: 1, completed: false, duration_seconds: 0 },
    });

    render(<PomodoroTimer courses={mockCourses} />);
    const startBtn = screen.getByText('Start Study Session');
    fireEvent.click(startBtn);

    // After starting, timer display should appear (25:00)
    // The API call is async, so we wait
    const { api: apiMod } = await import('../../api/client');
    expect(apiMod.post).toHaveBeenCalledWith('/api/study-sessions/start', expect.any(Object));
  });
});
