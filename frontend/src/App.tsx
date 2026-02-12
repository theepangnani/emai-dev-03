import { Suspense, lazy, type ComponentType } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { PageLoader } from './components/PageLoader';
import './App.css';

// Retry lazy imports to handle stale chunks after deployment.
// If a chunk 404s (old hash), retry once then force-reload the page.
function lazyRetry<T extends ComponentType<any>>(
  importFn: () => Promise<{ default: T }>,
): React.LazyExoticComponent<T> {
  return lazy(() =>
    importFn().catch(() => {
      // Chunk failed to load — likely stale after a deploy.
      // Only auto-reload once to avoid infinite reload loops.
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
const AcceptInvite = lazyRetry(() => import('./pages/AcceptInvite').then((m) => ({ default: m.AcceptInvite })));

// Clear the chunk reload flag on successful app boot
sessionStorage.removeItem('chunk_reload');

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
        <BrowserRouter>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/accept-invite" element={<AcceptInvite />} />
              <Route
                path="/dashboard"
                element={
                  <ProtectedRoute>
                    <Dashboard />
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
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
    </ThemeProvider>
  );
}

export default App;
