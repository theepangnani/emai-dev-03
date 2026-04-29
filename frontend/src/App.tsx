import { Suspense, lazy, type ComponentType, type ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { FABProvider } from './context/FABContext';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { ToastProvider } from './components/Toast';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ProtectedRoute } from './components/ProtectedRoute';
import { FeatureGate } from './components/FeatureGate';
import { PageLoader } from './components/PageLoader';
import { SeoDefaults } from './components/SeoDefaults';
import { BridgeDefaultApplier } from './components/BridgeDefaultApplier';
import { useVariantBucket } from './hooks/useVariantBucket';
import { useFeatureFlagState } from './hooks/useFeatureToggle';
import { RedirectPreservingQuery, LegacySessionRedirect } from './lib/routing-helpers';
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
const FlashTutorSessionPage = lazyRetry(() => import('./pages/FlashTutorSessionPage').then((m) => ({ default: m.FlashTutorSessionPage })));
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
const CompliancePage = lazyRetry(() => import('./pages/CompliancePage').then((m) => ({ default: m.CompliancePage })));
const LaunchLandingPage = lazyRetry(() => import('./pages/LaunchLandingPage').then((m) => ({ default: m.LaunchLandingPage })));
const LandingPageV2 = lazyRetry(() => import('./pages/LandingPageV2').then((m) => ({ default: m.LandingPageV2 })));
const OnboardingPage = lazyRetry(() => import('./pages/OnboardingPage').then((m) => ({ default: m.OnboardingPage })));
const VerifyEmailPage = lazyRetry(() => import('./pages/VerifyEmailPage').then((m) => ({ default: m.VerifyEmailPage })));
const HelpPage = lazyRetry(() => import('./pages/HelpPage').then((m) => ({ default: m.HelpPage })));
const FAQPage = lazyRetry(() => import('./pages/FAQPage').then((m) => ({ default: m.FAQPage })));
const FAQDetailPage = lazyRetry(() => import('./pages/FAQDetailPage').then((m) => ({ default: m.FAQDetailPage })));
const AdminFAQPage = lazyRetry(() => import('./pages/AdminFAQPage').then((m) => ({ default: m.AdminFAQPage })));
const AdminWaitlistPage = lazyRetry(() => import('./pages/AdminWaitlistPage').then((m) => ({ default: m.AdminWaitlistPage })));
const AdminDemoSessionsPage = lazyRetry(() => import('./pages/AdminDemoSessionsPage').then((m) => ({ default: m.AdminDemoSessionsPage })));
const AdminContactsPage = lazyRetry(() => import('./pages/AdminContactsPage').then((m) => ({ default: m.AdminContactsPage })));
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
const AdminFeaturesPage = lazyRetry(() => import('./pages/AdminFeaturesPage').then((m) => ({ default: m.AdminFeaturesPage })));
const ParentAITools = lazyRetry(() => import('./pages/parent/ParentAITools').then((m) => ({ default: m.ParentAITools })));
const ActivityHistoryPage = lazyRetry(() => import('./pages/parent/ActivityHistoryPage').then((m) => ({ default: m.ActivityHistoryPage })));
const ReportCardAnalysis = lazyRetry(() => import('./pages/parent/ReportCardAnalysis').then((m) => ({ default: m.ReportCardAnalysis })));
const EmailDigestPage = lazyRetry(() => import('./pages/parent/EmailDigestPage').then((m) => ({ default: m.EmailDigestPage })));
// CB-CMCP-001 M1-F 1F-4 (#4498) — Parent Companion 5-section render page; PARENT-only.
// M3α prequel (#4575): Re-enabled — the GET /api/cmcp/artifacts/{id}/parent-companion
// endpoint now exists and returns the persisted parent companion content
// (or a minimal stub for sync-route artifacts where M1 doesn't run AI).
const ParentCompanionPage = lazyRetry(() => import('./pages/parent/ParentCompanionPage').then((m) => ({ default: m.ParentCompanionPage })));
const GmailOAuthCallbackPage = lazyRetry(() => import('./pages/GmailOAuthCallbackPage').then((m) => ({ default: m.GmailOAuthCallbackPage })));
const ReadinessCheckPage = lazyRetry(() => import('./pages/ReadinessCheckPage').then((m) => ({ default: m.ReadinessCheckPage })));
const WalletPage = lazyRetry(() => import('./pages/WalletPage'));
const SurveyPage = lazyRetry(() => import('./pages/SurveyPage').then((m) => ({ default: m.SurveyPage })));
const AdminSurveyPage = lazyRetry(() => import('./pages/AdminSurveyPage').then((m) => ({ default: m.AdminSurveyPage })));
const XpHistoryPage = lazyRetry(() => import('./pages/XpHistoryPage').then((m) => ({ default: m.XpHistoryPage })));
const BadgesPage = lazyRetry(() => import('./pages/BadgesPage').then((m) => ({ default: m.BadgesPage })));
const StudyTimelinePage = lazyRetry(() => import('./pages/StudyTimelinePage').then((m) => ({ default: m.StudyTimelinePage })));
const ReportCardPage = lazyRetry(() => import('./pages/ReportCardPage').then((m) => ({ default: m.ReportCardPage })));
const StudySessionPage = lazyRetry(() => import('./pages/StudySessionPage').then((m) => ({ default: m.StudySessionPage })));
const AdminOutreachComposer = lazyRetry(() => import('./pages/AdminOutreachComposer').then((m) => ({ default: m.AdminOutreachComposer })));
const TutorPage = lazyRetry(() => import('./pages/TutorPage').then((m) => ({ default: m.TutorPage })));
const LearningCyclePage = lazyRetry(() => import('./pages/LearningCyclePage').then((m) => ({ default: m.LearningCyclePage })));
const DemoVerifiedPage = lazyRetry(() => import('./pages/DemoVerifiedPage').then((m) => ({ default: m.DemoVerifiedPage })));
// CB-DCI-001 M0-9 — kid /checkin flow (3 screens). Gated by `dci_v1_enabled`
// flag; flag-OFF visitors get redirected to `/` by `DciFlagGate`.
const CheckInIntroPage = lazyRetry(() => import('./pages/dci/CheckInIntroPage').then((m) => ({ default: m.CheckInIntroPage })));
const CheckInCapturePage = lazyRetry(() => import('./pages/dci/CheckInCapturePage').then((m) => ({ default: m.CheckInCapturePage })));
const CheckInDonePage = lazyRetry(() => import('./pages/dci/CheckInDonePage').then((m) => ({ default: m.CheckInDonePage })));
// CB-DCI-001 M0-10 — parent /parent/today routes (also gated by DciFlagGate).
const EveningSummaryPage = lazyRetry(() => import('./pages/dci/EveningSummaryPage').then((m) => ({ default: m.EveningSummaryPage })));
const ArtifactDeepDivePage = lazyRetry(() => import('./pages/dci/ArtifactDeepDivePage').then((m) => ({ default: m.ArtifactDeepDivePage })));
const PatternsStubPage = lazyRetry(() => import('./pages/dci/PatternsStubPage').then((m) => ({ default: m.PatternsStubPage })));
// CB-DCI-001 M0-13 — parent consent screen routed at /dci/consent (#4260).
const ConsentScreen = lazyRetry(() => import('./pages/dci/ConsentScreen').then((m) => ({ default: m.ConsentScreen })));
// CB-DCI-001 (#4266) — kid-friendly fallback when /checkin is hit without consent.
const CheckinNeedsConsentPage = lazyRetry(() => import('./pages/dci/CheckinNeedsConsentPage').then((m) => ({ default: m.CheckinNeedsConsentPage })));
// CB-CMCP-001 M0-B 0B-3b (#4429) — curriculum-admin review page; gated to CURRICULUM_ADMIN role + cmcp.enabled flag.
const CEGReviewPage = lazyRetry(() => import('./pages/admin/CEGReviewPage').then((m) => ({ default: m.CEGReviewPage })));

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
      {/* CB-THEME-001: must live INSIDE QueryClientProvider so it can read
          the `theme.bridge_default` feature flag, and INSIDE ThemeProvider
          so it can call applyBridgeDefaultIfUnset(). Renders nothing. */}
      <BridgeDefaultApplier />
      <AuthProvider>
        <ToastProvider>
        <BrowserRouter>
          <FABProvider>
          <ErrorBoundary>
          <SeoDefaults />
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
              <Route path="/demo/verified" element={<DemoVerifiedPage />} />
              <Route path="/survey" element={<SurveyPage />} />
              <Route path="/privacy" element={<PrivacyPolicy />} />
              <Route path="/terms" element={<TermsOfService />} />
              <Route path="/compliance" element={<CompliancePage />} />
              <Route path="/oauth/gmail/callback" element={<GmailOAuthCallbackPage />} />
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
                    <FeatureGate feature="report_cards">
                      <ReportCardAnalysis />
                    </FeatureGate>
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
              {/* CB-CMCP-001 M1-F 1F-4 (#4498) — Parent Companion 5-section render. */}
              {/* M3α prequel (#4575): Backend endpoint now exists; route re-enabled. */}
              <Route
                path="/parent/companion/:artifact_id"
                element={
                  <ProtectedRoute allowedRoles={['parent']}>
                    <ParentCompanionPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/analytics"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student', 'admin']}>
                    <FeatureGate feature="analytics">
                      <AnalyticsPage />
                    </FeatureGate>
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
                path="/tutor"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student', 'teacher']}>
                    <TutorPage />
                  </ProtectedRoute>
                }
              />
              {/* Legacy redirects — keeps deep links working after the
                  Ask + Flash-Tutor merger into /tutor. Uses
                  RedirectPreservingQuery so `?content_id=…`, `?question=…`,
                  etc. from old entry points survive the hop. */}
              <Route path="/ask" element={<RedirectPreservingQuery to="/tutor" />} />
              <Route path="/flash-tutor" element={<RedirectPreservingQuery to="/tutor?mode=drill" />} />
              <Route
                path="/tutor/session/:id"
                element={
                  <ProtectedRoute>
                    <FlashTutorSessionPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/tutor/cycle/:id"
                element={
                  <ProtectedRoute allowedRoles={['parent', 'student', 'teacher']}>
                    <LearningCyclePage />
                  </ProtectedRoute>
                }
              />
              <Route path="/flash-tutor/session/:id" element={<LegacySessionRedirect />} />
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
              {/* CB-CMCP-001 M0-B 0B-3b (#4429) — curriculum-admin review page. */}
              <Route
                path="/admin/ceg/review"
                element={
                  <ProtectedRoute allowedRoles={['CURRICULUM_ADMIN']}>
                    <CEGReviewPage />
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
                path="/admin/demo-sessions"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminDemoSessionsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/contacts/compose"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminOutreachComposer />
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
                path="/admin/contacts"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminContactsPage />
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
                path="/admin/features"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminFeaturesPage />
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
              {/* CB-DCI-001 M0-9 — kid daily check-in /checkin (3 screens).
                  Flag-gated via `dci_v1_enabled`; ProtectedRoute role=student. */}
              <Route
                path="/checkin"
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <DciFlagGate>
                      <CheckInIntroPage />
                    </DciFlagGate>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/checkin/capture"
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <DciFlagGate>
                      <CheckInCapturePage />
                    </DciFlagGate>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/checkin/done"
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <DciFlagGate>
                      <CheckInDonePage />
                    </DciFlagGate>
                  </ProtectedRoute>
                }
              />
              {/* CB-DCI-001 (#4266) — kid-friendly fallback shown when a kid
                  hits /checkin without a parent-saved consent row. The old
                  redirect to /dci/consent (parent-only) caused a silent
                  two-hop bounce; this page replaces it with a "show your
                  parent" message + copy-link affordance. */}
              <Route
                path="/checkin/needs-consent"
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <DciFlagGate>
                      <CheckinNeedsConsentPage />
                    </DciFlagGate>
                  </ProtectedRoute>
                }
              />
              {/* CB-DCI-001 M0-10 — parent /parent/today route block. Flag-gated. */}
              <Route
                path="/parent/today"
                element={
                  <ProtectedRoute allowedRoles={['parent']}>
                    <DciFlagGate>
                      <EveningSummaryPage />
                    </DciFlagGate>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/parent/today/artifact/:id"
                element={
                  <ProtectedRoute allowedRoles={['parent']}>
                    <DciFlagGate>
                      <ArtifactDeepDivePage />
                    </DciFlagGate>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/parent/today/patterns"
                element={
                  <ProtectedRoute allowedRoles={['parent']}>
                    <DciFlagGate>
                      <PatternsStubPage />
                    </DciFlagGate>
                  </ProtectedRoute>
                }
              />
              {/* CB-DCI-001 M0-13 — parent consent screen (#4260). Reads
                  ?return_to= to bounce parents back into /checkin or
                  /parent/today after they grant consent. Settings flow
                  remains the alternate entry. */}
              <Route
                path="/dci/consent"
                element={
                  <ProtectedRoute allowedRoles={['parent']}>
                    <DciFlagGate>
                      <ConsentScreen />
                    </DciFlagGate>
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

/**
 * CB-DCI-001 M0-10 — gates the /parent/today routes behind the
 * `dci_v1_enabled` feature flag (default OFF). When the flag is off the
 * route silently redirects to `/` so the routes are invisible until M0
 * ramps. When it is on, the wrapped page renders.
 */
function DciFlagGate({ children }: { children: ReactNode }) {
  // S-3 (#4216): show a loader while the feature-flag query hydrates so
  // parents with the flag ON don't see a momentary redirect-to-/ flash on
  // cold loads. Once hydrated, redirect when disabled / render when enabled.
  const { enabled, isLoading } = useFeatureFlagState('dci_v1_enabled');
  if (isLoading) return <PageLoader />;
  if (!enabled) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function HomeRedirect() {
  const { user, isLoading } = useAuth();
  // CB-LAND-001 kill-switch (#3802, §6.136.8): anonymous visitors see
  // LandingPageV2 only when the `landing_v2` flag's sticky variant bucket
  // resolves to 'on'. Otherwise the legacy LaunchLandingPage renders —
  // flipping the flag off instantly reverts everyone.
  const landingV2 = useVariantBucket('landing_v2');
  if (isLoading) return <PageLoader />;
  if (user && (user.needs_onboarding || !user.onboarding_completed)) return <Navigate to="/onboarding" replace />;
  if (user) return <Navigate to="/dashboard" replace />;
  return landingV2 === 'on' ? <LandingPageV2 /> : <LaunchLandingPage />;
}

export default App;
