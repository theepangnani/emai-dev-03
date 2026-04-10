import { Suspense, lazy, type ComponentType, type ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { FABProvider } from './context/FABContext';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { ToastProvider } from './components/Toast';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ProtectedRoute } from './components/ProtectedRoute';
import { PageLoader } from './components/PageLoader';
import './App.css';

// Retry lazy imports to handle stale chunks after deployment.
// If a chunk 404s (old hash), reload the page once to get fresh HTML,
// then retry the import. The sessionStorage flag prevents infinite reloads.
function lazyRetry<T extends ComponentType<Record<string, unknown>>>(
  importFn: () => Promise<{ default: T }>,
): React.LazyExoticComponent<T> {
  return lazy(() =>
    importFn()
      .then((module) => {
        if (!module.default) {
          throw new Error('Chunk loaded but export is undefined');
        }
        // Successfully loaded — clear any stale reload flag
        sessionStorage.removeItem('chunk_reload');
        return module;
      })
      .catch(() => {
        // Chunk failed to load — likely stale after a deploy.
        const reloaded = sessionStorage.getItem('chunk_reload');
        if (!reloaded) {
          sessionStorage.setItem('chunk_reload', '1');
          window.location.reload();
          return new Promise(() => {}); // never resolves (page is reloading)
        }
        sessionStorage.removeItem('chunk_reload');
        return importFn(); // final retry after reload
      }),
  );
}

const Login = lazyRetry(() => import('./pages/Login').then((m) => ({ default: m.Login })));
const Register = lazyRetry(() => import('./pages/Register').then((m) => ({ default: m.Register })));
const Dashboard = lazyRetry(() => import('./pages/Dashboard').then((m) => ({ default: m.Dashboard })));
const StudyGuidePage = lazyRetry(() => import('./pages/StudyGuidePage').then((m) => ({ default: m.StudyGuidePage })));
const QuizPage = lazyRetry(() => import('./pages/QuizPage').then((m) => ({ default: m.QuizPage })));
const FlashcardsPage = lazyRetry(() => import('./pages/FlashcardsPage').then((m) => ({ default: m.FlashcardsPage })));
const MessagesPage = lazyRetry(() => import('./pages/MessagesPage').then((m) => ({ default: m.MessagesPage })));
const TeacherCommsPage = lazyRetry(() => import('./pages/TeacherCommsPage').then((m) => ({ default: m.TeacherCommsPage })));
const CoursesPage = lazyRetry(() => import('./pages/CoursesPage').then((m) => ({ default: m.CoursesPage })));
const CourseDetailPage = lazyRetry(() => import('./pages/CourseDetailPage').then((m) => ({ default: m.CourseDetailPage })));
const StudyGuidesListPage = lazyRetry(() => import('./pages/StudyGuidesPage').then((m) => ({ default: m.StudyGuidesPage })));
const TasksPage = lazyRetry(() => import('./pages/TasksPage').then((m) => ({ default: m.TasksPage })));
const TaskDetailPage = lazyRetry(() => import('./pages/TaskDetailPage').then((m) => ({ default: m.TaskDetailPage })));
const CourseMaterialDetailPage = lazyRetry(() => import('./pages/CourseMaterialDetailPage').then((m) => ({ default: m.CourseMaterialDetailPage })));
const AdminAuditLog = lazyRetry(() => import('./pages/AdminAuditLog').then((m) => ({ default: m.AdminAuditLog })));
const AdminInspirationPage = lazyRetry(() => import('./pages/AdminInspirationPage').then((m) => ({ default: m.AdminInspirationPage })));
const AcceptInvite = lazyRetry(() => import('./pages/AcceptInvite').then((m) => ({ default: m.AcceptInvite })));
const MyKidsPage = lazyRetry(() => import('./pages/MyKidsPage').then((m) => ({ default: m.MyKidsPage })));
const ForgotPasswordPage = lazyRetry(() => import('./pages/ForgotPasswordPage').then((m) => ({ default: m.ForgotPasswordPage })));
const ResetPasswordPage = lazyRetry(() => import('./pages/ResetPasswordPage').then((m) => ({ default: m.ResetPasswordPage })));
const PrivacyPolicy = lazyRetry(() => import('./pages/PrivacyPolicy').then((m) => ({ default: m.PrivacyPolicy })));
const TermsOfService = lazyRetry(() => import('./pages/TermsOfService').then((m) => ({ default: m.TermsOfService })));
const LaunchLandingPage = lazyRetry(() => import('./pages/LaunchLandingPage').then((m) => ({ default: m.LaunchLandingPage })));
const OnboardingPage = lazyRetry(() => import('./pages/OnboardingPage').then((m) => ({ default: m.OnboardingPage })));
const VerifyEmailPage = lazyRetry(() => import('./pages/VerifyEmailPage').then((m) => ({ default: m.VerifyEmailPage })));
const HelpPage = lazyRetry(() => import('./pages/HelpPage').then((m) => ({ default: m.HelpPage })));
const FAQPage = lazyRetry(() => import('./pages/FAQPage').then((m) => ({ default: m.FAQPage })));
const FAQDetailPage = lazyRetry(() => import('./pages/FAQDetailPage').then((m) => ({ default: m.FAQDetailPage })));
const AdminFAQPage = lazyRetry(() => import('./pages/AdminFAQPage').then((m) => ({ default: m.AdminFAQPage })));
const AdminWaitlistPage = lazyRetry(() => import('./pages/AdminWaitlistPage').then((m) => ({ default: m.AdminWaitlistPage })));
const AdminAIUsagePage = lazyRetry(() => import('./pages/AdminAIUsagePage').then((m) => ({ default: m.AdminAIUsagePage })));
const AnalyticsPage = lazyRetry(() => import('./pages/AnalyticsPage').then((m) => ({ default: m.AnalyticsPage })));
const GradesPage = lazyRetry(() => import('./pages/GradesPage').then((m) => ({ default: m.GradesPage })));
const NotificationsPage = lazyRetry(() => import('./pages/NotificationsPage').then((m) => ({ default: m.NotificationsPage })));
const LinkRequestsPage = lazyRetry(() => import('./pages/LinkRequestsPage').then((m) => ({ default: m.LinkRequestsPage })));
const QuizHistoryPage = lazyRetry(() => import('./pages/QuizHistoryPage').then((m) => ({ default: m.QuizHistoryPage })));
const EmailSettingsPage = lazyRetry(() => import('./pages/EmailSettingsPage').then((m) => ({ default: m.EmailSettingsPage })));
const DataExportPage = lazyRetry(() => import('./pages/DataExportPage').then((m) => ({ default: m.DataExportPage })));
// StudyPage will be created by another agent — lazy import registered here for the /study route
const StudyPage = lazyRetry(() => import('./pages/StudyPage').then((m) => ({ default: m.StudyPage })));
const WaitlistPage = lazyRetry(() => import('./pages/WaitlistPage').then((m) => ({ default: m.WaitlistPage })));
const ParentBriefingNotesPage = lazyRetry(() => import('./pages/ParentBriefingNotesPage').then((m) => ({ default: m.ParentBriefingNotesPage })));
const NotificationPreferencesPage = lazyRetry(() => import('./pages/NotificationPreferencesPage').then((m) => ({ default: m.NotificationPreferencesPage })));
const AccountSettingsPage = lazyRetry(() => import('./pages/AccountSettingsPage').then((m) => ({ default: m.AccountSettingsPage })));
const CalendarImportPage = lazyRetry(() => import('./pages/CalendarImportPage').then((m) => ({ default: m.CalendarImportPage })));
const ConfirmDeletionPage = lazyRetry(() => import('./pages/ConfirmDeletionPage').then((m) => ({ default: m.ConfirmDeletionPage })));
const AdminDeletionRequestsPage = lazyRetry(() => import('./pages/AdminDeletionRequestsPage').then((m) => ({ default: m.AdminDeletionRequestsPage })));
const ParentAITools = lazyRetry(() => import('./pages/parent/ParentAITools').then((m) => ({ default: m.ParentAITools })));
const ActivityHistoryPage = lazyRetry(() => import('./pages/parent/ActivityHistoryPage').then((m) => ({ default: m.ActivityHistoryPage })));
const ReportCardAnalysis = lazyRetry(() => import('./pages/parent/ReportCardAnalysis').then((m) => ({ default: m.ReportCardAnalysis })));
const EmailDigestPage = lazyRetry(() => import('./pages/parent/EmailDigestPage').then((m) => ({ default: m.EmailDigestPage })));
const ReadinessCheckPage = lazyRetry(() => import('./pages/ReadinessCheckPage').then((m) => ({ default: m.ReadinessCheckPage })));
const WalletPage = lazyRetry(() => import('./pages/WalletPage'));
const SurveyPage = lazyRetry(() => import('./pages/SurveyPage').then((m) => ({ default: m.SurveyPage })));
const AdminSurveyPage = lazyRetry(() => import('./pages/AdminSurveyPage').then((m) => ({ default: m.AdminSurveyPage })));
const XpHistoryPage = lazyRetry(() => import('./pages/XpHistoryPage').then((m) => ({ default: m.XpHistoryPage })));
const BadgesPage = lazyRetry(() => import('./pages/BadgesPage').then((m) => ({ default: m.BadgesPage })));
const StudyTimelinePage = lazyRetry(() => import('./pages/StudyTimelinePage').then((m) => ({ default: m.StudyTimelinePage })));
const ReportCardPage = lazyRetry(() => import('./pages/ReportCardPage').then((m) => ({ default: m.ReportCardPage })));
const StudySessionPage = lazyRetry(() => import('./pages/StudySessionPage').then((m) => ({ default: m.StudySessionPage })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
      retry: 1,
    },
  },
});

function App() {
  return (
    <ThemeProvider>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
        <BrowserRouter>
          <FABProvider>
          <ErrorBoundary>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/onboarding" element={<OnboardingGuard><OnboardingPage /></OnboardingGuard>} />
              <Route path="/accept-invite" element={<AcceptInvite />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />
              <Route path="/verify-email" element={<VerifyEmailPage />} />
              <Route path="/waitlist" element={<WaitlistPage />} />
              <Route path="/survey" element={<SurveyPage />} />
              <Route path="/privacy" element={<PrivacyPolicy />} />
              <Route path="/terms" element={<TermsOfService />} />
              <Route
                path="/dashboard"
                element={
                  <ProtectedRoute>
                    <Dashboard />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/my-kids"
                element={
                  <ProtectedRoute>
                    <MyKidsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/parent-briefing-notes"
                element={
                  <ProtectedRoute allowedRoles={['parent']}>
                    <ParentBriefingNotesPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/readiness-check"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student']}>
                    <ReadinessCheckPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/link-requests"
                element={
                  <ProtectedRoute>
                    <LinkRequestsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/ai-tools"
                element={
                  <ProtectedRoute allowedRoles={['parent']}>
                    <ParentAITools />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/school-report-cards"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student']}>
                    <ReportCardAnalysis />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/activity"
                element={
                  <ProtectedRoute allowedRoles={['parent']}>
                    <ActivityHistoryPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/email-digest"
                element={
                  <ProtectedRoute allowedRoles={['parent']}>
                    <EmailDigestPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/analytics"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student', 'admin']}>
                    <AnalyticsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/grades"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student', 'admin']}>
                    <GradesPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/study/guide/:id"
                element={
                  <ProtectedRoute>
                    <StudyGuidePage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/study/quiz/:id"
                element={
                  <ProtectedRoute>
                    <QuizPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/study/flashcards/:id"
                element={
                  <ProtectedRoute>
                    <FlashcardsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/quiz-history"
                element={
                  <ProtectedRoute>
                    <QuizHistoryPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/study"
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <StudyPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/study/session"
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <StudySessionPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/courses"
                element={
                  <ProtectedRoute>
                    <CoursesPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/courses/:id"
                element={
                  <ProtectedRoute>
                    <CourseDetailPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/course-materials"
                element={
                  <ProtectedRoute>
                    <StudyGuidesListPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/course-materials/:id"
                element={
                  <ProtectedRoute>
                    <CourseMaterialDetailPage />
                  </ProtectedRoute>
                }
              />
              {/* Redirects from old /study-guides URLs */}
              <Route path="/study-guides" element={<Navigate to="/course-materials" replace />} />
              <Route path="/study-guides/:id" element={<Navigate to="/course-materials" replace />} />
              <Route
                path="/tasks"
                element={
                  <ProtectedRoute>
                    <TasksPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/tasks/:id"
                element={
                  <ProtectedRoute>
                    <TaskDetailPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/audit-log"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminAuditLog />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/inspiration"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminInspirationPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/notifications"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student', 'teacher', 'admin']}>
                    <NotificationsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/messages"
                element={
                  <ProtectedRoute>
                    <MessagesPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/teacher-communications"
                element={
                  <ProtectedRoute>
                    <TeacherCommsPage />
                  </ProtectedRoute>
                }
              />
              {/* /tutorial removed — content merged into /help */}
              <Route
                path="/tutorial"
                element={<Navigate to="/help" replace />}
              />
              <Route
                path="/help"
                element={
                  <ProtectedRoute>
                    <HelpPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/faq"
                element={
                  <ProtectedRoute>
                    <FAQPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/faq/:id"
                element={
                  <ProtectedRoute>
                    <FAQDetailPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/faq"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminFAQPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/waitlist"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminWaitlistPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/survey"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminSurveyPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/ai-usage"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminAIUsagePage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings/emails"
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <EmailSettingsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings/notifications"
                element={
                  <ProtectedRoute>
                    <NotificationPreferencesPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings/account"
                element={
                  <ProtectedRoute>
                    <AccountSettingsPage />
                  </ProtectedRoute>
                }
              />
              <Route path="/confirm-deletion" element={<ConfirmDeletionPage />} />
              <Route
                path="/admin/deletion-requests"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminDeletionRequestsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings/calendar-import"
                element={
                  <ProtectedRoute>
                    <CalendarImportPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings/data-export"
                element={
                  <ProtectedRoute>
                    <DataExportPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/xp/history"
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <XpHistoryPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/xp/badges"
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <BadgesPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/activity/timeline"
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <StudyTimelinePage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/report-card"
                element={
                  <ProtectedRoute allowedRoles={['student', 'parent']}>
                    <ReportCardPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/wallet"
                element={
                  <ProtectedRoute>
                    <WalletPage />
                  </ProtectedRoute>
                }
              />
              <Route path="/" element={<HomeRedirect />} />
            </Routes>
          </Suspense>
          </ErrorBoundary>
          </FABProvider>
        </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
    </ThemeProvider>
  );
}

function OnboardingGuard({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) return <PageLoader />;
  if (!user) return <Navigate to="/login" replace />;
  // User already completed onboarding — send them to the dashboard
  if (!user.needs_onboarding && user.onboarding_completed) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

function HomeRedirect() {
  const { user, isLoading } = useAuth();
  if (isLoading) return <PageLoader />;
  if (user && (user.needs_onboarding || !user.onboarding_completed)) return <Navigate to="/onboarding" replace />;
  if (user) return <Navigate to="/dashboard" replace />;
  return <LaunchLandingPage />;
}

export default App;
