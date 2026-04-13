import axios from 'axios';

const API_BASE_URL =
  import.meta.env.VITE_API_URL ??
  (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000');

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000, // 30 seconds default timeout
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

// Track outstanding reconnecting request chains so the banner stays visible
// until ALL chains complete, and always clears even on non-503 failures (#2623)
let _reconnectingCount = 0;
function _emitReconnecting() {
  _reconnectingCount++;
  window.dispatchEvent(new CustomEvent('api:reconnecting'));
}
function _emitReconnected() {
  _reconnectingCount = Math.max(0, _reconnectingCount - 1);
  if (_reconnectingCount === 0) {
    window.dispatchEvent(new CustomEvent('api:reconnected'));
  }
}

// Retry on 503 Service Unavailable (deploy readiness gate) (#2034, #2065)
api.interceptors.response.use(undefined, async (error) => {
  const config = error.config;
  if (
    error.response?.status === 503 &&
    config &&
    (config._retryCount ?? 0) < 5
  ) {
    config._retryCount = (config._retryCount ?? 0) + 1;
    // Only emit reconnecting on first retry of this chain
    if (config._retryCount === 1) {
      _emitReconnecting();
    }
    // Exponential backoff: 1s, 2s, 4s, 8s, 16s (max ~31s total)
    await new Promise((r) => setTimeout(r, 1000 * Math.pow(2, config._retryCount - 1)));
    try {
      const result = await api(config);
      _emitReconnected();
      return result;
    } catch (retryError) {
      // Clear banner even when retry chain ultimately fails (#2623)
      _emitReconnected();
      return Promise.reject(retryError);
    }
  }
  return Promise.reject(error);
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
    const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/register') || url.includes('/auth/accept-invite') || url.includes('/auth/refresh') || url.includes('/auth/forgot-password') || url.includes('/auth/reset-password') || url.includes('/features');

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
export { coursesApi, courseContentsApi, assignmentsApi, announcementsApi } from './courses';
export type { CourseContentItem, CourseContentUpdateResponse, LinkedCourseIdsResponse, LinkedCourseChild, AssignmentItem, SubmissionResponse, SubmissionListItem, TeacherCourseManagement, SourceFileItem, LinkedMaterialItem, CourseAnnouncementItem, AccessLogEntry, AccessLogResponse } from './courses';
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
  Worksheet,
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
export { teacherCommsApi, teacherThanksApi } from './teachers';
export type {
  TeacherCommunication,
  TeacherCommunicationList,
  EmailMonitoringStatus,
  TeacherThanksCount,
  TeacherThanksStatus,
  TeacherThanksResponse,
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
export { dailyQuizApi } from './dailyQuiz';
export type { DailyQuizQuestion, DailyQuizResponse, DailyQuizSubmitResponse } from './dailyQuiz';
