import React from 'react';
import { waitFor, fireEvent } from '@testing-library/react-native';
import { ChildOverviewScreen } from '../../src/screens/parent/ChildOverviewScreen';
import { renderWithProviders } from '../helpers';

// Mock useRoute to provide route params
jest.mock('@react-navigation/native', () => {
  const actual = jest.requireActual('@react-navigation/native');
  return {
    ...actual,
    useRoute: () => ({
      params: { studentId: 10, name: 'Alice Doe' },
      key: 'test-key',
      name: 'ChildOverview',
    }),
  };
});

const mockOverview = {
  student_id: 10,
  user_id: 20,
  full_name: 'Alice Doe',
  grade_level: 5,
  google_connected: true,
  courses: [
    { id: 1, name: 'Math', description: null, subject: 'Mathematics', google_classroom_id: 'gc-123', teacher_id: 1, created_at: '', teacher_name: 'Mr. Smith', teacher_email: null },
    { id: 2, name: 'English', description: null, subject: null, google_classroom_id: null, teacher_id: null, created_at: '', teacher_name: null, teacher_email: null },
  ],
  assignments: [
    { id: 1, title: 'Homework 1', description: 'Do problems 1-10', course_id: 1, google_classroom_id: null, due_date: new Date(Date.now() - 86400000).toISOString(), max_points: 100, created_at: '' },
    { id: 2, title: 'Essay', description: null, course_id: 2, google_classroom_id: null, due_date: new Date(Date.now() + 86400000 * 2).toISOString(), max_points: null, created_at: '' },
  ],
  study_guides_count: 3,
};

const mockTasks = [
  { id: 1, created_by_user_id: 1, assigned_to_user_id: 20, title: 'Study for test', description: null, due_date: new Date().toISOString(), is_completed: false, completed_at: null, archived_at: null, priority: 'high', category: null, creator_name: 'Jane', assignee_name: 'Alice', course_id: null, course_content_id: null, study_guide_id: null, course_name: null, course_content_title: null, study_guide_title: null, study_guide_type: null, created_at: '', updated_at: null },
  { id: 2, created_by_user_id: 1, assigned_to_user_id: 20, title: 'Read chapter 5', description: null, due_date: null, is_completed: true, completed_at: '2026-01-01', archived_at: null, priority: null, category: null, creator_name: 'Jane', assignee_name: 'Alice', course_id: null, course_content_id: null, study_guide_id: null, course_name: null, course_content_title: null, study_guide_title: null, study_guide_type: null, created_at: '', updated_at: null },
];

jest.mock('../../src/api/parent', () => ({
  parentApi: {
    getChildOverview: jest.fn(() => Promise.resolve(mockOverview)),
  },
}));

jest.mock('../../src/api/tasks', () => ({
  tasksApi: {
    list: jest.fn(() => Promise.resolve(mockTasks)),
    toggleComplete: jest.fn(() => Promise.resolve(mockTasks[0])),
  },
}));

describe('ChildOverviewScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders stats row with counts', async () => {
    const { getByText, getAllByText } = renderWithProviders(
      <ChildOverviewScreen />
    );
    await waitFor(() => {
      expect(getAllByText('2').length).toBeGreaterThanOrEqual(1); // 2 courses and 2 assignments
      expect(getAllByText('Courses').length).toBeGreaterThanOrEqual(1);
      expect(getAllByText('Assignments').length).toBeGreaterThanOrEqual(1);
      expect(getAllByText('Tasks').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders course names', async () => {
    const { getByText } = renderWithProviders(
      <ChildOverviewScreen />
    );
    await waitFor(() => {
      expect(getByText('Math')).toBeTruthy();
      expect(getByText('English')).toBeTruthy();
    });
  });

  it('renders course subject and teacher when present', async () => {
    const { getByText } = renderWithProviders(
      <ChildOverviewScreen />
    );
    await waitFor(() => {
      expect(getByText('Mathematics')).toBeTruthy();
      expect(getByText('Mr. Smith')).toBeTruthy();
    });
  });

  it('renders assignment titles', async () => {
    const { getByText } = renderWithProviders(
      <ChildOverviewScreen />
    );
    await waitFor(() => {
      expect(getByText('Homework 1')).toBeTruthy();
      expect(getByText('Essay')).toBeTruthy();
    });
  });

  it('shows overdue label for past due assignments', async () => {
    const { getByText } = renderWithProviders(
      <ChildOverviewScreen />
    );
    await waitFor(() => {
      expect(getByText('Overdue')).toBeTruthy();
    });
  });

  it('displays points when present', async () => {
    const { getByText } = renderWithProviders(
      <ChildOverviewScreen />
    );
    await waitFor(() => {
      expect(getByText('100 pts')).toBeTruthy();
    });
  });

  it('renders task titles', async () => {
    const { getByText } = renderWithProviders(
      <ChildOverviewScreen />
    );
    await waitFor(() => {
      expect(getByText('Study for test')).toBeTruthy();
      expect(getByText('Read chapter 5')).toBeTruthy();
    });
  });

  it('shows task completion count', async () => {
    const { getByText } = renderWithProviders(
      <ChildOverviewScreen />
    );
    await waitFor(() => {
      expect(getByText('(1/2 done)')).toBeTruthy();
    });
  });

  it('shows Completed divider between pending and completed tasks', async () => {
    const { getByText } = renderWithProviders(
      <ChildOverviewScreen />
    );
    await waitFor(() => {
      expect(getByText('Completed')).toBeTruthy();
    });
  });

  it('calls toggleComplete when task is pressed', async () => {
    const { tasksApi } = require('../../src/api/tasks');
    const { getByText } = renderWithProviders(
      <ChildOverviewScreen />
    );
    await waitFor(() => {
      expect(getByText('Study for test')).toBeTruthy();
    });
    fireEvent.press(getByText('Study for test'));
    await waitFor(() => {
      expect(tasksApi.toggleComplete).toHaveBeenCalledWith(1, true);
    });
  });
});
