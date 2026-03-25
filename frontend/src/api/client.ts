import axios from 'axios';

const API_BASE_URL =
  import.meta.env.VITE_API_URL ??
  (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000');

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000, // 30 seconds default timeout
  headers: {
    'Content-Type': 'application/json',
  },
});

/** Extended timeout (2 minutes) for AI generation and file upload calls. */
export const AI_TIMEOUT = { timeout: 120_000 };

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Retry on 503 Service Unavailable (deploy readiness gate) (#2034, #2065)
api.interceptors.response.use(undefined, async (error) => {
  const config = error.config;
  if (
    error.response?.status === 503 &&
    config &&
    (config._retryCount ?? 0) < 5
  ) {
    config._retryCount = (config._retryCount ?? 0) + 1;
    // Dispatch event so UI can show "reconnecting" indicator
    window.dispatchEvent(new CustomEvent('api:reconnecting', { detail: { attempt: config._retryCount } }));
    // Exponential backoff: 1s, 2s, 4s, 8s, 16s (max ~31s total)
    await new Promise((r) => setTimeout(r, 1000 * Math.pow(2, config._retryCount - 1)));
    return api(config);
  }
  // Clear reconnecting state on final failure
  if (error.response?.status === 503) {
    window.dispatchEvent(new CustomEvent('api:reconnected'));
  }
  return Promise.reject(error);
});

// Clear reconnecting indicator on successful response after retries
api.interceptors.response.use((response) => {
  if ((response.config as unknown as Record<string, unknown>)._retryCount) {
    window.dispatchEvent(new CustomEvent('api:reconnected'));
  }
  return response;
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
export type { CourseContentItem, CourseContentUpdateResponse, LinkedCourseIdsResponse, LinkedCourseChild, AssignmentItem, SubmissionResponse, SubmissionListItem, TeacherCourseManagement, SourceFileItem, LinkedMaterialItem } from './courses';
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
  MindMapData,
  MindMapBranch,
  MindMapBranchGroup,
  MindMap,
  SupportedFormats,
  ExtractedText,
  QuizResultCreate,
  QuizResultResponse,
  QuizResultSummary,
  QuizHistoryStats,
  ResolvedStudent,
  SharedGuideStatus,
  SharedWithMeGuide,
  StudyGuideTreeNode,
  StudyGuideTreeResponse,
} from './study';
export { messagesApi } from './messages';
export type {
  MessageResponse,
  MessageSearchResult,
  MessageSearchResponse,
  MessageSearchParams,
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
  BriefingNote,
  OnTrackSignal,
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
export { tasksApi, icsImportApi } from './tasks';
export type { TaskItem, AssignableUser, ICSEventPreview, ICSParseResponse, ICSImportResponse } from './tasks';
export { inspirationApi } from './inspiration';
export type { InspirationMessage, InspirationMessageFull } from './inspiration';
export { faqApi } from './faq';
export type { FAQQuestionItem, FAQAnswerItem, FAQQuestionDetail } from './faq';
export { analyticsApi } from './analytics';
export type { GradeItem, CourseAverage, GradeSummary, TrendPoint, TrendResponse, AIInsight, WeeklyReport } from './analytics';
export { linkRequestsApi } from './linkRequests';
export type { LinkRequestItem, LinkRequestUser } from './linkRequests';
export { gradesApi } from './grades';
export { waitlistApi } from './waitlist';
export { adminAIUsageApi } from './adminAIUsage';
export type { AIUsageUser, AIUsageUserList, AILimitRequest, AILimitRequestList, AIUsageSummary } from './adminAIUsage';
export type {
  CourseGradeInfo,
  ChildGradeSummary,
  GradeSummaryResponse,
  CourseAssignmentGrade,
  CourseGradesResponse,
  GradeSyncResponse,
} from './grades';
export { aiUsageApi } from './aiUsage';
export type { AIUsageResponse, AIUsageRequestData, AIUsageRequestResponse } from './aiUsage';
export { notesApi } from './notes';
export type { NoteItem, NoteCreateTaskData } from './notes';
export { accountDeletionApi } from './accountDeletion';
export type { DeletionStatus, DeletionRequestItem, DeletionRequestList } from './accountDeletion';
export { dataExportApi } from './dataExport';
export type { DataExportRequest as DataExportRequestItem } from './dataExport';
export { activityApi } from './activity';
export type { ActivityItem } from './activity';
export { xpApi } from './xp';
export type { XpSummary, XpBadge, XpHistoryItem, XpHistoryResponse, XpStreakResponse } from './xp';
export { briefingApi } from './briefing';
export type { DailyBriefingResponse, BriefingChildSection } from './briefing';
export { parentAIApi } from './parentAI';
export type { WeakSpot, WeakSpotsResponse, ReadinessItem, ReadinessCheckResponse, PracticeProblem, PracticeProblemsResponse } from './parentAI';
export { weeklyDigestApi } from './weeklyDigest';
export type { WeeklyDigestResponse, ChildDigest, WeeklyDigestSendResponse } from './weeklyDigest';
export { dailyDigestApi } from './dailyDigest';
export type { DigestSettings, DailyDigestPreview, DigestSendResponse } from './dailyDigest';
