import { api } from './client';

export interface ConversationStarter {
  prompt: string;
  context: string | null;
}

export interface ConversationStartersResponse {
  starters: ConversationStarter[];
  student_name: string;
  generated_at: string;
}

export const conversationStartersApi = {
  generate: async (studentId: number, courseId?: number | null) => {
    const response = await api.post('/api/conversation-starters/generate', {
      student_id: studentId,
      course_id: courseId ?? null,
    });
    return response.data as ConversationStartersResponse;
  },

  getDaily: async () => {
    const response = await api.get('/api/conversation-starters/daily');
    return response.data as ConversationStartersResponse;
  },
};
