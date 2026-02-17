import React from 'react';
import { waitFor, fireEvent } from '@testing-library/react-native';
import { NotificationsScreen } from '../../src/screens/notifications/NotificationsScreen';
import { renderWithProviders } from '../helpers';

const mockNotifications = [
  {
    id: 1,
    user_id: 1,
    type: 'assignment_due' as const,
    title: 'Math homework due tomorrow',
    content: 'Homework 1 is due Feb 18',
    link: null,
    read: false,
    created_at: new Date(Date.now() - 300000).toISOString(), // 5 min ago
  },
  {
    id: 2,
    user_id: 1,
    type: 'message' as const,
    title: 'New message from Mr. Smith',
    content: null,
    link: null,
    read: true,
    created_at: new Date(Date.now() - 7200000).toISOString(), // 2 hours ago
  },
  {
    id: 3,
    user_id: 1,
    type: 'system' as const,
    title: 'Welcome to ClassBridge!',
    content: 'Get started by adding your children.',
    link: null,
    read: true,
    created_at: new Date(Date.now() - 86400000 * 3).toISOString(), // 3 days ago
  },
];

jest.mock('../../src/api/notifications', () => ({
  notificationsApi: {
    list: jest.fn(() => Promise.resolve(mockNotifications)),
    markAsRead: jest.fn(() => Promise.resolve(mockNotifications[0])),
    markAllAsRead: jest.fn(() => Promise.resolve()),
    getUnreadCount: jest.fn(() => Promise.resolve({ count: 1 })),
  },
}));

describe('NotificationsScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders notification titles', async () => {
    const { getByText } = renderWithProviders(<NotificationsScreen />);
    await waitFor(() => {
      expect(getByText('Math homework due tomorrow')).toBeTruthy();
      expect(getByText('New message from Mr. Smith')).toBeTruthy();
      expect(getByText('Welcome to ClassBridge!')).toBeTruthy();
    });
  });

  it('renders notification content when present', async () => {
    const { getByText } = renderWithProviders(<NotificationsScreen />);
    await waitFor(() => {
      expect(getByText('Homework 1 is due Feb 18')).toBeTruthy();
      expect(getByText('Get started by adding your children.')).toBeTruthy();
    });
  });

  it('shows relative time for notifications', async () => {
    const { getByText } = renderWithProviders(<NotificationsScreen />);
    await waitFor(() => {
      expect(getByText('5m ago')).toBeTruthy();
      expect(getByText('2h ago')).toBeTruthy();
      expect(getByText('3d ago')).toBeTruthy();
    });
  });

  it('shows unread count in header bar', async () => {
    const { getByText } = renderWithProviders(<NotificationsScreen />);
    await waitFor(() => {
      expect(getByText('1 unread')).toBeTruthy();
    });
  });

  it('shows Mark all read button', async () => {
    const { getByText } = renderWithProviders(<NotificationsScreen />);
    await waitFor(() => {
      expect(getByText('Mark all read')).toBeTruthy();
    });
  });

  it('calls markAsRead when tapping unread notification', async () => {
    const { notificationsApi } = require('../../src/api/notifications');
    const { getByText } = renderWithProviders(<NotificationsScreen />);
    await waitFor(() => {
      expect(getByText('Math homework due tomorrow')).toBeTruthy();
    });
    fireEvent.press(getByText('Math homework due tomorrow'));
    await waitFor(() => {
      expect(notificationsApi.markAsRead).toHaveBeenCalledWith(1);
    });
  });

  it('calls markAllAsRead when pressing Mark all read', async () => {
    const { notificationsApi } = require('../../src/api/notifications');
    const { getByText } = renderWithProviders(<NotificationsScreen />);
    await waitFor(() => {
      expect(getByText('Mark all read')).toBeTruthy();
    });
    fireEvent.press(getByText('Mark all read'));
    await waitFor(() => {
      expect(notificationsApi.markAllAsRead).toHaveBeenCalled();
    });
  });

  it('renders correct icons for notification types', async () => {
    const { getByText } = renderWithProviders(<NotificationsScreen />);
    await waitFor(() => {
      expect(getByText('assignment-late')).toBeTruthy(); // assignment_due icon
      expect(getByText('chat')).toBeTruthy(); // message icon
      expect(getByText('info')).toBeTruthy(); // system icon
    });
  });
});

describe('NotificationsScreen - empty', () => {
  it('shows empty state when no notifications', async () => {
    const { notificationsApi } = require('../../src/api/notifications');
    notificationsApi.list.mockResolvedValue([]);

    const { getByText } = renderWithProviders(<NotificationsScreen />);
    await waitFor(() => {
      expect(getByText('No notifications')).toBeTruthy();
    });
  });
});
