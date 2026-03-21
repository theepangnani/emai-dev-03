import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../test/helpers';

const mockGetUpcoming = vi.fn();
const mockDismiss = vi.fn();

vi.mock('../api/events', () => ({
  eventsApi: {
    getUpcoming: (...args: unknown[]) => mockGetUpcoming(...args),
    dismiss: (...args: unknown[]) => mockDismiss(...args),
  },
}));

import { AssessmentCountdown } from './AssessmentCountdown';

describe('AssessmentCountdown', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing when no events', async () => {
    mockGetUpcoming.mockResolvedValue([]);
    const { container } = renderWithProviders(<AssessmentCountdown />);
    await waitFor(() => {
      expect(container.querySelector('.ac-section')).toBeNull();
    });
  });

  it('renders countdown cards with correct urgency', async () => {
    const today = new Date();
    const in2Days = new Date(today);
    in2Days.setDate(today.getDate() + 2);
    const in5Days = new Date(today);
    in5Days.setDate(today.getDate() + 5);
    const in10Days = new Date(today);
    in10Days.setDate(today.getDate() + 10);

    mockGetUpcoming.mockResolvedValue([
      { id: 1, event_title: 'Math Quiz', event_type: 'quiz', event_date: in2Days.toISOString().slice(0, 10), days_remaining: 2, dismissed: false, student_id: 1, source: 'document_parse', course_id: null, course_content_id: null, created_at: null },
      { id: 2, event_title: 'History Exam', event_type: 'exam', event_date: in5Days.toISOString().slice(0, 10), days_remaining: 5, dismissed: false, student_id: 1, source: 'document_parse', course_id: null, course_content_id: null, created_at: null },
      { id: 3, event_title: 'Science Test', event_type: 'test', event_date: in10Days.toISOString().slice(0, 10), days_remaining: 10, dismissed: false, student_id: 1, source: 'document_parse', course_id: null, course_content_id: null, created_at: null },
    ]);

    renderWithProviders(<AssessmentCountdown />);

    await waitFor(() => {
      expect(screen.getByText('Math Quiz')).toBeInTheDocument();
    });

    expect(screen.getByText('History Exam')).toBeInTheDocument();
    expect(screen.getByText('Science Test')).toBeInTheDocument();
    expect(screen.getByText('Upcoming Assessments')).toBeInTheDocument();
  });

  it('calls dismiss on X button click', async () => {
    const user = userEvent.setup();
    mockGetUpcoming.mockResolvedValue([
      { id: 42, event_title: 'Pop Quiz', event_type: 'quiz', event_date: '2026-04-01', days_remaining: 5, dismissed: false, student_id: 1, source: 'document_parse', course_id: null, course_content_id: null, created_at: null },
    ]);
    mockDismiss.mockResolvedValue(undefined);

    renderWithProviders(<AssessmentCountdown />);

    await waitFor(() => {
      expect(screen.getByText('Pop Quiz')).toBeInTheDocument();
    });

    const dismissBtn = screen.getByLabelText('Dismiss Pop Quiz');
    await user.click(dismissBtn);

    expect(mockDismiss.mock.calls[0][0]).toBe(42);
  });
});
