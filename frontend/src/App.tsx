import { Suspense, lazy, type ComponentType, type ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { ToastProvider } from './components/Toast';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ProtectedRoute } from './components/ProtectedRoute';
import { PageLoader } from './components/PageLoader';
import { CookieConsentBanner } from './components/CookieConsentBanner';
import './App.css';

// Retry lazy imports to handle stale chunks after deployment.
// If a chunk 404s (old hash), reload the page once to get fresh HTML,
// then retry the import. The sessionStorage flag prevents infinite reloads.
function lazyRetry<T extends ComponentType<any>>(
  importFn: () => Promise<{ default: T }>,
): React.LazyExoticComponent<T> {
  return lazy(() =>
    importFn()
      .then((module) => {
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
const LandingPage = lazyRetry(() => import('./pages/LandingPage').then((m) => ({ default: m.LandingPage })));
const OnboardingPage = lazyRetry(() => import('./pages/OnboardingPage').then((m) => ({ default: m.OnboardingPage })));
const VerifyEmailPage = lazyRetry(() => import('./pages/VerifyEmailPage').then((m) => ({ default: m.VerifyEmailPage })));
const HelpPage = lazyRetry(() => import('./pages/HelpPage').then((m) => ({ default: m.HelpPage })));
const FAQPage = lazyRetry(() => import('./pages/FAQPage').then((m) => ({ default: m.FAQPage })));
const FAQDetailPage = lazyRetry(() => import('./pages/FAQDetailPage').then((m) => ({ default: m.FAQDetailPage })));
const AdminFAQPage = lazyRetry(() => import('./pages/AdminFAQPage').then((m) => ({ default: m.AdminFAQPage })));
const AnalyticsPage = lazyRetry(() => import('./pages/AnalyticsPage').then((m) => ({ default: m.AnalyticsPage })));
const GradesPage = lazyRetry(() => import('./pages/GradesPage').then((m) => ({ default: m.GradesPage })));
const NotificationsPage = lazyRetry(() => import('./pages/NotificationsPage').then((m) => ({ default: m.NotificationsPage })));
const LinkRequestsPage = lazyRetry(() => import('./pages/LinkRequestsPage').then((m) => ({ default: m.LinkRequestsPage })));
const QuizHistoryPage = lazyRetry(() => import('./pages/QuizHistoryPage').then((m) => ({ default: m.QuizHistoryPage })));
const EmailSettingsPage = lazyRetry(() => import('./pages/EmailSettingsPage').then((m) => ({ default: m.EmailSettingsPage })));
const DocumentsPage = lazyRetry(() => import('./pages/DocumentsPage').then((m) => ({ default: m.DocumentsPage })));
const AccountSettingsPage = lazyRetry(() => import('./pages/AccountSettingsPage').then((m) => ({ default: m.AccountSettingsPage })));
const NotificationPreferencesPage = lazyRetry(() => import('./pages/NotificationPreferencesPage').then((m) => ({ default: m.NotificationPreferencesPage })));
const ReportCardsPage = lazyRetry(() => import('./pages/ReportCardsPage').then((m) => ({ default: m.ReportCardsPage })));
const GradeEntryPage = lazyRetry(() => import('./pages/GradeEntryPage').then((m) => ({ default: m.GradeEntryPage })));
const TeacherMaterialsPage = lazyRetry(() => import('./pages/TeacherMaterialsPage').then((m) => ({ default: m.TeacherMaterialsPage })));
const ExamPage = lazyRetry(() => import('./pages/ExamPage').then((m) => ({ default: m.ExamPage })));
const TeacherExamsPage = lazyRetry(() => import('./pages/TeacherExamsPage').then((m) => ({ default: m.TeacherExamsPage })));
const AIRecommendationsPage = lazyRetry(() => import('./pages/AIRecommendationsPage').then((m) => ({ default: m.AIRecommendationsPage })));
const SemesterPlannerPage = lazyRetry(() => import('./pages/SemesterPlannerPage').then((m) => ({ default: m.SemesterPlannerPage })));
const CoursePlanningPage = lazyRetry(() => import('./pages/CoursePlanningPage').then((m) => ({ default: m.CoursePlanningPage })));
const MultiYearPlannerPage = lazyRetry(() => import('./pages/MultiYearPlannerPage').then((m) => ({ default: m.MultiYearPlannerPage })));
const StudentProgressPage = lazyRetry(() => import('./pages/StudentProgressPage').then((m) => ({ default: m.StudentProgressPage })));
const ExamPrepPage = lazyRetry(() => import('./pages/ExamPrepPage').then((m) => ({ default: m.ExamPrepPage })));
const NotesPage = lazyRetry(() => import('./pages/NotesPage').then((m) => ({ default: m.NotesPage })));
const ProjectsPage = lazyRetry(() => import('./pages/ProjectsPage').then((m) => ({ default: m.ProjectsPage })));
const CurriculumPage = lazyRetry(() => import('./pages/CurriculumPage').then((m) => ({ default: m.CurriculumPage })));
const AdminAnalyticsPage = lazyRetry(() => import('./pages/AdminAnalyticsPage').then(m => ({ default: m.AdminAnalyticsPage })));
const SampleExamsPage = lazyRetry(() => import('./pages/SampleExamsPage').then((m) => ({ default: m.SampleExamsPage })));
const LMSConnectionsPage = lazyRetry(() => import('./pages/LMSConnectionsPage').then((m) => ({ default: m.LMSConnectionsPage })));
const AIInsightsPage = lazyRetry(() => import('./pages/AIInsightsPage').then((m) => ({ default: m.AIInsightsPage })));
const TutorMarketplacePage = lazyRetry(() => import('./pages/TutorMarketplacePage').then((m) => ({ default: m.TutorMarketplacePage })));
const TutorProfilePage = lazyRetry(() => import('./pages/TutorProfilePage').then((m) => ({ default: m.TutorProfilePage })));
const TutorDashboardPage = lazyRetry(() => import('./pages/TutorDashboardPage').then((m) => ({ default: m.TutorDashboardPage })));
const AdminLMSPage = lazyRetry(() => import('./pages/AdminLMSPage').then((m) => ({ default: m.AdminLMSPage })));
const APIKeysPage = lazyRetry(() => import('./pages/APIKeysPage').then((m) => ({ default: m.APIKeysPage })));
const EmailAgentPage = lazyRetry(() => import('./pages/EmailAgentPage'));
const LessonPlannerPage = lazyRetry(() => import('./pages/LessonPlannerPage').then((m) => ({ default: m.LessonPlannerPage })));
const PersonalizationPage = lazyRetry(() => import('./pages/PersonalizationPage'));
const BillingPage = lazyRetry(() => import('./pages/BillingPage').then((m) => ({ default: m.BillingPage })));
const AdminBillingPage = lazyRetry(() => import('./pages/AdminBillingPage').then((m) => ({ default: m.AdminBillingPage })));
const TutorMatchPage = lazyRetry(() => import('./pages/TutorMatchPage').then((m) => ({ default: m.TutorMatchPage })));
const AdminFeatureFlagsPage = lazyRetry(() => import('./pages/AdminFeatureFlagsPage').then((m) => ({ default: m.AdminFeatureFlagsPage })));
const StudentPortfolioPage = lazyRetry(() => import('./pages/StudentPortfolioPage').then((m) => ({ default: m.StudentPortfolioPage })));
const StudyTimerPage = lazyRetry(() => import('./pages/StudyTimerPage').then((m) => ({ default: m.StudyTimerPage })));
const GradePredictionPage = lazyRetry(() => import('./pages/GradePredictionPage').then((m) => ({ default: m.GradePredictionPage })));
const TwoFactorSetupPage = lazyRetry(() => import('./pages/TwoFactorSetupPage').then((m) => ({ default: m.TwoFactorSetupPage })));
const ForumPage = lazyRetry(() => import('./pages/ForumPage').then((m) => ({ default: m.ForumPage })));
const WritingAssistantPage = lazyRetry(() => import('./pages/WritingAssistantPage').then((m) => ({ default: m.WritingAssistantPage })));
const ReminderPreferencesPage = lazyRetry(() => import('./pages/ReminderPreferencesPage').then((m) => ({ default: m.ReminderPreferencesPage })));
const ResourceLibraryPage = lazyRetry(() => import('./pages/ResourceLibraryPage').then((m) => ({ default: m.ResourceLibraryPage })));

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
          <ErrorBoundary>
          <CookieConsentBanner />
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/onboarding" element={<OnboardingGuard><OnboardingPage /></OnboardingGuard>} />
              <Route path="/accept-invite" element={<AcceptInvite />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />
              <Route path="/verify-email" element={<VerifyEmailPage />} />
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
                path="/link-requests"
                element={
                  <ProtectedRoute>
                    <LinkRequestsPage />
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
                path="/documents"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student', 'teacher', 'admin']}>
                    <DocumentsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/report-cards"
                element={
                  <ProtectedRoute allowedRoles={['parent']}>
                    <ReportCardsPage />
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
              <Route
                path="/teacher/grades"
                element={
                  <ProtectedRoute allowedRoles={['teacher', 'admin']}>
                    <GradeEntryPage />
                  </ProtectedRoute>
                }
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
                path="/settings/emails"
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <EmailSettingsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings/account"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student', 'teacher', 'admin']}>
                    <AccountSettingsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/notifications/preferences"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student', 'teacher', 'admin']}>
                    <NotificationPreferencesPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/teacher/materials"
                element={
                  <ProtectedRoute allowedRoles={['teacher', 'admin']}>
                    <TeacherMaterialsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/exams/:assignmentId"
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <ExamPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/teacher/exams"
                element={
                  <ProtectedRoute allowedRoles={['teacher', 'admin']}>
                    <TeacherExamsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/course-planning"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student']}>
                    <CoursePlanningPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/planner"
                element={
                  <ProtectedRoute allowedRoles={['student', 'parent', 'admin']}>
                    <SemesterPlannerPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/planner/overview"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student']}>
                    <MultiYearPlannerPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/planner/ai"
                element={
                  <ProtectedRoute allowedRoles={['student', 'parent']}>
                    <AIRecommendationsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/progress"
                element={
                  <ProtectedRoute allowedRoles={['student', 'parent']}>
                    <StudentProgressPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/exam-prep"
                element={
                  <ProtectedRoute allowedRoles={['student', 'parent']}>
                    <ExamPrepPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/notes"
                element={
                  <ProtectedRoute allowedRoles={['student', 'parent', 'teacher']}>
                    <NotesPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/projects"
                element={
                  <ProtectedRoute allowedRoles={['student', 'parent', 'teacher']}>
                    <ProjectsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/curriculum"
                element={
                  <ProtectedRoute allowedRoles={['teacher', 'admin']}>
                    <CurriculumPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/analytics"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminAnalyticsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/teacher/exams/samples"
                element={
                  <ProtectedRoute allowedRoles={['teacher', 'admin']}>
                    <SampleExamsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings/lms"
                element={
                  <ProtectedRoute allowedRoles={['student', 'parent', 'teacher', 'admin']}>
                    <LMSConnectionsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/insights"
                element={
                  <ProtectedRoute allowedRoles={['parent']}>
                    <AIInsightsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/tutors"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student', 'teacher', 'admin']}>
                    <TutorMarketplacePage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/tutors/:id"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student', 'teacher', 'admin']}>
                    <TutorProfilePage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/tutors/dashboard"
                element={
                  <ProtectedRoute allowedRoles={['teacher']}>
                    <TutorDashboardPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/lms"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminLMSPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings/api-keys"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student', 'teacher', 'admin']}>
                    <APIKeysPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/email-agent"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'teacher', 'student', 'admin']}>
                    <EmailAgentPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/teacher/lesson-plans"
                element={
                  <ProtectedRoute allowedRoles={['teacher', 'admin']}>
                    <LessonPlannerPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/personalization"
                element={
                  <ProtectedRoute allowedRoles={['student', 'parent', 'admin']}>
                    <PersonalizationPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings/billing"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student', 'teacher', 'admin']}>
                    <BillingPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/billing"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminBillingPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/tutor-match"
                element={
                  <ProtectedRoute allowedRoles={['student', 'parent']}>
                    <TutorMatchPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/feature-flags"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminFeatureFlagsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/portfolio"
                element={
                  <ProtectedRoute allowedRoles={['student', 'parent']}>
                    <StudentPortfolioPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/study-timer"
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <StudyTimerPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/grade-prediction"
                element={
                  <ProtectedRoute allowedRoles={['student', 'parent']}>
                    <GradePredictionPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings/2fa"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student', 'teacher', 'admin']}>
                    <TwoFactorSetupPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/forum"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'teacher', 'student', 'admin']}>
                    <ForumPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/writing-assistant"
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <WritingAssistantPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings/reminders"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student', 'teacher', 'admin']}>
                    <ReminderPreferencesPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/resources"
                element={
                  <ProtectedRoute allowedRoles={['teacher', 'admin']}>
                    <ResourceLibraryPage />
                  </ProtectedRoute>
                }
              />
              <Route path="/" element={<HomeRedirect />} />
            </Routes>
          </Suspense>
          </ErrorBoundary>
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
  return <LandingPage />;
}

export default App;
