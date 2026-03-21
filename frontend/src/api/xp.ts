import { api } from './client';

export interface XpBadge {
  id: string;
  name: string;
  description: string;
  icon: string;
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

export interface XpStreakResponse {
  current_streak: number;
  longest_streak: number;
  streak_start_date: string | null;
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

  getChildSummary: async (studentId: number) => {
    const response = await api.get<XpSummary>(`/api/xp/children/${studentId}/summary`);
    return response.data;
  },
};
