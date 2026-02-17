import React from 'react';
import { waitFor, fireEvent } from '@testing-library/react-native';
import { ChatScreen } from '../../src/screens/messages/ChatScreen';
import { renderWithProviders, mockUser } from '../helpers';

jest.mock('../../src/context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, email: 'parent@test.com', full_name: 'Jane Doe', role: 'parent', roles: ['parent'], is_active: true, google_connected: true },
  }),
}));

const mockRoute = {
  params: { conversationId: 1, name: 'Mr. Smith' },
  key: 'test-key',
  name: 'Chat' as const,
};
const mockNavigation = {} as any;

const mockConversation = {
  id: 1,
  participant_1_id: 1,
  participant_1_name: 'Jane Doe',
  participant_2_id: 5,
  participant_2_name: 'Mr. Smith',
  student_id: 10,
  student_name: 'Alice Doe',
  subject: 'Math grade',
  messages: [
    { id: 1, conversation_id: 1, sender_id: 5, sender_name: 'Mr. Smith', content: 'Hello, regarding Alice...', is_read: true, read_at: null, created_at: '2026-02-17T09:00:00Z' },
    { id: 2, conversation_id: 1, sender_id: 1, sender_name: 'Jane Doe', content: 'Thank you for reaching out.', is_read: true, read_at: null, created_at: '2026-02-17T09:05:00Z' },
  ],
  messages_total: 2,
  messages_offset: 0,
  messages_limit: 50,
  created_at: '2026-02-17T08:00:00Z',
};

jest.mock('../../src/api/messages', () => ({
  messagesApi: {
    getConversation: jest.fn(() => Promise.resolve(mockConversation)),
    markAsRead: jest.fn(() => Promise.resolve()),
    sendMessage: jest.fn(() => Promise.resolve({ id: 3, conversation_id: 1, sender_id: 1, sender_name: 'Jane Doe', content: 'Test message', is_read: false, read_at: null, created_at: new Date().toISOString() })),
    getUnreadCount: jest.fn(() => Promise.resolve({ total_unread: 0 })),
    listConversations: jest.fn(() => Promise.resolve([])),
  },
}));

describe('ChatScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders conversation messages', async () => {
    const { getByText } = renderWithProviders(
      <ChatScreen route={mockRoute} navigation={mockNavigation} />
    );
    await waitFor(() => {
      expect(getByText('Hello, regarding Alice...')).toBeTruthy();
      expect(getByText('Thank you for reaching out.')).toBeTruthy();
    });
  });

  it('shows sender name on incoming messages', async () => {
    const { getByText } = renderWithProviders(
      <ChatScreen route={mockRoute} navigation={mockNavigation} />
    );
    await waitFor(() => {
      expect(getByText('Mr. Smith')).toBeTruthy();
    });
  });

  it('renders subject bar with subject and student name', async () => {
    const { getByText } = renderWithProviders(
      <ChatScreen route={mockRoute} navigation={mockNavigation} />
    );
    await waitFor(() => {
      expect(getByText('Math grade')).toBeTruthy();
      expect(getByText('Re: Alice Doe')).toBeTruthy();
    });
  });

  it('marks conversation as read on load', async () => {
    const { messagesApi } = require('../../src/api/messages');
    renderWithProviders(
      <ChatScreen route={mockRoute} navigation={mockNavigation} />
    );
    await waitFor(() => {
      expect(messagesApi.markAsRead).toHaveBeenCalledWith(1);
    });
  });

  it('renders message input and send button', async () => {
    const { getByPlaceholderText } = renderWithProviders(
      <ChatScreen route={mockRoute} navigation={mockNavigation} />
    );
    await waitFor(() => {
      expect(getByPlaceholderText('Type a message...')).toBeTruthy();
    });
  });

  it('sends message when text is entered and send pressed', async () => {
    const { messagesApi } = require('../../src/api/messages');
    const { getByPlaceholderText, getByText } = renderWithProviders(
      <ChatScreen route={mockRoute} navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(getByPlaceholderText('Type a message...')).toBeTruthy();
    });

    fireEvent.changeText(getByPlaceholderText('Type a message...'), 'Hello!');
    fireEvent.press(getByText('send'));

    await waitFor(() => {
      expect(messagesApi.sendMessage).toHaveBeenCalledWith(1, 'Hello!');
    });
  });
});

describe('ChatScreen - empty', () => {
  it('shows empty state when no messages', async () => {
    const { messagesApi } = require('../../src/api/messages');
    messagesApi.getConversation.mockResolvedValue({
      ...mockConversation,
      messages: [],
    });

    const { getByText } = renderWithProviders(
      <ChatScreen route={mockRoute} navigation={mockNavigation} />
    );
    await waitFor(() => {
      expect(getByText('No messages yet')).toBeTruthy();
    });
  });
});
