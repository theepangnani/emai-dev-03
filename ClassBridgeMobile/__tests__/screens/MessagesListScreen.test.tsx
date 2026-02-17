import React from 'react';
import { waitFor, fireEvent } from '@testing-library/react-native';
import { MessagesListScreen } from '../../src/screens/messages/MessagesListScreen';
import { renderWithProviders } from '../helpers';

const mockNavigate = jest.fn();
jest.mock('@react-navigation/native', () => ({
  ...jest.requireActual('@react-navigation/native'),
  useNavigation: () => ({ navigate: mockNavigate }),
}));

const mockConversations = [
  {
    id: 1,
    other_participant_id: 5,
    other_participant_name: 'Mr. Smith',
    other_participant_role: 'teacher',
    student_id: 10,
    student_name: 'Alice Doe',
    subject: 'Math grade concern',
    last_message_preview: 'Hi, I wanted to discuss...',
    last_message_at: new Date().toISOString(),
    unread_count: 3,
    created_at: '2026-01-01',
  },
  {
    id: 2,
    other_participant_id: 6,
    other_participant_name: 'Ms. Johnson',
    other_participant_role: 'teacher',
    student_id: null,
    student_name: null,
    subject: null,
    last_message_preview: 'Thank you for the update',
    last_message_at: new Date(Date.now() - 86400000).toISOString(), // yesterday
    unread_count: 0,
    created_at: '2026-01-01',
  },
];

jest.mock('../../src/api/messages', () => ({
  messagesApi: {
    listConversations: jest.fn(() => Promise.resolve(mockConversations)),
    getUnreadCount: jest.fn(() => Promise.resolve({ total_unread: 3 })),
  },
}));

describe('MessagesListScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders conversation participants', async () => {
    const { getByText } = renderWithProviders(<MessagesListScreen />);
    await waitFor(() => {
      expect(getByText('Mr. Smith')).toBeTruthy();
      expect(getByText('Ms. Johnson')).toBeTruthy();
    });
  });

  it('renders avatars with initials', async () => {
    const { getByText } = renderWithProviders(<MessagesListScreen />);
    await waitFor(() => {
      expect(getByText('MS')).toBeTruthy(); // Mr. Smith
      expect(getByText('MJ')).toBeTruthy(); // Ms. Johnson
    });
  });

  it('renders message previews', async () => {
    const { getByText } = renderWithProviders(<MessagesListScreen />);
    await waitFor(() => {
      expect(getByText('Hi, I wanted to discuss...')).toBeTruthy();
      expect(getByText('Thank you for the update')).toBeTruthy();
    });
  });

  it('shows subject when present', async () => {
    const { getByText } = renderWithProviders(<MessagesListScreen />);
    await waitFor(() => {
      expect(getByText('Math grade concern')).toBeTruthy();
    });
  });

  it('shows student tag when present', async () => {
    const { getByText } = renderWithProviders(<MessagesListScreen />);
    await waitFor(() => {
      expect(getByText('Re: Alice Doe')).toBeTruthy();
    });
  });

  it('shows unread badge count', async () => {
    const { getByText } = renderWithProviders(<MessagesListScreen />);
    await waitFor(() => {
      expect(getByText('3')).toBeTruthy();
    });
  });

  it('navigates to chat on conversation press', async () => {
    const { getByText } = renderWithProviders(<MessagesListScreen />);
    await waitFor(() => {
      expect(getByText('Mr. Smith')).toBeTruthy();
    });
    fireEvent.press(getByText('Mr. Smith'));
    expect(mockNavigate).toHaveBeenCalledWith('Chat', {
      conversationId: 1,
      name: 'Mr. Smith',
    });
  });
});

describe('MessagesListScreen - empty', () => {
  it('shows empty state when no conversations', async () => {
    const { messagesApi } = require('../../src/api/messages');
    messagesApi.listConversations.mockResolvedValue([]);

    const { getByText } = renderWithProviders(<MessagesListScreen />);
    await waitFor(() => {
      expect(getByText('No conversations')).toBeTruthy();
    });
  });
});
