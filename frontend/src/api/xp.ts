import { api } from './client';

export interface XpBadge {
  id: string;
  name: string;
  description: string;
  icon: string;
  earned: boolean;
  earned_at: string | null;
}

export interface XpSummary {
  total_xp: number;
  level: number;
  level_title: string;
  xp_in_level: number;
  xp_for_next_level: number;
  today_xp: number;
  today_max_xp: number;
  streak_days: number;
  weekly_xp: number;
  recent_badges: XpBadge[];
}

export interface XpHistoryItem {
  id: number;
  xp: number;
  reason: string;
  created_at: string;
}

export interface XpHistoryResponse {
  items: XpHistoryItem[];
  total: number;
}

export interface XpLedgerEntry {
  action_type: string;
  xp_awarded: number;
  multiplier: number;
  reason: string | null;
  created_at: string;
}

export interface XpLedgerResponse {
  entries: XpLedgerEntry[];
  total_count: number;
}

export interface BadgeResponse {
  badge_id: string;
  badge_name: string;
  badge_description: string;
  earned: boolean;
  awarded_at: string | null;
}

export interface XpStreakResponse {
  current_streak: number;
  longest_streak: number;
  streak_start_date: string | null;
}

export interface BrowniePointResponse {
  awarded: number;
  student_user_id: number;
  new_total_xp: number;
  remaining_weekly_cap: number;
  message: string;
}

export interface BrownieRemaining {
  remaining: number;
  weekly_cap: number;
}

export const xpApi = {
  getSummary: async () => {
    const response = await api.get<XpSummary>('/api/xp/summary');
    return response.data;
  },

  getHistory: async (limit = 50, offset = 0) => {
    const response = await api.get<XpHistoryResponse>(`/api/xp/history?limit=${limit}&offset=${offset}`);
    return response.data;
  },

  getLedger: async (limit = 50, offset = 0) => {
    const response = await api.get<XpLedgerResponse>(`/api/xp/history?limit=${limit}&offset=${offset}`);
    return response.data;
  },

  getBadges: async () => {
    const response = await api.get<XpBadge[]>('/api/xp/badges');
    return response.data;
  },

  getStreak: async () => {
    const response = await api.get<XpStreakResponse>('/api/xp/streak');
    return response.data;
  },

  getChildStreak: async (studentId: number) => {
    const response = await api.get<{ current_streak: number; longest_streak: number; freeze_tokens_remaining: number; streak_tier: string; multiplier: number; tier_label: string; last_streak_date: string | null }>(`/api/students/${studentId}/streak`);
    return response.data;
  },

  getChildSummary: async (studentId: number) => {
    const response = await api.get<XpSummary>(`/api/xp/children/${studentId}/summary`);
    return response.data;
  },

  awardBrowniePoints: async (studentUserId: number, points: number, reason?: string) => {
    const response = await api.post<BrowniePointResponse>('/api/xp/award', {
      student_user_id: studentUserId,
      points,
      reason: reason || undefined,
    });
    return response.data;
  },

  getBrownieRemaining: async (studentUserId: number) => {
    const response = await api.get<BrownieRemaining>(`/api/xp/award/remaining?student_user_id=${studentUserId}`);
    return response.data;
  },
};
