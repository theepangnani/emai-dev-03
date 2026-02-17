import React from 'react';
import { waitFor, fireEvent } from '@testing-library/react-native';
import { CalendarScreen } from '../../src/screens/parent/CalendarScreen';
import { renderWithProviders } from '../helpers';

const mockTodayISO = new Date().toISOString();

const mockDashboard = {
  children: [],
  google_connected: true,
  unread_messages: 0,
  total_overdue: 0,
  total_due_today: 1,
  total_tasks: 0,
  child_highlights: [
    {
      student_id: 10,
      user_id: 20,
      full_name: 'Alice',
      grade_level: 5,
      overdue_count: 0,
      due_today_count: 0,
      upcoming_count: 0,
      completed_today_count: 0,
      courses: [{ id: 1, name: 'Math', description: null, subject: null, google_classroom_id: null, teacher_id: null, created_at: '', teacher_name: null, teacher_email: null }],
      overdue_items: [],
      due_today_items: [],
    },
  ],
  all_assignments: [
    { id: 1, title: 'Math Homework', description: null, course_id: 1, google_classroom_id: null, due_date: mockTodayISO, max_points: 50, created_at: '' },
  ],
  all_tasks: [],
};

const mockTaskData = [
  { id: 1, created_by_user_id: 1, assigned_to_user_id: 20, title: 'Study', description: null, due_date: mockTodayISO, is_completed: false, completed_at: null, archived_at: null, priority: 'high', category: null, creator_name: 'Jane', assignee_name: 'Alice', course_id: null, course_content_id: null, study_guide_id: null, course_name: null, course_content_title: null, study_guide_title: null, study_guide_type: null, created_at: '', updated_at: null },
];

jest.mock('../../src/api/parent', () => ({
  parentApi: {
    getDashboard: jest.fn(() => Promise.resolve(mockDashboard)),
  },
}));

jest.mock('../../src/api/tasks', () => ({
  tasksApi: {
    list: jest.fn(() => Promise.resolve(mockTaskData)),
  },
}));

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

const today = new Date();

describe('CalendarScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders current month and year', async () => {
    const { getByText } = renderWithProviders(<CalendarScreen />);
    const expectedTitle = `${MONTHS[today.getMonth()]} ${today.getFullYear()}`;
    await waitFor(() => {
      expect(getByText(expectedTitle)).toBeTruthy();
    });
  });

  it('renders weekday headers', async () => {
    const { getByText } = renderWithProviders(<CalendarScreen />);
    await waitFor(() => {
      expect(getByText('Sun')).toBeTruthy();
      expect(getByText('Mon')).toBeTruthy();
      expect(getByText('Tue')).toBeTruthy();
      expect(getByText('Wed')).toBeTruthy();
      expect(getByText('Thu')).toBeTruthy();
      expect(getByText('Fri')).toBeTruthy();
      expect(getByText('Sat')).toBeTruthy();
    });
  });

  it('renders today date number in the grid', async () => {
    const { getAllByText } = renderWithProviders(<CalendarScreen />);
    await waitFor(() => {
      expect(getAllByText(String(today.getDate())).length).toBeGreaterThanOrEqual(1);
    });
  });

  it('shows items for today in the detail section', async () => {
    const { getByText } = renderWithProviders(<CalendarScreen />);
    await waitFor(() => {
      expect(getByText('Math Homework')).toBeTruthy();
      expect(getByText('Study')).toBeTruthy();
    });
  });

  it('shows assignment and task type labels', async () => {
    const { getByText } = renderWithProviders(<CalendarScreen />);
    await waitFor(() => {
      expect(getByText('Assignment')).toBeTruthy();
      expect(getByText('Task')).toBeTruthy();
    });
  });

  it('shows High priority badge for high priority tasks', async () => {
    const { getByText } = renderWithProviders(<CalendarScreen />);
    await waitFor(() => {
      expect(getByText('High')).toBeTruthy();
    });
  });

  it('shows course name for assignments', async () => {
    const { getByText } = renderWithProviders(<CalendarScreen />);
    await waitFor(() => {
      expect(getByText('Math')).toBeTruthy();
    });
  });

  it('navigates to previous month on left chevron press', async () => {
    const { getByText } = renderWithProviders(<CalendarScreen />);
    const expectedTitle = `${MONTHS[today.getMonth()]} ${today.getFullYear()}`;
    await waitFor(() => {
      expect(getByText(expectedTitle)).toBeTruthy();
    });
    fireEvent.press(getByText('chevron-left'));
    const prevMonth = today.getMonth() === 0 ? 11 : today.getMonth() - 1;
    const prevYear = today.getMonth() === 0 ? today.getFullYear() - 1 : today.getFullYear();
    await waitFor(() => {
      expect(getByText(`${MONTHS[prevMonth]} ${prevYear}`)).toBeTruthy();
    });
  });
});

describe('CalendarScreen - empty day', () => {
  it('shows "Nothing scheduled" when selecting a day with no items', async () => {
    const { parentApi } = require('../../src/api/parent');
    parentApi.getDashboard.mockResolvedValue({
      ...mockDashboard,
      all_assignments: [],
    });
    const { tasksApi } = require('../../src/api/tasks');
    tasksApi.list.mockResolvedValue([]);

    const { getByText } = renderWithProviders(<CalendarScreen />);
    await waitFor(() => {
      expect(getByText('Nothing scheduled')).toBeTruthy();
    });
  });
});
