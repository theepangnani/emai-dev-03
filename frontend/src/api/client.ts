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

// Re-export all API modules and types for backward compatibility
export { authApi } from './auth';
export { coursesApi, courseContentsApi, assignmentsApi } from './courses';
export type { CourseContentItem, CourseContentUpdateResponse, AssignmentItem } from './courses';
export { googleApi } from './google';
export type { GoogleAccount } from './google';
export { studyApi } from './study';
export type {
  AutoCreatedTask,
  StudyGuide,
  DuplicateCheckResponse,
  QuizQuestion,
  Quiz,
  Flashcard,
  FlashcardSet,
  SupportedFormats,
  ExtractedText,
} from './study';
export { messagesApi } from './messages';
export type {
  MessageResponse,
  ConversationSummary,
  ConversationDetail,
  RecipientOption,
} from './messages';
export { notificationsApi } from './notifications';
export type { NotificationResponse, NotificationPreferences } from './notifications';
export { teacherCommsApi } from './teachers';
export type {
  TeacherCommunication,
  TeacherCommunicationList,
  EmailMonitoringStatus,
} from './teachers';
export { parentApi } from './parent';
export type {
  ChildHighlight,
  ParentDashboardData,
  ChildSummary,
  ChildOverview,
  DiscoveredChild,
  DiscoverChildrenResponse,
  LinkedTeacher,
} from './parent';
export { invitesApi } from './invites';
export type { InviteResponse } from './invites';
export { adminApi } from './admin';
export type {
  AdminUserItem,
  AdminUserList,
  AdminStats,
  AuditLogItem,
  AuditLogList,
  BroadcastResponse,
  BroadcastItem,
} from './admin';
export { tasksApi } from './tasks';
export type { TaskItem, AssignableUser } from './tasks';
export { searchApi } from './search';
export type { SearchResultItem, SearchResultGroup, SearchResponse } from './search';
export { inspirationApi } from './inspiration';
export type { InspirationMessage, InspirationMessageFull } from './inspiration';
export { faqApi } from './faq';
export type { FAQQuestionItem, FAQAnswerItem, FAQQuestionDetail } from './faq';
export { analyticsApi } from './analytics';
export type { GradeItem, CourseAverage, GradeSummary, TrendPoint, TrendResponse, AIInsight, WeeklyReport } from './analytics';
