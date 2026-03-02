/**
 * Gamification API client — XP, badges, leaderboard.
 */
import { apiClient } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type BadgeCategory = 'study' | 'quiz' | 'streak' | 'social' | 'milestone' | 'special';

export interface BadgeDefinition {
  id: number;
  key: string;
  name: string;
  description: string;
  icon_emoji: string;
  category: BadgeCategory;
  xp_reward: number;
  criteria_json: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
}

export interface UserBadge {
  id: number;
  user_id: number;
  badge_id: number;
  earned_at: string;
  notified: boolean;
  badge: BadgeDefinition;
}

export interface UserXP {
  id: number;
  user_id: number;
  total_xp: number;
  level: number;
  xp_this_week: number;
  leaderboard_opt_in: boolean;
  updated_at: string | null;
  xp_for_next_level: number;
  xp_progress: number;
}

export interface XPTransaction {
  id: number;
  user_id: number;
  amount: number;
  reason: string;
  created_at: string;
}

export interface LeaderboardEntry {
  rank: number;
  display_name: string;
  level: number;
  total_xp: number;
  badge_count: number;
}

export interface LeaderboardResponse {
  entries: LeaderboardEntry[];
  total: number;
}

export interface NewBadgeNotification {
  badge: BadgeDefinition;
  xp_awarded: number;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/** Fetch all active badge definitions (for badge showcase grid). */
export async function getAllBadges(): Promise<BadgeDefinition[]> {
  const res = await apiClient.get<BadgeDefinition[]>('/api/badges/');
  return res.data;
}

/** Fetch badges the current user has earned. */
export async function getMyBadges(): Promise<UserBadge[]> {
  const res = await apiClient.get<UserBadge[]>('/api/badges/mine');
  return res.data;
}

/** Fetch unread badge notifications (and mark them as notified). */
export async function getNewBadgeNotifications(): Promise<NewBadgeNotification[]> {
  const res = await apiClient.get<NewBadgeNotification[]>('/api/badges/new');
  return res.data;
}

/** Parent/teacher: fetch badges for a specific student. */
export async function getStudentBadges(studentUserId: number): Promise<UserBadge[]> {
  const res = await apiClient.get<UserBadge[]>(`/api/badges/student/${studentUserId}`);
  return res.data;
}

/** Fetch current user's XP and level. */
export async function getMyXP(): Promise<UserXP> {
  const res = await apiClient.get<UserXP>('/api/xp/');
  return res.data;
}

/** Fetch XP transaction history. */
export async function getXPHistory(limit = 50): Promise<XPTransaction[]> {
  const res = await apiClient.get<XPTransaction[]>('/api/xp/history', { params: { limit } });
  return res.data;
}

/** Toggle leaderboard opt-in. */
export async function setLeaderboardOptIn(optIn: boolean): Promise<UserXP> {
  const res = await apiClient.patch<UserXP>('/api/xp/leaderboard-opt-in', { opt_in: optIn });
  return res.data;
}

/** Fetch leaderboard (top users). */
export async function getLeaderboard(limit = 20): Promise<LeaderboardResponse> {
  const res = await apiClient.get<LeaderboardResponse>('/api/leaderboard', { params: { limit } });
  return res.data;
}
