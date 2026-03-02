/**
 * Admin Analytics API client.
 * Provides typed interfaces and fetch functions for all 4 analytics endpoints.
 */
import { api } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface OverviewStats {
  total_users: number;
  users_by_role: {
    parent: number;
    student: number;
    teacher: number;
    admin: number;
  };
  active_last_7d: number;
  active_last_30d: number;
  new_users_this_week: number;
  total_courses: number;
  total_study_guides: number;
  total_quiz_attempts: number;
  total_tasks: number;
  total_messages: number;
  google_connected_users: number;
  premium_users: number;
  generated_at: string;
}

export interface DailyRegistration {
  date: string;
  total: number;
  parent: number;
  student: number;
  teacher: number;
  admin: number;
}

export interface UserGrowthStats {
  period_days: number;
  daily_registrations: DailyRegistration[];
  total_period: number;
}

export interface TopCourseByMaterials {
  course_id: number;
  course_name: string;
  material_count: number;
}

export interface ContentStats {
  study_guides_last_7d: number;
  study_guides_last_30d: number;
  quizzes_generated: number;
  flashcard_sets: number;
  exam_prep_plans: number;
  mock_exams_created: number;
  documents_uploaded: number;
  top_courses_by_materials: TopCourseByMaterials[];
}

export interface StudyStreaks {
  avg_streak_days: number;
  users_with_streak_7plus: number;
  users_with_streak_30plus: number;
}

export interface EngagementStats {
  quiz_attempts_last_7d: number;
  avg_quiz_score: number;
  messages_last_7d: number;
  tasks_created_last_7d: number;
  tasks_completed_last_7d: number;
  study_streaks: StudyStreaks;
}

export interface MFIPPAConsents {
  under_16: number;
  '16_17': number;
  '18_plus': number;
}

export interface PrivacyStats {
  pending_deletion_requests: number;
  completed_deletions_30d: number;
  data_exports_30d: number;
  cookie_consent_given: number;
  cookie_consent_pending: number;
  mfippa_consents: MFIPPAConsents;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function fetchOverview(): Promise<OverviewStats> {
  const res = await api.get<OverviewStats>('/api/admin/analytics/overview');
  return res.data;
}

export async function fetchUserGrowth(): Promise<UserGrowthStats> {
  const res = await api.get<UserGrowthStats>('/api/admin/analytics/users');
  return res.data;
}

export async function fetchContentStats(): Promise<ContentStats> {
  const res = await api.get<ContentStats>('/api/admin/analytics/content');
  return res.data;
}

export async function fetchEngagementStats(): Promise<EngagementStats> {
  const res = await api.get<EngagementStats>('/api/admin/analytics/engagement');
  return res.data;
}

export async function fetchPrivacyStats(): Promise<PrivacyStats> {
  const res = await api.get<PrivacyStats>('/api/admin/analytics/privacy');
  return res.data;
}
