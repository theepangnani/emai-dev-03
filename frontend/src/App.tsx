import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { Dashboard } from './pages/Dashboard';
import { StudyGuidePage } from './pages/StudyGuidePage';
import { QuizPage } from './pages/QuizPage';
import { FlashcardsPage } from './pages/FlashcardsPage';
import { MessagesPage } from './pages/MessagesPage';
import { TeacherCommsPage } from './pages/TeacherCommsPage';
import { AcceptInvite } from './pages/AcceptInvite';
import './App.css';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
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
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
