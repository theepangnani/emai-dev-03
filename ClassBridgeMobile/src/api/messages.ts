import { api } from './client';

// Messages Types (ported from web frontend/src/api/messages.ts)
export interface MessageResponse {
  id: number;
  conversation_id: number;
  sender_id: number;
  sender_name: string;
  content: string;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface ConversationSummary {
  id: number;
  other_participant_id: number;
  other_participant_name: string;
  other_participant_role: string | null;
  student_id: number | null;
  student_name: string | null;
  subject: string | null;
  last_message_preview: string | null;
  last_message_at: string | null;
  unread_count: number;
  created_at: string;
}

export interface ConversationDetail {
  id: number;
  participant_1_id: number;
  participant_1_name: string;
  participant_2_id: number;
  participant_2_name: string;
  student_id: number | null;
  student_name: string | null;
  subject: string | null;
  messages: MessageResponse[];
  messages_total: number;
  messages_offset: number;
  messages_limit: number;
  created_at: string;
}

// Messages API — mobile supports read + reply
export const messagesApi = {
  listConversations: async (params?: { skip?: number; limit?: number }) => {
    const response = await api.get('/api/messages/conversations', { params });
    return response.data as ConversationSummary[];
  },

  getConversation: async (
    id: number,
    params?: { offset?: number; limit?: number }
  ) => {
    const response = await api.get(`/api/messages/conversations/${id}`, {
      params,
    });
    return response.data as ConversationDetail;
  },

  sendMessage: async (conversationId: number, content: string) => {
    const response = await api.post(
      `/api/messages/conversations/${conversationId}/messages`,
      { content }
    );
    return response.data as MessageResponse;
  },

  markAsRead: async (conversationId: number) => {
    await api.patch(`/api/messages/conversations/${conversationId}/read`);
  },

  getUnreadCount: async () => {
    const response = await api.get('/api/messages/unread-count');
    return response.data as { total_unread: number };
  },
};
