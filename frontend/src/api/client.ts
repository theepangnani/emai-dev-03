import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Don't redirect on auth endpoints — let the login/register pages handle their own errors
      const url = error.config?.url || '';
      const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/register') || url.includes('/auth/accept-invite');
      if (!isAuthEndpoint) {
        localStorage.removeItem('token');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  login: async (email: string, password: string) => {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await api.post('/api/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return response.data;
  },

  register: async (data: { email: string; password: string; full_name: string; role: string; teacher_type?: string; google_id?: string; google_access_token?: string; google_refresh_token?: string }) => {
    const response = await api.post('/api/auth/register', data);
    return response.data;
  },

  getMe: async () => {
    const response = await api.get('/api/users/me');
    return response.data;
  },

  acceptInvite: async (token: string, password: string, full_name: string) => {
    const response = await api.post('/api/auth/accept-invite', { token, password, full_name });
    return response.data as { access_token: string; token_type: string };
  },
};

// Courses API
export const coursesApi = {
  list: async () => {
    const response = await api.get('/api/courses/');
    return response.data;
  },

  get: async (id: number) => {
    const response = await api.get(`/api/courses/${id}`);
    return response.data;
  },

  teachingList: async () => {
    const response = await api.get('/api/courses/teaching');
    return response.data;
  },
};

// Assignments API
export const assignmentsApi = {
  list: async (courseId?: number) => {
    const params = courseId ? { course_id: courseId } : {};
    const response = await api.get('/api/assignments/', { params });
    return response.data;
  },

  get: async (id: number) => {
    const response = await api.get(`/api/assignments/${id}`);
    return response.data;
  },
};

// Google Classroom API
export const googleApi = {
  getAuthUrl: async () => {
    const response = await api.get('/api/google/auth');
    return response.data;
  },

  getConnectUrl: async () => {
    const response = await api.get('/api/google/connect');
    return response.data;
  },

  getStatus: async () => {
    const response = await api.get('/api/google/status');
    return response.data;
  },

  disconnect: async () => {
    const response = await api.delete('/api/google/disconnect');
    return response.data;
  },

  getCourses: async () => {
    const response = await api.get('/api/google/courses');
    return response.data;
  },

  syncCourses: async () => {
    const response = await api.post('/api/google/courses/sync');
    return response.data;
  },

  getAssignments: async (courseId: string) => {
    const response = await api.get(`/api/google/courses/${courseId}/assignments`);
    return response.data;
  },

  syncAssignments: async (courseId: string) => {
    const response = await api.post(`/api/google/courses/${courseId}/assignments/sync`);
    return response.data;
  },
};

// Study Tools API
export interface StudyGuide {
  id: number;
  user_id: number;
  assignment_id: number | null;
  course_id: number | null;
  title: string;
  content: string;
  guide_type: string;
  created_at: string;
}

export interface QuizQuestion {
  question: string;
  options: { A: string; B: string; C: string; D: string };
  correct_answer: string;
  explanation: string;
}

export interface Quiz {
  id: number;
  title: string;
  questions: QuizQuestion[];
  guide_type: string;
  created_at: string;
}

export interface Flashcard {
  front: string;
  back: string;
}

export interface FlashcardSet {
  id: number;
  title: string;
  cards: Flashcard[];
  guide_type: string;
  created_at: string;
}

export interface SupportedFormats {
  documents: string[];
  spreadsheets: string[];
  presentations: string[];
  images: string[];
  archives: string[];
  max_file_size_mb: number;
  ocr_available: boolean;
}

export interface ExtractedText {
  filename: string;
  text: string;
  character_count: number;
  word_count: number;
}

export const studyApi = {
  generateGuide: async (params: { assignment_id?: number; course_id?: number; title?: string; content?: string }) => {
    const response = await api.post('/api/study/generate', params);
    return response.data as StudyGuide;
  },

  generateQuiz: async (params: { assignment_id?: number; course_id?: number; topic?: string; content?: string; num_questions?: number }) => {
    const response = await api.post('/api/study/quiz/generate', params);
    return response.data as Quiz;
  },

  generateFlashcards: async (params: { assignment_id?: number; course_id?: number; topic?: string; content?: string; num_cards?: number }) => {
    const response = await api.post('/api/study/flashcards/generate', params);
    return response.data as FlashcardSet;
  },

  listGuides: async (guideType?: string) => {
    const params = guideType ? { guide_type: guideType } : {};
    const response = await api.get('/api/study/guides', { params });
    return response.data as StudyGuide[];
  },

  getGuide: async (id: number) => {
    const response = await api.get(`/api/study/guides/${id}`);
    return response.data as StudyGuide;
  },

  deleteGuide: async (id: number) => {
    await api.delete(`/api/study/guides/${id}`);
  },

  // File Upload Methods
  getSupportedFormats: async () => {
    const response = await api.get('/api/study/upload/formats');
    return response.data as SupportedFormats;
  },

  generateFromFile: async (params: {
    file: File;
    title?: string;
    guide_type: 'study_guide' | 'quiz' | 'flashcards';
    num_questions?: number;
    num_cards?: number;
  }) => {
    const formData = new FormData();
    formData.append('file', params.file);
    if (params.title) formData.append('title', params.title);
    formData.append('guide_type', params.guide_type);
    if (params.num_questions) formData.append('num_questions', params.num_questions.toString());
    if (params.num_cards) formData.append('num_cards', params.num_cards.toString());

    const response = await api.post('/api/study/upload/generate', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data as StudyGuide;
  },

  extractTextFromFile: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post('/api/study/upload/extract-text', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data as ExtractedText;
  },
};

// Messages Types
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

export interface RecipientOption {
  user_id: number;
  full_name: string;
  role: string;
  student_names: string[];
}

// Messages API
export const messagesApi = {
  getRecipients: async () => {
    const response = await api.get('/api/messages/recipients');
    return response.data as RecipientOption[];
  },

  listConversations: async (params?: { skip?: number; limit?: number }) => {
    const response = await api.get('/api/messages/conversations', { params });
    return response.data as ConversationSummary[];
  },

  getConversation: async (id: number, params?: { offset?: number; limit?: number }) => {
    const response = await api.get(`/api/messages/conversations/${id}`, { params });
    return response.data as ConversationDetail;
  },

  createConversation: async (data: {
    recipient_id: number;
    student_id?: number;
    subject?: string;
    initial_message: string;
  }) => {
    const response = await api.post('/api/messages/conversations', data);
    return response.data as ConversationDetail;
  },

  sendMessage: async (conversationId: number, content: string) => {
    const response = await api.post(`/api/messages/conversations/${conversationId}/messages`, {
      content,
    });
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

// Notification Types
export interface NotificationResponse {
  id: number;
  user_id: number;
  type: 'assignment_due' | 'grade_posted' | 'message' | 'system';
  title: string;
  content: string | null;
  link: string | null;
  read: boolean;
  created_at: string;
}

export interface NotificationPreferences {
  email_notifications: boolean;
  assignment_reminder_days: string;
}

// Notifications API
export const notificationsApi = {
  list: async (skip = 0, limit = 20) => {
    const response = await api.get('/api/notifications/', { params: { skip, limit } });
    return response.data as NotificationResponse[];
  },

  getUnreadCount: async () => {
    const response = await api.get('/api/notifications/unread-count');
    return response.data as { count: number };
  },

  markAsRead: async (id: number) => {
    const response = await api.put(`/api/notifications/${id}/read`);
    return response.data as NotificationResponse;
  },

  markAllAsRead: async () => {
    await api.put('/api/notifications/read-all');
  },

  delete: async (id: number) => {
    await api.delete(`/api/notifications/${id}`);
  },

  getSettings: async () => {
    const response = await api.get('/api/notifications/settings');
    return response.data as NotificationPreferences;
  },

  updateSettings: async (settings: NotificationPreferences) => {
    const response = await api.put('/api/notifications/settings', settings);
    return response.data as NotificationPreferences;
  },
};

// Teacher Communication Types
export interface TeacherCommunication {
  id: number;
  user_id: number;
  type: 'email' | 'announcement' | 'comment';
  source_id: string;
  sender_name: string | null;
  sender_email: string | null;
  subject: string | null;
  body: string | null;
  snippet: string | null;
  ai_summary: string | null;
  course_name: string | null;
  is_read: boolean;
  received_at: string | null;
  created_at: string;
}

export interface TeacherCommunicationList {
  items: TeacherCommunication[];
  total: number;
  page: number;
  page_size: number;
}

export interface EmailMonitoringStatus {
  gmail_enabled: boolean;
  classroom_enabled: boolean;
  last_gmail_sync: string | null;
  last_classroom_sync: string | null;
  total_communications: number;
  unread_count: number;
}

// Teacher Communications API
export const teacherCommsApi = {
  list: async (params?: {
    page?: number;
    page_size?: number;
    type?: string;
    search?: string;
    unread_only?: boolean;
  }) => {
    const response = await api.get('/api/teacher-communications/', { params });
    return response.data as TeacherCommunicationList;
  },

  get: async (id: number) => {
    const response = await api.get(`/api/teacher-communications/${id}`);
    return response.data as TeacherCommunication;
  },

  getStatus: async () => {
    const response = await api.get('/api/teacher-communications/status');
    return response.data as EmailMonitoringStatus;
  },

  markAsRead: async (id: number) => {
    await api.put(`/api/teacher-communications/${id}/read`);
  },

  triggerSync: async () => {
    const response = await api.post('/api/teacher-communications/sync');
    return response.data as { synced: number };
  },

  getEmailMonitoringAuthUrl: async () => {
    const response = await api.get('/api/teacher-communications/auth/email-monitoring');
    return response.data as { authorization_url: string };
  },
};

// Parent Types
export interface ChildSummary {
  student_id: number;
  user_id: number;
  full_name: string;
  grade_level: number | null;
  school_name: string | null;
  relationship_type: string | null;
}

export interface ChildOverview {
  student_id: number;
  user_id: number;
  full_name: string;
  grade_level: number | null;
  google_connected: boolean;
  courses: Array<{ id: number; name: string; description: string | null; subject: string | null; google_classroom_id: string | null; teacher_id: number | null; created_at: string; teacher_name: string | null; teacher_email: string | null }>;
  assignments: Array<{ id: number; title: string; description: string | null; course_id: number; google_classroom_id: string | null; due_date: string | null; max_points: number | null; created_at: string }>;
  study_guides_count: number;
}

export interface DiscoveredChild {
  user_id: number;
  email: string;
  full_name: string;
  google_courses: string[];
  already_linked: boolean;
}

export interface DiscoverChildrenResponse {
  discovered: DiscoveredChild[];
  google_connected: boolean;
  courses_searched: number;
}

// Parent API
export const parentApi = {
  getChildren: async () => {
    const response = await api.get('/api/parent/children');
    return response.data as ChildSummary[];
  },

  getChildOverview: async (studentId: number) => {
    const response = await api.get(`/api/parent/children/${studentId}/overview`);
    return response.data as ChildOverview;
  },

  linkChild: async (studentEmail: string, relationshipType: string = 'guardian') => {
    const response = await api.post('/api/parent/children/link', {
      student_email: studentEmail,
      relationship_type: relationshipType,
    });
    return response.data as ChildSummary;
  },

  discoverViaGoogle: async () => {
    const response = await api.post('/api/parent/children/discover-google');
    return response.data as DiscoverChildrenResponse;
  },

  linkChildrenBulk: async (userIds: number[], relationshipType: string = 'guardian') => {
    const response = await api.post('/api/parent/children/link-bulk', {
      user_ids: userIds,
      relationship_type: relationshipType,
    });
    return response.data as ChildSummary[];
  },

  syncChildCourses: async (studentId: number) => {
    const response = await api.post(`/api/parent/children/${studentId}/sync-courses`);
    return response.data as { message: string; courses: Array<{ id: number; name: string; google_id: string }> };
  },
};

// Invite Types
export interface InviteResponse {
  id: number;
  email: string;
  invite_type: string;
  token: string;
  expires_at: string;
  invited_by_user_id: number;
  metadata_json: Record<string, any> | null;
  accepted_at: string | null;
  created_at: string;
}

// Invites API
export const invitesApi = {
  create: async (data: { email: string; invite_type: string; metadata?: Record<string, any> }) => {
    const response = await api.post('/api/invites/', data);
    return response.data as InviteResponse;
  },

  listSent: async () => {
    const response = await api.get('/api/invites/sent');
    return response.data as InviteResponse[];
  },
};

// Admin Types
export interface AdminUserItem {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface AdminUserList {
  users: AdminUserItem[];
  total: number;
}

export interface AdminStats {
  total_users: number;
  users_by_role: Record<string, number>;
  total_courses: number;
  total_assignments: number;
}

// Admin API
export const adminApi = {
  getStats: async () => {
    const response = await api.get('/api/admin/stats');
    return response.data as AdminStats;
  },

  getUsers: async (params?: { role?: string; search?: string; skip?: number; limit?: number }) => {
    const response = await api.get('/api/admin/users', { params });
    return response.data as AdminUserList;
  },
};
