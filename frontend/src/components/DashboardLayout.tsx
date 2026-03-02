import { useMemo, useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import { messagesApi, inspirationApi } from '../api/client';
import { useLastVisitedPage } from '../hooks/useLastVisitedPage';
import type { InspirationMessage } from '../api/client';
import { NotificationBell } from './NotificationBell';
import { GlobalSearch } from './GlobalSearch';
import { ThemeToggle } from './ThemeToggle';
import { LanguageToggle } from './LanguageToggle';
import { KeyboardShortcutsModal } from './KeyboardShortcutsModal';
import { OnboardingTour, PARENT_TOUR_STEPS, STUDENT_TOUR_STEPS, TEACHER_TOUR_STEPS } from './OnboardingTour';
import { QuickActionFAB } from './QuickActionFAB';
import type { FABAction } from './QuickActionFAB';
import { CreateTaskModal } from './CreateTaskModal';
import { OfflineIndicator } from './OfflineIndicator';
import { getMyXP } from '../api/gamification';
import { useFeatureFlags } from '../hooks/useFeatureFlag';
import '../pages/Dashboard.css';

// Map nav paths to feature flag keys. Items without a mapping are always shown.
const PATH_FLAG_MAP: Record<string, string> = {
  '/courses': 'google_classroom',
  '/course-materials': 'google_classroom',
  '/documents': 'document_repository',
  '/report-cards': 'grade_tracking',
  '/grades': 'grade_tracking',
  '/grade-prediction': 'grade_tracking',
  '/teacher/grades': 'grade_tracking',
  '/messages': 'messaging',
  '/teacher-communications': 'teacher_email_monitoring',
  '/notifications': 'notification_system',
  '/settings/reminders': 'notification_system',
  '/settings/lms': 'multi_lms',
  '/admin/lms': 'multi_lms',
  '/notes': 'notes_projects',
  '/projects': 'notes_projects',
  '/faq': 'faq_knowledge_base',
  '/tutors': 'tutor_marketplace',
  '/tutor-match': 'tutor_marketplace',
  '/tutors/dashboard': 'tutor_marketplace',
  '/forum': 'parent_forum',
  '/resources': 'teacher_resources',
  '/email-agent': 'ai_email_agent',
  '/settings/emails': 'ai_email_agent',
  '/settings/billing': 'stripe_billing',
  '/admin/billing': 'stripe_billing',
  '/teacher/lesson-plans': 'lesson_planner',
  '/personalization': 'ai_personalization',
  '/course-planning': 'course_planning',
  '/planner': 'course_planning',
  '/curriculum': 'course_planning',
  '/exam-prep': 'course_planning',
  '/writing-assistant': 'ai_writing_assistant',
  '/teacher/exams': 'ai_mock_exams',
  '/teacher/exams/samples': 'ai_mock_exams',
  '/study-timer': 'student_engagement',
  '/achievements': 'student_engagement',
  '/portfolio': 'student_engagement',
  '/quiz-history': 'ai_study_tools',
  '/progress': 'ai_study_tools',
};

interface SidebarAction {
  label: string;
  icon?: string;
  onClick: () => void;
}

export interface InspirationData {
  text: string;
  author: string | null;
}

interface DashboardLayoutProps {
  children: React.ReactNode;
  welcomeSubtitle?: string;
  sidebarActions?: SidebarAction[];
  /** @deprecated Use <PageNav> inside page content instead. Kept for backward compat. */
  showBackButton?: boolean;
  /** When provided, replaces the default welcome section. Receives inspiration data. */
  headerSlot?: (inspiration: InspirationData | null) => React.ReactNode;
}

// Module-level cache so inspiration persists across DashboardLayout remounts (page navigations)
let cachedInspiration: InspirationMessage | null = null;

// SVG icon component for nav items (Feather/Lucide style)
const NAV_SVG: Record<string, React.ReactNode> = {
  Home: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
      <polyline points="9 22 9 12 15 12 15 22"/>
    </svg>
  ),
  'My Kids': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
      <circle cx="9" cy="7" r="4"/>
      <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
      <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
    </svg>
  ),
  Classes: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
    </svg>
  ),
  Materials: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="16" y1="13" x2="8" y2="13"/>
      <line x1="16" y1="17" x2="8" y2="17"/>
    </svg>
  ),
  'My Materials': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="16" y1="13" x2="8" y2="13"/>
      <line x1="16" y1="17" x2="8" y2="17"/>
    </svg>
  ),
  'Quiz History': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10"/>
      <line x1="12" y1="20" x2="12" y2="4"/>
      <line x1="6" y1="20" x2="6" y2="14"/>
    </svg>
  ),
  Tasks: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 11 12 14 22 4"/>
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
    </svg>
  ),
  Messages: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
  ),
  'Teacher Comms': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
      <polyline points="22,6 12,13 2,6"/>
    </svg>
  ),
  Help: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
      <line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  ),
  Documents: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
    </svg>
  ),
  Analytics: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10"/>
      <line x1="12" y1="20" x2="12" y2="4"/>
      <line x1="6" y1="20" x2="6" y2="14"/>
    </svg>
  ),
  FAQ: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
      <line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  ),
  Account: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
      <circle cx="12" cy="7" r="4"/>
    </svg>
  ),
  Grades: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
      <polyline points="22 4 12 14.01 9 11.01"/>
    </svg>
  ),
  'Report Cards': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="16" y1="13" x2="8" y2="13"/>
      <line x1="16" y1="17" x2="8" y2="17"/>
      <line x1="10" y1="9" x2="8" y2="9"/>
    </svg>
  ),
  'Grade Entry': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
      <line x1="3" y1="9" x2="21" y2="9"/>
      <line x1="3" y1="15" x2="21" y2="15"/>
      <line x1="9" y1="9" x2="9" y2="21"/>
      <line x1="15" y1="9" x2="15" y2="21"/>
    </svg>
  ),
  'Mock Exams': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
      <rect x="9" y="3" width="6" height="4" rx="1"/>
      <line x1="9" y1="12" x2="15" y2="12"/>
      <line x1="9" y1="16" x2="12" y2="16"/>
    </svg>
  ),
  'Course Planning': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2L2 7l10 5 10-5-10-5z"/>
      <path d="M2 17l10 5 10-5"/>
      <path d="M2 12l10 5 10-5"/>
    </svg>
  ),
  'Course Planner': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
      <line x1="16" y1="2" x2="16" y2="6"/>
      <line x1="8" y1="2" x2="8" y2="6"/>
      <line x1="3" y1="10" x2="21" y2="10"/>
      <line x1="8" y1="14" x2="8" y2="14"/>
      <line x1="12" y1="14" x2="12" y2="14"/>
      <line x1="16" y1="14" x2="16" y2="14"/>
    </svg>
  ),
  Progress: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <polyline points="12 6 12 12 16 14"/>
    </svg>
  ),
  'Exam Prep': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
      <rect x="9" y="3" width="6" height="4" rx="1"/>
      <line x1="9" y1="12" x2="15" y2="12"/>
      <line x1="9" y1="16" x2="12" y2="16"/>
    </svg>
  ),
  Notes: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
    </svg>
  ),
  Projects: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7"/>
      <rect x="14" y="3" width="7" height="7"/>
      <rect x="14" y="14" width="7" height="7"/>
      <rect x="3" y="14" width="7" height="7"/>
    </svg>
  ),
  Curriculum: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
      <line x1="10" y1="8" x2="16" y2="8"/>
      <line x1="10" y1="12" x2="16" y2="12"/>
    </svg>
  ),
  'Sample Exams': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="9" y1="12" x2="15" y2="12"/>
      <line x1="9" y1="16" x2="12" y2="16"/>
      <circle cx="17" cy="17" r="3"/>
      <line x1="19.5" y1="19.5" x2="21" y2="21"/>
    </svg>
  ),
  'LMS Connections': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
    </svg>
  ),
  'AI Insights': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
    </svg>
  ),
  'Find a Tutor': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
      <circle cx="12" cy="7" r="4"/>
      <circle cx="19" cy="19" r="3"/>
      <line x1="21" y1="21" x2="19.5" y2="19.5"/>
    </svg>
  ),
  'Tutor Dashboard': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
      <circle cx="12" cy="7" r="4"/>
      <polyline points="16 11 18 13 22 9"/>
    </svg>
  ),
  'LMS Admin': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
      <line x1="8" y1="21" x2="16" y2="21"/>
      <line x1="12" y1="17" x2="12" y2="21"/>
      <path d="M6 8h.01M6 12h.01M10 8h8M10 12h8"/>
    </svg>
  ),
  'API Keys': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>
    </svg>
  ),
  'Two-Factor Auth': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      <polyline points="9 12 11 14 15 10"/>
    </svg>
  ),
  'AI Email': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
      <polyline points="22,6 12,13 2,6"/>
      <circle cx="18" cy="8" r="3" fill="currentColor" opacity="0.6"/>
    </svg>
  ),
  Forum: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
      <circle cx="9" cy="7" r="4"/>
      <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
      <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
      <polyline points="19 11 21 13 23 11"/>
    </svg>
  ),
  'Lesson Planner': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
      <rect x="9" y="3" width="6" height="4" rx="1"/>
      <line x1="9" y1="12" x2="15" y2="12"/>
      <line x1="9" y1="16" x2="11" y2="16"/>
    </svg>
  ),
  'Resource Library': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
      <line x1="9" y1="8" x2="15" y2="8"/>
      <line x1="9" y1="12" x2="15" y2="12"/>
      <circle cx="17" cy="17" r="3"/>
      <line x1="19.5" y1="19.5" x2="21" y2="21"/>
    </svg>
  ),
  'My Learning': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z"/>
      <path d="M12 6v6l4 2"/>
    </svg>
  ),
  'Grade Predictions': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
    </svg>
  ),
  'Writing Assistant': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
      <circle cx="20" cy="4" r="1" fill="currentColor"/>
    </svg>
  ),
  'Billing': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="1" y="4" width="22" height="16" rx="2" ry="2"/>
      <line x1="1" y1="10" x2="23" y2="10"/>
    </svg>
  ),
  'Billing Admin': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10"/>
      <line x1="12" y1="20" x2="12" y2="4"/>
      <line x1="6" y1="20" x2="6" y2="14"/>
      <rect x="1" y="1" width="6" height="6" rx="1"/>
    </svg>
  ),
  Portfolio: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 7V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v16l-7-3-7 3V7"/>
      <path d="M8 10h8M8 14h5"/>
    </svg>
  ),
  'Study Timer': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="13" r="8"/>
      <path d="M12 9v4l2.5 2.5"/>
      <path d="M5 3L3 5"/>
      <path d="M19 3l2 2"/>
      <path d="M12 3V1"/>
    </svg>
  ),
  'Reminder Settings': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
      <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
      <line x1="12" y1="2" x2="12" y2="4"/>
    </svg>
  ),
  'Peer Review': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
      <circle cx="9" cy="7" r="4"/>
      <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
      <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
      <polyline points="16 16 18 18 22 14"/>
    </svg>
  ),
  Goals: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <circle cx="12" cy="12" r="6"/>
      <circle cx="12" cy="12" r="2"/>
    </svg>
  ),
  'Homework Help': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z"/>
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
      <circle cx="12" cy="17" r="0.5" fill="currentColor" stroke="currentColor"/>
    </svg>
  ),
  Attendance: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
      <line x1="16" y1="2" x2="16" y2="6"/>
      <line x1="8" y1="2" x2="8" y2="6"/>
      <line x1="3" y1="10" x2="21" y2="10"/>
      <polyline points="9 16 11 18 15 14"/>
    </svg>
  ),
  Wellness: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
    </svg>
  ),
  Achievements: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="6"/>
      <path d="M15.477 12.89L17 22l-5-3-5 3 1.523-9.11"/>
    </svg>
  ),
  Newsletter: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
      <polyline points="22,6 12,13 2,6"/>
      <line x1="8" y1="17" x2="12" y2="17"/>
      <line x1="8" y1="13" x2="10" y2="13"/>
    </svg>
  ),
  Meetings: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
      <line x1="16" y1="2" x2="16" y2="6"/>
      <line x1="8" y1="2" x2="8" y2="6"/>
      <line x1="3" y1="10" x2="21" y2="10"/>
      <circle cx="8" cy="15" r="1" fill="currentColor"/>
      <circle cx="12" cy="15" r="1" fill="currentColor"/>
    </svg>
  ),
  'Lesson Summarizer': (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="16" y1="13" x2="8" y2="13"/>
      <line x1="13" y1="17" x2="8" y2="17"/>
      <circle cx="19" cy="18" r="3"/>
      <path d="M19 16v2l1 1"/>
    </svg>
  ),
  Journal: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
      <path d="M12 8h4M12 12h4M8 16h.01"/>
      <circle cx="8" cy="8" r="1" fill="currentColor"/>
      <circle cx="8" cy="12" r="1" fill="currentColor"/>
    </svg>
  ),
};

const NavIcon = ({ name }: { name: string }) => {
  return NAV_SVG[name] || <span>{name[0]}</span>;
};

// Quick action SVG icons — maps sidebar action labels to nav SVGs
const QUICK_ACTION_SVG: Record<string, React.ReactNode> = {
  '+ Class Material': NAV_SVG.Materials,
  '+ Course Material': NAV_SVG.Materials,
  '+ Create Class Material': NAV_SVG.Materials,
  '+ Task': NAV_SVG.Tasks,
  '+ Child': NAV_SVG['My Kids'],
  '+ Add Child': NAV_SVG['My Kids'],
  '+ Class': NAV_SVG.Classes,
  '+ Add Class': NAV_SVG.Classes,
  '+ Create Study Material': NAV_SVG.Materials,
};

export function DashboardLayout({ children, welcomeSubtitle, sidebarActions, headerSlot }: DashboardLayoutProps) {
  const { user, logout, switchRole, resendVerification } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Track last visited page for session persistence (#886)
  useLastVisitedPage();

  const [unreadCount, setUnreadCount] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const [roleSwitcherOpen, setRoleSwitcherOpen] = useState(false);
  const roleSwitcherRef = useRef<HTMLDivElement>(null);
  const [inspiration, setInspiration] = useState<InspirationMessage | null>(cachedInspiration);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [quickActionsOpen, setQuickActionsOpen] = useState(false);
  const [verifyBannerDismissed, setVerifyBannerDismissed] = useState(false);
  const [resendStatus, setResendStatus] = useState<'idle' | 'sending' | 'sent'>('idle');
  const [showFabTaskModal, setShowFabTaskModal] = useState(false);

  const hasMultipleRoles = (user?.roles?.length ?? 0) > 1;
  const { flags } = useFeatureFlags();

  // XP level badge — only fetched for students and parents
  const { data: userXP } = useQuery({
    queryKey: ['xp', 'me'],
    queryFn: getMyXP,
    enabled: user?.role === 'student' || user?.role === 'parent',
    staleTime: 60_000,
  });

  const navItems = useMemo(() => {
    if (user?.role === 'parent') {
      return [
        { label: 'Home', path: '/dashboard' },
        { label: 'My Kids', path: '/my-kids' },
        { label: 'Attendance', path: '/attendance' },
        { label: 'Achievements', path: '/achievements' },
        { label: 'Wellness', path: '/wellness' },
        { label: 'Goals', path: '/goals' },
        { label: 'Meetings', path: '/meetings' },
        { label: 'AI Insights', path: '/insights' },
        { label: 'Grade Predictions', path: '/grade-prediction' },
        { label: 'Course Planning', path: '/course-planning' },
        { label: 'Documents', path: '/documents' },
        { label: 'Report Cards', path: '/report-cards' },
        { label: 'Tasks', path: '/tasks' },
        { label: 'Grades', path: '/grades' },
        { label: 'Progress', path: '/progress' },
        { label: 'Analytics', path: '/analytics' },
        { label: 'Messages', path: '/messages' },
        { label: 'Forum', path: '/forum' },
        { label: 'My Learning', path: '/personalization' },
        { label: 'AI Email', path: '/email-agent' },
        { label: 'Notes', path: '/notes' },
        { label: 'Projects', path: '/projects' },
        { label: 'Find a Tutor', path: '/tutors' },
        { label: 'Tutor Match', path: '/tutor-match' },
        { label: 'FAQ', path: '/faq' },
        { label: 'Help', path: '/help' },
        { label: 'LMS Connections', path: '/settings/lms' },
        { label: 'Billing', path: '/settings/billing' },
        { label: 'API Keys', path: '/settings/api-keys' },
        { label: 'Two-Factor Auth', path: '/settings/2fa' },
        { label: 'Reminder Settings', path: '/settings/reminders' },
        { label: 'Account', path: '/settings/account' },
      ].filter(item => {
        const flagKey = PATH_FLAG_MAP[item.path];
        return !flagKey || flags[flagKey] !== false;
      });
    }

    const items: Array<{ label: string; path: string }> = [
      { label: 'Home', path: '/dashboard' },
      { label: 'Classes', path: '/courses' },
      { label: 'Materials', path: '/course-materials' },
      { label: 'Documents', path: '/documents' },
    ];

    if (user?.role === 'student') {
      items.push({ label: 'Portfolio', path: '/portfolio' });
      items.push({ label: 'Achievements', path: '/achievements' });
      items.push({ label: 'Goals', path: '/goals' });
      items.push({ label: 'Course Planning', path: '/course-planning' });
      items.push({ label: 'Course Planner', path: '/planner' });
      items.push({ label: 'Study Timer', path: '/study-timer' });
      items.push({ label: 'Quiz History', path: '/quiz-history' });
      items.push({ label: 'Writing Assistant', path: '/writing-assistant' });
      items.push({ label: 'Homework Help', path: '/homework-help' });
      items.push({ label: 'Lesson Summarizer', path: '/lesson-summarizer' });
      items.push({ label: 'Peer Review', path: '/peer-review' });
      items.push({ label: 'Journal', path: '/journal' });
      items.push({ label: 'My Emails', path: '/settings/emails' });
      items.push({ label: 'Find a Tutor', path: '/tutors' });
      items.push({ label: 'Tutor Match', path: '/tutor-match' });
    }

    items.push(
      { label: 'Tasks', path: '/tasks' },
      { label: 'Messages', path: '/messages' },
    );

    if (user?.role === 'student') {
      items.push({ label: 'Grades', path: '/grades' });
      items.push({ label: 'Grade Predictions', path: '/grade-prediction' });
      items.push({ label: 'Exam Prep', path: '/exam-prep' });
      items.push({ label: 'Progress', path: '/progress' });
      items.push({ label: 'Analytics', path: '/analytics' });
      items.push({ label: 'Wellness', path: '/wellness' });
      items.push({ label: 'My Learning', path: '/personalization' });
      items.push({ label: 'Forum', path: '/forum' });
    }

    if (user?.role === 'teacher') {
      items.push({ label: 'Attendance', path: '/attendance' });
      items.push({ label: 'Mock Exams', path: '/teacher/exams' });
      items.push({ label: 'Sample Exams', path: '/teacher/exams/samples' });
      items.push({ label: 'My Materials', path: '/teacher/materials' });
      items.push({ label: 'Grade Entry', path: '/teacher/grades' });
      items.push({ label: 'Teacher Comms', path: '/teacher-communications' });
      items.push({ label: 'Curriculum', path: '/curriculum' });
      items.push({ label: 'Lesson Planner', path: '/teacher/lesson-plans' });
      items.push({ label: 'Resource Library', path: '/resources' });
      items.push({ label: 'Peer Review', path: '/peer-review' });
      items.push({ label: 'Meetings', path: '/meetings' });
      items.push({ label: 'Newsletter', path: '/newsletter' });
      items.push({ label: 'AI Email', path: '/email-agent' });
      items.push({ label: 'Tutor Dashboard', path: '/tutors/dashboard' });
      items.push({ label: 'Forum', path: '/forum' });
    }

    if (user?.role === 'parent' || user?.role === 'teacher') {
      // Already added in parent block above; add for teacher here if not parent
    }

    items.push({ label: 'Notes', path: '/notes' });
    items.push({ label: 'Projects', path: '/projects' });
    items.push({ label: 'FAQ', path: '/faq' });
    items.push({ label: 'Help', path: '/help' });

    if (user?.role === 'admin') {
      items.push({ label: 'Analytics', path: '/admin/analytics' });
      items.push({ label: 'LMS Admin', path: '/admin/lms' });
      items.push({ label: 'Billing Admin', path: '/admin/billing' });
      items.push({ label: 'Feature Flags', path: '/admin/feature-flags' });
      items.push({ label: 'Newsletter', path: '/newsletter' });
      items.push({ label: 'Lesson Summarizer', path: '/lesson-summarizer' });
      items.push({ label: 'My Learning', path: '/personalization' });
      items.push({ label: 'AI Email', path: '/email-agent' });
    }

    items.push({ label: 'LMS Connections', path: '/settings/lms' });
    items.push({ label: 'Billing', path: '/settings/billing' });
    items.push({ label: 'API Keys', path: '/settings/api-keys' });
    items.push({ label: 'Two-Factor Auth', path: '/settings/2fa' });
    items.push({ label: 'Reminder Settings', path: '/settings/reminders' });
    items.push({ label: 'Account', path: '/settings/account' });

    // Filter out nav items whose feature flag is disabled
    return items.filter(item => {
      const flagKey = PATH_FLAG_MAP[item.path];
      return !flagKey || flags[flagKey] !== false;
    });
  }, [user?.role, flags]);

  useEffect(() => {
    const loadUnreadCount = async () => {
      try {
        const data = await messagesApi.getUnreadCount();
        setUnreadCount(data.total_unread);
      } catch {
        // Silently fail
      }
    };

    loadUnreadCount();
    const interval = setInterval(loadUnreadCount, 60000);
    return () => clearInterval(interval);
  }, []);

  // Load inspirational message once per session (cached across remounts)
  useEffect(() => {
    if (cachedInspiration) return;
    inspirationApi.getRandom().then((msg) => {
      cachedInspiration = msg;
      setInspiration(msg);
    }).catch(() => {});
  }, []);

  // Close menu when route changes
  useEffect(() => {
    // Menu close is intentionally synchronous here to provide immediate feedback on navigation
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMenuOpen(false);
    setQuickActionsOpen(false);
  }, [location.pathname]);

  // Close role switcher on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (roleSwitcherRef.current && !roleSwitcherRef.current.contains(e.target as Node)) {
        setRoleSwitcherOpen(false);
      }
    };
    if (roleSwitcherOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [roleSwitcherOpen]);

  // Keyboard shortcuts: ? key opens legend
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT') return;
      if (e.key === '?') {
        e.preventDefault();
        setShowShortcuts(true);
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, []);

  // Build the full quick actions list for persistent sidebar (non-parent roles only)
  const persistentQuickActions = useMemo(() => {
    return sidebarActions || [];
  }, [sidebarActions]);

  // Paths where the FAB should not be shown
  const FAB_EXCLUDED_PATHS = ['/login', '/register', '/onboarding', '/admin'];
  const showFAB = user !== null && !FAB_EXCLUDED_PATHS.some(p => location.pathname.startsWith(p));

  // Role-specific FAB actions
  const fabActions = useMemo((): FABAction[] => {
    if (!user) return [];

    // Common SVG icon helpers (inline to avoid importing a large icon library)
    const IconTask = (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <polyline points="9 11 12 14 22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
    );
    const IconStudyGuide = (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      </svg>
    );
    const IconMessage = (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    );
    const IconAddChild = (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <line x1="19" y1="8" x2="19" y2="14" />
        <line x1="22" y1="11" x2="16" y2="11" />
      </svg>
    );
    const IconSync = (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <polyline points="23 4 23 10 17 10" />
        <polyline points="1 20 1 14 7 14" />
        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
      </svg>
    );
    const IconFlashcards = (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
        <line x1="8" y1="21" x2="16" y2="21" />
        <line x1="12" y1="17" x2="12" y2="21" />
      </svg>
    );
    const IconUpload = (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="17 8 12 3 7 8" />
        <line x1="12" y1="3" x2="12" y2="15" />
      </svg>
    );
    const IconBroadcast = (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M22 17H2a3 3 0 0 0 3-3V9a7 7 0 0 1 14 0v5a3 3 0 0 0 3 3z" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
    );

    if (user.role === 'parent') {
      return [
        {
          label: 'Add Task',
          icon: IconTask,
          onClick: () => setShowFabTaskModal(true),
        },
        {
          label: 'Study Guide',
          icon: IconStudyGuide,
          onClick: () => navigate('/courses?action=study-guide'),
        },
        {
          label: 'Send Message',
          icon: IconMessage,
          onClick: () => navigate('/messages?compose=true'),
        },
        {
          label: 'Add Child',
          icon: IconAddChild,
          onClick: () => navigate('/dashboard?add-child=true'),
        },
        {
          label: 'Sync Classroom',
          icon: IconSync,
          onClick: () => navigate('/courses?action=sync'),
        },
      ];
    }

    if (user.role === 'student') {
      return [
        {
          label: 'Study Guide',
          icon: IconStudyGuide,
          onClick: () => navigate('/courses?action=study-guide'),
        },
        {
          label: 'Add Task',
          icon: IconTask,
          onClick: () => setShowFabTaskModal(true),
        },
        {
          label: 'Flashcards',
          icon: IconFlashcards,
          onClick: () => navigate('/course-materials?tab=flashcards'),
        },
        {
          label: 'Send Message',
          icon: IconMessage,
          onClick: () => navigate('/messages?compose=true'),
        },
      ];
    }

    if (user.role === 'teacher') {
      return [
        {
          label: 'Upload Material',
          icon: IconUpload,
          onClick: () => navigate('/course-materials?action=upload'),
        },
        {
          label: 'Send Message',
          icon: IconMessage,
          onClick: () => navigate('/messages?compose=true'),
        },
        {
          label: 'Add Task',
          icon: IconTask,
          onClick: () => setShowFabTaskModal(true),
        },
        {
          label: 'Broadcast',
          icon: IconBroadcast,
          onClick: () => navigate('/dashboard?action=broadcast'),
        },
      ];
    }

    return [];
  }, [user, navigate]);

  const handleNavClick = useCallback((path: string) => {
    navigate(path);
    setMenuOpen(false);
  }, [navigate]);

  const handleActionClick = useCallback((action: SidebarAction) => {
    action.onClick();
    setMenuOpen(false);
  }, []);

  const handleSwitchRole = useCallback(async (role: string) => {
    try {
      await switchRole(role);
      setRoleSwitcherOpen(false);
      navigate('/dashboard');
    } catch {
      // Silently fail
    }
  }, [switchRole, navigate]);

  const handleResendVerification = useCallback(async () => {
    setResendStatus('sending');
    try {
      await resendVerification();
      setResendStatus('sent');
    } catch {
      setResendStatus('idle');
    }
  }, [resendVerification]);

  const showVerifyBanner = user && !user.email_verified && !verifyBannerDismissed;

  return (
    <>
      {/* Skip to content link for keyboard users */}
      <a href="#main-content" className="skip-to-content">
        Skip to main content
      </a>

      <div className="dashboard">
        <header className="dashboard-header">
        <div className="header-left">
          <button
            className={`hamburger-btn${menuOpen ? ' open' : ''}`}
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle navigation"
          >
            <span />
            <span />
            <span />
          </button>
          <img src="/classbridge-logo-v6.png" alt="ClassBridge" className="header-logo" onClick={() => navigate('/dashboard')} style={{ cursor: 'pointer' }} />
        </div>
        <GlobalSearch />
        <div className="header-right">
          <LanguageToggle />
          <ThemeToggle />
          <NotificationBell />
          <div className="user-chip" ref={roleSwitcherRef}>
            <span className="user-name">{user?.full_name}</span>
            {userXP && (
              <button
                className="header-xp-badge"
                onClick={() => navigate('/achievements')}
                title={`Level ${userXP.level} — ${userXP.total_xp} XP`}
                aria-label={`Your level: ${userXP.level}`}
              >
                Lvl {userXP.level}
              </button>
            )}
            {hasMultipleRoles ? (
              <>
                <button
                  className="user-role role-switcher-trigger"
                  onClick={() => setRoleSwitcherOpen(!roleSwitcherOpen)}
                >
                  {user?.role} &#9662;
                </button>
                {roleSwitcherOpen && (
                  <div className="role-switcher-dropdown">
                    {user?.roles
                      .filter(r => r !== user?.role)
                      .map(r => (
                        <button
                          key={r}
                          className="role-switcher-option"
                          onClick={() => handleSwitchRole(r)}
                        >
                          Switch to {r}
                        </button>
                      ))}
                  </div>
                )}
              </>
            ) : (
              <span className="user-role">{user?.role}</span>
            )}
          </div>
          <button onClick={logout} className="logout-button">
            Sign Out
          </button>
        </div>
      </header>

      {showVerifyBanner && (
        <div className="verify-email-banner">
          <span>Please verify your email address. Check your inbox for a verification link.</span>
          {resendStatus === 'idle' && (
            <button className="verify-email-banner__resend" onClick={handleResendVerification}>
              Resend email
            </button>
          )}
          {resendStatus === 'sending' && <span className="verify-email-banner__status">Sending...</span>}
          {resendStatus === 'sent' && <span className="verify-email-banner__status">Sent! Check your inbox.</span>}
          <button className="verify-email-banner__dismiss" onClick={() => setVerifyBannerDismissed(true)} aria-label="Dismiss">
            &times;
          </button>
        </div>
      )}

      {/* Slide-out menu overlay (mobile only, <768px) */}
      {menuOpen && <div className="menu-overlay" onClick={() => setMenuOpen(false)} />}

      <div className={`slide-menu${menuOpen ? ' open' : ''}`}>
        <div className="sidebar-title">Navigation</div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <button
              key={item.path}
              className={`sidebar-link${location.pathname === item.path ? ' active' : ''}`}
              onClick={() => handleNavClick(item.path)}
            >
              <span className="sidebar-link-icon"><NavIcon name={item.label} /></span>
              <span className="sidebar-link-label">{item.label}</span>
              {item.path === '/messages' && unreadCount > 0 && (
                <span className="sidebar-badge">{unreadCount}</span>
              )}
            </button>
          ))}
        </nav>
        {sidebarActions && sidebarActions.length > 0 && (
          <>
            <div className="sidebar-divider" />
            <div className="sidebar-title">Quick Actions</div>
            <div className="sidebar-nav">
              {sidebarActions.map((action, i) => (
                <button
                  key={i}
                  className="sidebar-action"
                  onClick={() => handleActionClick(action)}
                >
                  <span className="sidebar-action-icon icon-with-plus">{QUICK_ACTION_SVG[action.label] || <NavIcon name={action.label} />}</span>
                  <span className="sidebar-action-label">{action.label}</span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="dashboard-body">
        {/* Persistent sidebar (>=768px) */}
        <aside className="persistent-sidebar" aria-label="Main navigation">
          <nav className="persistent-sidebar-nav">
            {navItems.map((item) => (
              <button
                key={item.path}
                className={`ps-nav-item${location.pathname === item.path ? ' active' : ''}`}
                onClick={() => navigate(item.path)}
                title={item.label}
                aria-label={item.label}
              >
                <span className="ps-nav-icon"><NavIcon name={item.label} /></span>
                <span className="ps-nav-label">{item.label}</span>
                {item.path === '/messages' && unreadCount > 0 && (
                  <span className="ps-nav-badge">{unreadCount}</span>
                )}
              </button>
            ))}
          </nav>

          {persistentQuickActions.length > 0 && (
            <>
              <div className="ps-divider" />
              <button
                className={`ps-fab-toggle${quickActionsOpen ? ' open' : ''}`}
                onClick={() => setQuickActionsOpen(p => !p)}
                title="Quick Actions"
                aria-label="Quick Actions"
              >
                <span className="ps-fab-icon">
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
                    <path d="M9 3v12M3 9h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                </span>
              </button>
              {quickActionsOpen && (
                <div className="persistent-sidebar-actions">
                  {persistentQuickActions.map((action, i) => (
                    <button
                      key={i}
                      className="ps-action-item"
                      onClick={action.onClick}
                      title={action.label}
                      aria-label={action.label}
                    >
                      <span className="ps-action-icon icon-with-plus">{QUICK_ACTION_SVG[action.label] || <NavIcon name={action.label} />}</span>
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </aside>

        <main id="main-content" className="dashboard-main-full" tabIndex={-1}>
        {headerSlot ? (
          headerSlot(inspiration ? { text: inspiration.text, author: inspiration.author } : null)
        ) : (
          <div className="welcome-section">
            {inspiration && (
              <div className="welcome-inspiration">
                <h2 className="inspiration-text">"{inspiration.text}"</h2>
                {inspiration.author && (
                  <p className="inspiration-author">— {inspiration.author}</p>
                )}
              </div>
            )}
            <div className={`welcome-fallback${inspiration ? ' has-inspiration' : ''}`}>
              <h2>Welcome back, {user?.full_name?.split(' ')[0]}!</h2>
              <p>{welcomeSubtitle || "Here's your overview"}</p>
            </div>
          </div>
        )}

        {children}
      </main>
      </div>{/* end dashboard-body */}

      <footer className="dashboard-footer">
        <Link to="/privacy">Privacy Policy</Link>
        <span className="dashboard-footer-divider">|</span>
        <Link to="/terms">Terms of Service</Link>
        <span className="dashboard-footer-divider">|</span>
        <a href="mailto:support@classbridge.ca">Contact Us</a>
      </footer>

      <KeyboardShortcutsModal open={showShortcuts} onClose={() => setShowShortcuts(false)} />

      {user?.role === 'parent' && (
        <OnboardingTour steps={PARENT_TOUR_STEPS} storageKey="tour_completed_parent" />
      )}
      {user?.role === 'student' && (
        <OnboardingTour steps={STUDENT_TOUR_STEPS} storageKey="tour_completed_student" />
      )}
      {user?.role === 'teacher' && (
        <OnboardingTour steps={TEACHER_TOUR_STEPS} storageKey="tour_completed_teacher" />
      )}

      {/* Quick Action FAB (#837) — fixed floating speed-dial, hidden on admin/auth pages */}
      {showFAB && fabActions.length > 0 && (
        <QuickActionFAB actions={fabActions} />
      )}

      {/* CreateTaskModal triggered from the FAB (#837) */}
      <CreateTaskModal
        open={showFabTaskModal}
        onClose={() => setShowFabTaskModal(false)}
      />

      {/* Offline status indicator — fixed bottom bar */}
      <OfflineIndicator />
      </div>
    </>
  );
}
