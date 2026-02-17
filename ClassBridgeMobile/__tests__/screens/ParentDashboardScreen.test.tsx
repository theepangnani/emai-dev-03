import React from 'react';
import { waitFor } from '@testing-library/react-native';
import { ParentDashboardScreen } from '../../src/screens/parent/ParentDashboardScreen';
import { renderWithProviders, mockAuthContext } from '../helpers';

// Mock auth context
jest.mock('../../src/context/AuthContext', () => ({
  useAuth: () => mockAuthContext,
}));

// Mock navigation
const mockNavigate = jest.fn();
jest.mock('@react-navigation/native', () => ({
  ...jest.requireActual('@react-navigation/native'),
  useNavigation: () => ({
    navigate: mockNavigate,
  }),
}));

// Mock API responses
const mockDashboard = {
  children: [],
  google_connected: true,
  unread_messages: 2,
  total_overdue: 1,
  total_due_today: 3,
  total_tasks: 5,
  child_highlights: [
    {
      student_id: 10,
      user_id: 20,
      full_name: 'Alice Doe',
      grade_level: 5,
      overdue_count: 1,
      due_today_count: 2,
      upcoming_count: 3,
      completed_today_count: 0,
      courses: [
        { id: 1, name: 'Math', description: null, subject: 'Mathematics', google_classroom_id: null, teacher_id: null, created_at: '', teacher_name: null, teacher_email: null },
      ],
      overdue_items: [],
      due_today_items: [],
    },
    {
      student_id: 11,
      user_id: 21,
      full_name: 'Bob Doe',
      grade_level: null,
      overdue_count: 0,
      due_today_count: 0,
      upcoming_count: 0,
      completed_today_count: 0,
      courses: [],
      overdue_items: [],
      due_today_items: [],
    },
  ],
  all_assignments: [],
  all_tasks: [],
};

jest.mock('../../src/api/parent', () => ({
  parentApi: {
    getDashboard: jest.fn(() => Promise.resolve(mockDashboard)),
  },
}));

jest.mock('../../src/api/messages', () => ({
  messagesApi: {
    getUnreadCount: jest.fn(() => Promise.resolve({ total_unread: 5 })),
  },
}));

describe('ParentDashboardScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders greeting with user first name', async () => {
    const { getByText } = renderWithProviders(<ParentDashboardScreen />);
    await waitFor(() => {
      // greeting depends on time of day, but should contain first name
      expect(getByText(/Jane/)).toBeTruthy();
    });
  });

  it('renders subtitle text', async () => {
    const { getByText } = renderWithProviders(<ParentDashboardScreen />);
    await waitFor(() => {
      expect(getByText("Here's how your children are doing")).toBeTruthy();
    });
  });

  it('displays status cards with correct counts', async () => {
    const { getByText } = renderWithProviders(<ParentDashboardScreen />);
    await waitFor(() => {
      expect(getByText('1')).toBeTruthy(); // overdue
      expect(getByText('3')).toBeTruthy(); // due today
      expect(getByText('Overdue')).toBeTruthy();
      expect(getByText('Due Today')).toBeTruthy();
      expect(getByText('Messages')).toBeTruthy();
    });
  });

  it('renders child cards with names', async () => {
    const { getByText } = renderWithProviders(<ParentDashboardScreen />);
    await waitFor(() => {
      expect(getByText('Alice Doe')).toBeTruthy();
      expect(getByText('Bob Doe')).toBeTruthy();
    });
  });

  it('renders grade badge for children with grade_level', async () => {
    const { getByText } = renderWithProviders(<ParentDashboardScreen />);
    await waitFor(() => {
      expect(getByText('Grade 5')).toBeTruthy();
    });
  });

  it('renders child initials in avatar', async () => {
    const { getByText } = renderWithProviders(<ParentDashboardScreen />);
    await waitFor(() => {
      expect(getByText('AD')).toBeTruthy(); // Alice Doe
      expect(getByText('BD')).toBeTruthy(); // Bob Doe
    });
  });

  it('shows course count on child cards', async () => {
    const { getByText } = renderWithProviders(<ParentDashboardScreen />);
    await waitFor(() => {
      expect(getByText('1 course')).toBeTruthy(); // Alice has 1 course
      expect(getByText('0 courses')).toBeTruthy(); // Bob has 0 courses
    });
  });

  it('shows status badges for child with overdue items', async () => {
    const { getByText } = renderWithProviders(<ParentDashboardScreen />);
    await waitFor(() => {
      expect(getByText('1 overdue')).toBeTruthy();
      expect(getByText('2 due today')).toBeTruthy();
      expect(getByText('3 upcoming')).toBeTruthy();
    });
  });

  it('shows "All caught up!" for child with no items', async () => {
    const { getByText } = renderWithProviders(<ParentDashboardScreen />);
    await waitFor(() => {
      expect(getByText('All caught up!')).toBeTruthy();
    });
  });

  it('renders "Your Children" section title', async () => {
    const { getByText } = renderWithProviders(<ParentDashboardScreen />);
    await waitFor(() => {
      expect(getByText('Your Children')).toBeTruthy();
    });
  });
});

describe('ParentDashboardScreen - empty state', () => {
  beforeEach(() => {
    const { parentApi } = require('../../src/api/parent');
    parentApi.getDashboard.mockResolvedValue({
      ...mockDashboard,
      child_highlights: [],
    });
  });

  it('shows empty state when no children', async () => {
    const { getByText } = renderWithProviders(<ParentDashboardScreen />);
    await waitFor(() => {
      expect(getByText('No children linked')).toBeTruthy();
    });
  });
});
