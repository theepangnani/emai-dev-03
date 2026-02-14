import axios from 'axios';

const API_BASE_URL =
  import.meta.env.VITE_API_URL ??
  (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000');

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

// Handle auth errors with token refresh
let isRefreshing = false;
let failedQueue: Array<{ resolve: (token: string) => void; reject: (err: unknown) => void }> = [];

function processQueue(error: unknown, token: string | null) {
  failedQueue.forEach(p => {
    if (token) p.resolve(token);
    else p.reject(error);
  });
  failedQueue = [];
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const url = originalRequest?.url || '';
    const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/register') || url.includes('/auth/accept-invite') || url.includes('/auth/refresh') || url.includes('/auth/forgot-password') || url.includes('/auth/reset-password');

    if (error.response?.status === 401 && !isAuthEndpoint && !originalRequest._retry) {
      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        localStorage.removeItem('token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token: string) => {
              originalRequest.headers.Authorization = `Bearer ${token}`;
              resolve(api(originalRequest));
            },
            reject,
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const { data } = await axios.post(`${API_BASE_URL}/api/auth/refresh`, { refresh_token: refreshToken });
        localStorage.setItem('token', data.access_token);
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        processQueue(null, data.access_token);
        return api(originalRequest);
      } catch {
        processQueue(error, null);
        localStorage.removeItem('token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(error);
      } finally {
        isRefreshing = false;
      }
    }

    if (error.response?.status === 401 && !isAuthEndpoint) {
      localStorage.removeItem('token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/login';
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

  register: async (data: { email: string; password: string; full_name: string; role: string; teacher_type?: string; google_id?: string }) => {
    const response = await api.post('/api/auth/register', data);
    return response.data;
  },

  getMe: async () => {
    const response = await api.get('/api/users/me');
    return response.data;
  },

  switchRole: async (role: string) => {
    const response = await api.post('/api/users/me/switch-role', { role });
    return response.data;
  },

  acceptInvite: async (token: string, password: string, full_name: string) => {
    const response = await api.post('/api/auth/accept-invite', { token, password, full_name });
    return response.data as { access_token: string; token_type: string; refresh_token?: string };
  },

  forgotPassword: async (email: string) => {
    const response = await api.post('/api/auth/forgot-password', { email });
    return response.data as { message: string };
  },

  resetPassword: async (token: string, new_password: string) => {
    const response = await api.post('/api/auth/reset-password', { token, new_password });
    return response.data as { message: string };
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

  create: async (data: { name: string; description?: string; subject?: string; teacher_email?: string }) => {
    const response = await api.post('/api/courses/', data);
    return response.data;
  },

  update: async (id: number, data: { name?: string; description?: string; subject?: string; teacher_email?: string }) => {
    const response = await api.patch(`/api/courses/${id}`, data);
    return response.data;
  },

  createdByMe: async () => {
    const response = await api.get('/api/courses/created/me');
    return response.data;
  },

  getDefault: async () => {
    const response = await api.get('/api/courses/default');
    return response.data;
  },

  listStudents: async (courseId: number) => {
    const response = await api.get(`/api/courses/${courseId}/students`);
    return response.data as Array<{ student_id: number; user_id: number; full_name: string; email: string; grade_level: number | null }>;
  },

  addStudent: async (courseId: number, email: string) => {
    const response = await api.post(`/api/courses/${courseId}/students`, { email });
    return response.data;
  },

  removeStudent: async (courseId: number, studentId: number) => {
    const response = await api.delete(`/api/courses/${courseId}/students/${studentId}`);
    return response.data;
  },
};

// Course Content API
export interface CourseContentItem {
  id: number;
  course_id: number;
  course_name: string | null;
  title: string;
  description: string | null;
  text_content: string | null;
  content_type: string;
  reference_url: string | null;
  google_classroom_url: string | null;
  created_by_user_id: number;
  created_at: string;
  updated_at: string | null;
  archived_at: string | null;
  last_viewed_at: string | null;
}

export interface CourseContentUpdateResponse extends CourseContentItem {
  archived_guides_count: number;
}

export const courseContentsApi = {
  list: async (courseId: number, contentType?: string) => {
    const params: Record<string, any> = { course_id: courseId };
    if (contentType) params.content_type = contentType;
    const response = await api.get('/api/course-contents/', { params });
    return response.data as CourseContentItem[];
  },

  listAll: async (params?: { student_user_id?: number; content_type?: string; include_archived?: boolean }) => {
    const response = await api.get('/api/course-contents/', { params: params || {} });
    return response.data as CourseContentItem[];
  },

  get: async (id: number) => {
    const response = await api.get(`/api/course-contents/${id}`);
    return response.data as CourseContentItem;
  },

  create: async (data: {
    course_id: number;
    title: string;
    description?: string;
    text_content?: string;
    content_type?: string;
    reference_url?: string;
    google_classroom_url?: string;
  }) => {
    const response = await api.post('/api/course-contents/', data);
    return response.data as CourseContentItem;
  },

  update: async (id: number, data: {
    title?: string;
    description?: string;
    text_content?: string;
    content_type?: string;
    reference_url?: string;
    google_classroom_url?: string;
  }) => {
    const response = await api.patch(`/api/course-contents/${id}`, data);
    return response.data as CourseContentUpdateResponse;
  },

  delete: async (id: number) => {
    await api.delete(`/api/course-contents/${id}`);
  },

  restore: async (id: number) => {
    const response = await api.patch(`/api/course-contents/${id}/restore`);
    return response.data as CourseContentItem;
  },

  permanentDelete: async (id: number) => {
    await api.delete(`/api/course-contents/${id}/permanent`);
  },
};

// Assignments API
export interface AssignmentItem {
  id: number;
  title: string;
  description: string | null;
  course_id: number;
  course_name: string | null;
  google_classroom_id: string | null;
  due_date: string | null;
  max_points: number | null;
  created_at: string;
}

export const assignmentsApi = {
  list: async (courseId?: number): Promise<AssignmentItem[]> => {
    const params = courseId ? { course_id: courseId } : {};
    const response = await api.get('/api/assignments/', { params });
    return response.data;
  },

  get: async (id: number): Promise<AssignmentItem> => {
    const response = await api.get(`/api/assignments/${id}`);
    return response.data;
  },

  create: async (data: { course_id: number; title: string; description?: string; due_date?: string; max_points?: number }): Promise<AssignmentItem> => {
    const response = await api.post('/api/assignments/', data);
    return response.data;
  },

  update: async (id: number, data: { title?: string; description?: string; due_date?: string | null; max_points?: number | null }): Promise<AssignmentItem> => {
    const response = await api.put(`/api/assignments/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/assignments/${id}`);
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
export interface AutoCreatedTask {
  id: number;
  title: string;
  due_date: string;
  priority: string;
}

export interface StudyGuide {
  id: number;
  user_id: number;
  assignment_id: number | null;
  course_id: number | null;
  course_content_id: number | null;
  title: string;
  content: string;
  guide_type: string;
  version: number;
  parent_guide_id: number | null;
  created_at: string;
  archived_at: string | null;
  auto_created_tasks?: AutoCreatedTask[];
}

export interface DuplicateCheckResponse {
  exists: boolean;
  existing_guide: StudyGuide | null;
  message: string | null;
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
  version: number;
  parent_guide_id: number | null;
  created_at: string;
  auto_created_tasks?: AutoCreatedTask[];
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
  version: number;
  parent_guide_id: number | null;
  created_at: string;
  auto_created_tasks?: AutoCreatedTask[];
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
  generateGuide: async (params: { assignment_id?: number; course_id?: number; course_content_id?: number; title?: string; content?: string; regenerate_from_id?: number }) => {
    const response = await api.post('/api/study/generate', params);
    return response.data as StudyGuide;
  },

  generateQuiz: async (params: { assignment_id?: number; course_id?: number; course_content_id?: number; topic?: string; content?: string; num_questions?: number; regenerate_from_id?: number }) => {
    const response = await api.post('/api/study/quiz/generate', params);
    return response.data as Quiz;
  },

  generateFlashcards: async (params: { assignment_id?: number; course_id?: number; course_content_id?: number; topic?: string; content?: string; num_cards?: number; regenerate_from_id?: number }) => {
    const response = await api.post('/api/study/flashcards/generate', params);
    return response.data as FlashcardSet;
  },

  checkDuplicate: async (params: { title?: string; guide_type: string; assignment_id?: number; course_id?: number }) => {
    const response = await api.post('/api/study/check-duplicate', params);
    return response.data as DuplicateCheckResponse;
  },

  listGuides: async (params?: { guide_type?: string; course_id?: number; course_content_id?: number; include_children?: boolean; include_archived?: boolean; student_user_id?: number }) => {
    const response = await api.get('/api/study/guides', { params: params || {} });
    return response.data as StudyGuide[];
  },

  listGuideVersions: async (guideId: number) => {
    const response = await api.get(`/api/study/guides/${guideId}/versions`);
    return response.data as StudyGuide[];
  },

  getGuide: async (id: number) => {
    const response = await api.get(`/api/study/guides/${id}`);
    return response.data as StudyGuide;
  },

  deleteGuide: async (id: number) => {
    await api.delete(`/api/study/guides/${id}`);
  },

  restoreGuide: async (id: number) => {
    const response = await api.patch(`/api/study/guides/${id}/restore`);
    return response.data as StudyGuide;
  },

  permanentDeleteGuide: async (id: number) => {
    await api.delete(`/api/study/guides/${id}/permanent`);
  },

  updateGuide: async (id: number, data: { course_id?: number | null; course_content_id?: number | null }) => {
    const response = await api.patch(`/api/study/guides/${id}`, data);
    return response.data as StudyGuide;
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
    course_id?: number;
    course_content_id?: number;
  }) => {
    const formData = new FormData();
    formData.append('file', params.file);
    if (params.title) formData.append('title', params.title);
    formData.append('guide_type', params.guide_type);
    if (params.num_questions) formData.append('num_questions', params.num_questions.toString());
    if (params.num_cards) formData.append('num_cards', params.num_cards.toString());
    if (params.course_id) formData.append('course_id', params.course_id.toString());
    if (params.course_content_id) formData.append('course_content_id', params.course_content_id.toString());

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
export interface ChildHighlight {
  student_id: number;
  user_id: number;
  full_name: string;
  grade_level: number | null;
  overdue_count: number;
  due_today_count: number;
  upcoming_count: number;
  completed_today_count: number;
  courses: Array<{ id: number; name: string; description: string | null; subject: string | null; google_classroom_id: string | null; teacher_id: number | null; created_at: string; teacher_name: string | null; teacher_email: string | null }>;
  overdue_items: Array<{ title: string; type: string; course_name: string; due_date: string }>;
  due_today_items: Array<{ title: string; type: string; course_name: string; due_date: string }>;
}

export interface ParentDashboardData {
  children: ChildSummary[];
  google_connected: boolean;
  unread_messages: number;
  total_overdue: number;
  total_due_today: number;
  total_tasks: number;
  child_highlights: ChildHighlight[];
  all_assignments: Array<{ id: number; title: string; description: string | null; course_id: number; google_classroom_id: string | null; due_date: string | null; max_points: number | null; created_at: string }>;
  all_tasks: Array<Record<string, any>>;
}

export interface ChildSummary {
  student_id: number;
  user_id: number;
  full_name: string;
  grade_level: number | null;
  school_name: string | null;
  relationship_type: string | null;
  invite_link: string | null;
  course_count: number;
  active_task_count: number;
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

export interface LinkedTeacher {
  id: number;
  student_id: number;
  teacher_user_id: number | null;
  teacher_name: string | null;
  teacher_email: string | null;
  added_by_user_id: number;
  created_at: string | null;
}

// Parent API
export const parentApi = {
  getDashboard: async () => {
    const response = await api.get('/api/parent/dashboard');
    return response.data as ParentDashboardData;
  },

  getChildren: async () => {
    const response = await api.get('/api/parent/children');
    return response.data as ChildSummary[];
  },

  getChildOverview: async (studentId: number) => {
    const response = await api.get(`/api/parent/children/${studentId}/overview`);
    return response.data as ChildOverview;
  },

  linkChild: async (studentEmail: string, relationshipType: string = 'guardian', fullName?: string) => {
    const response = await api.post('/api/parent/children/link', {
      student_email: studentEmail,
      relationship_type: relationshipType,
      ...(fullName ? { full_name: fullName } : {}),
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

  createChild: async (fullName: string, relationshipType: string = 'guardian', email?: string) => {
    const response = await api.post('/api/parent/children/create', {
      full_name: fullName,
      relationship_type: relationshipType,
      ...(email ? { email } : {}),
    });
    return response.data as ChildSummary;
  },

  updateChild: async (studentId: number, data: { full_name?: string; grade_level?: number; school_name?: string }) => {
    const response = await api.patch(`/api/parent/children/${studentId}`, data);
    return response.data as ChildSummary;
  },

  assignCoursesToChild: async (studentId: number, courseIds: number[]) => {
    const response = await api.post(`/api/parent/children/${studentId}/courses`, {
      course_ids: courseIds,
    });
    return response.data as { message: string; assigned: Array<{ course_id: number; course_name: string }> };
  },

  unassignCourseFromChild: async (studentId: number, courseId: number) => {
    const response = await api.delete(`/api/parent/children/${studentId}/courses/${courseId}`);
    return response.data;
  },

  linkTeacher: async (studentId: number, teacherEmail: string, teacherName?: string) => {
    const response = await api.post(`/api/parent/children/${studentId}/teachers`, {
      teacher_email: teacherEmail,
      ...(teacherName ? { teacher_name: teacherName } : {}),
    });
    return response.data as LinkedTeacher;
  },

  getLinkedTeachers: async (studentId: number) => {
    const response = await api.get(`/api/parent/children/${studentId}/teachers`);
    return response.data as LinkedTeacher[];
  },

  unlinkTeacher: async (studentId: number, linkId: number) => {
    const response = await api.delete(`/api/parent/children/${studentId}/teachers/${linkId}`);
    return response.data;
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
  email: string | null;
  full_name: string;
  role: string;
  roles: string[];
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

// Audit Log Types
export interface AuditLogItem {
  id: number;
  user_id: number | null;
  user_name: string | null;
  action: string;
  resource_type: string;
  resource_id: number | null;
  details: string | null;
  ip_address: string | null;
  created_at: string;
}

export interface AuditLogList {
  items: AuditLogItem[];
  total: number;
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

  getAuditLogs: async (params?: { user_id?: number; action?: string; resource_type?: string; date_from?: string; date_to?: string; search?: string; skip?: number; limit?: number }) => {
    const response = await api.get('/api/admin/audit-logs', { params });
    return response.data as AuditLogList;
  },

  addRole: async (userId: number, role: string) => {
    const response = await api.post(`/api/admin/users/${userId}/add-role`, { role });
    return response.data as AdminUserItem;
  },

  removeRole: async (userId: number, role: string) => {
    const response = await api.post(`/api/admin/users/${userId}/remove-role`, { role });
    return response.data as AdminUserItem;
  },
};

// Task Types
export interface TaskItem {
  id: number;
  created_by_user_id: number;
  assigned_to_user_id: number | null;
  title: string;
  description: string | null;
  due_date: string | null;
  is_completed: boolean;
  completed_at: string | null;
  archived_at: string | null;
  priority: string | null;
  category: string | null;
  creator_name: string;
  assignee_name: string | null;
  course_id: number | null;
  course_content_id: number | null;
  study_guide_id: number | null;
  course_name: string | null;
  course_content_title: string | null;
  study_guide_title: string | null;
  study_guide_type: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface AssignableUser {
  user_id: number;
  name: string;
  role: string;
}

// Tasks API
export const tasksApi = {
  get: async (taskId: number) => {
    const response = await api.get(`/api/tasks/${taskId}`);
    return response.data as TaskItem;
  },

  list: async (params?: { assigned_to_user_id?: number; is_completed?: boolean; priority?: string; include_archived?: boolean; course_id?: number }) => {
    const response = await api.get('/api/tasks/', { params });
    return response.data as TaskItem[];
  },

  create: async (data: { title: string; description?: string; due_date?: string; assigned_to_user_id?: number; priority?: string; category?: string; course_id?: number; course_content_id?: number; study_guide_id?: number }) => {
    const response = await api.post('/api/tasks/', data);
    return response.data as TaskItem;
  },

  update: async (taskId: number, data: { title?: string; description?: string; due_date?: string; assigned_to_user_id?: number; is_completed?: boolean; priority?: string; category?: string; course_id?: number; course_content_id?: number; study_guide_id?: number }) => {
    const response = await api.patch(`/api/tasks/${taskId}`, data);
    return response.data as TaskItem;
  },

  delete: async (taskId: number) => {
    await api.delete(`/api/tasks/${taskId}`);
  },

  restore: async (taskId: number) => {
    const response = await api.patch(`/api/tasks/${taskId}/restore`);
    return response.data as TaskItem;
  },

  permanentDelete: async (taskId: number) => {
    await api.delete(`/api/tasks/${taskId}/permanent`);
  },

  getAssignableUsers: async () => {
    const response = await api.get('/api/tasks/assignable-users');
    return response.data as AssignableUser[];
  },
};

// Search Types
export interface SearchResultItem {
  id: number;
  title: string;
  subtitle: string | null;
  entity_type: string;
  url: string;
}

export interface SearchResultGroup {
  entity_type: string;
  label: string;
  items: SearchResultItem[];
  total: number;
}

export interface SearchResponse {
  query: string;
  groups: SearchResultGroup[];
  total: number;
}

// Search API
export const searchApi = {
  search: async (query: string, types?: string, limit?: number) => {
    const params: Record<string, string | number> = { q: query };
    if (types) params.types = types;
    if (limit) params.limit = limit;
    const response = await api.get('/api/search', { params });
    return response.data as SearchResponse;
  },
};

// ── Inspiration Messages ──────────────────────────────────────
export interface InspirationMessage {
  id: number;
  text: string;
  author: string | null;
  role: string;
}

export interface InspirationMessageFull {
  id: number;
  role: string;
  text: string;
  author: string | null;
  is_active: boolean;
  created_at: string | null;
}

export const inspirationApi = {
  getRandom: async () => {
    const response = await api.get('/api/inspiration/random');
    return response.data as InspirationMessage | null;
  },
  list: async (params?: { role?: string; is_active?: boolean }) => {
    const response = await api.get('/api/inspiration/messages', { params });
    return response.data as InspirationMessageFull[];
  },
  create: async (data: { role: string; text: string; author?: string }) => {
    const response = await api.post('/api/inspiration/messages', data);
    return response.data as InspirationMessageFull;
  },
  update: async (id: number, data: { text?: string; author?: string; is_active?: boolean }) => {
    const response = await api.patch(`/api/inspiration/messages/${id}`, data);
    return response.data as InspirationMessageFull;
  },
  delete: async (id: number) => {
    await api.delete(`/api/inspiration/messages/${id}`);
  },
  seed: async () => {
    const response = await api.post('/api/inspiration/seed');
    return response.data as { seeded: number };
  },
};
