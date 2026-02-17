import React from 'react';
import { Alert } from 'react-native';
import { waitFor, fireEvent } from '@testing-library/react-native';
import { ProfileScreen } from '../../src/screens/profile/ProfileScreen';
import { renderWithProviders } from '../helpers';

const mockLogout = jest.fn();
jest.mock('../../src/context/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 1,
      email: 'jane@test.com',
      full_name: 'Jane Doe',
      role: 'parent',
      roles: ['parent'],
      is_active: true,
      google_connected: true,
    },
    logout: mockLogout,
  }),
}));

jest.mock('../../src/api/notifications', () => ({
  notificationsApi: {
    getUnreadCount: jest.fn(() => Promise.resolve({ count: 4 })),
  },
}));

jest.mock('../../src/api/messages', () => ({
  messagesApi: {
    getUnreadCount: jest.fn(() => Promise.resolve({ total_unread: 2 })),
  },
}));

describe('ProfileScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders user name', () => {
    const { getByText } = renderWithProviders(<ProfileScreen />);
    expect(getByText('Jane Doe')).toBeTruthy();
  });

  it('renders user email', () => {
    const { getAllByText } = renderWithProviders(<ProfileScreen />);
    expect(getAllByText('jane@test.com').length).toBeGreaterThan(0);
  });

  it('renders user initials in avatar', () => {
    const { getByText } = renderWithProviders(<ProfileScreen />);
    expect(getByText('JD')).toBeTruthy();
  });

  it('renders role badge', () => {
    const { getAllByText } = renderWithProviders(<ProfileScreen />);
    expect(getAllByText('Parent').length).toBeGreaterThanOrEqual(1);
  });

  it('shows Google connected status', () => {
    const { getByText } = renderWithProviders(<ProfileScreen />);
    expect(getByText('Connected')).toBeTruthy();
  });

  it('shows app version', () => {
    const { getByText } = renderWithProviders(<ProfileScreen />);
    expect(getByText('1.0.0 (Pilot)')).toBeTruthy();
  });

  it('shows web app link', () => {
    const { getByText } = renderWithProviders(<ProfileScreen />);
    expect(getByText('classbridge.ca')).toBeTruthy();
  });

  it('shows web note about managing children on web', () => {
    const { getByText } = renderWithProviders(<ProfileScreen />);
    expect(getByText(/manage children, courses, study materials/)).toBeTruthy();
  });

  it('renders sign out button', () => {
    const { getByText } = renderWithProviders(<ProfileScreen />);
    expect(getByText('Sign Out')).toBeTruthy();
  });

  it('shows confirmation alert on sign out press', () => {
    const alertSpy = jest.spyOn(Alert, 'alert');
    const { getByText } = renderWithProviders(<ProfileScreen />);
    fireEvent.press(getByText('Sign Out'));
    expect(alertSpy).toHaveBeenCalledWith(
      'Sign Out',
      'Are you sure you want to sign out?',
      expect.arrayContaining([
        expect.objectContaining({ text: 'Cancel' }),
        expect.objectContaining({ text: 'Sign Out' }),
      ]),
    );
  });

  it('calls logout when confirming sign out', () => {
    const alertSpy = jest.spyOn(Alert, 'alert');
    const { getByText } = renderWithProviders(<ProfileScreen />);
    fireEvent.press(getByText('Sign Out'));
    // Get the Sign Out button handler from the alert
    const buttons = alertSpy.mock.calls[0][2] as Array<{ text: string; onPress?: () => void }>;
    const signOutBtn = buttons.find(b => b.text === 'Sign Out');
    signOutBtn?.onPress?.();
    expect(mockLogout).toHaveBeenCalled();
  });

  it('shows unread notification count', async () => {
    const { getByText } = renderWithProviders(<ProfileScreen />);
    await waitFor(() => {
      expect(getByText('4')).toBeTruthy();
    });
  });

  it('shows unread message count', async () => {
    const { getByText } = renderWithProviders(<ProfileScreen />);
    await waitFor(() => {
      expect(getByText('2')).toBeTruthy();
    });
  });

  it('renders section titles', () => {
    const { getByText } = renderWithProviders(<ProfileScreen />);
    expect(getByText('Account')).toBeTruthy();
    expect(getByText('App')).toBeTruthy();
  });
});
