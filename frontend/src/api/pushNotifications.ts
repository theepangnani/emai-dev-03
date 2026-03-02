import { api } from './client';

export type DevicePlatform = 'web' | 'ios' | 'android';

export interface PushTokenResponse {
  id: number;
  user_id: number;
  token: string;
  platform: DevicePlatform;
  device_name: string | null;
  app_version: string | null;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string | null;
}

export interface RegisterTokenRequest {
  token: string;
  platform: DevicePlatform;
  device_name?: string;
  app_version?: string;
}

export interface AdminSendRequest {
  user_ids: number[];
  title: string;
  body: string;
  data?: Record<string, string>;
}

export interface AdminSendResponse {
  sent: number;
  failed: number;
  users_reached?: number;
  skipped?: boolean;
  reason?: string;
}

export interface AdminPushStatsResponse {
  total_tokens: number;
  active_tokens: number;
  by_platform: Record<string, number>;
  unique_users_with_tokens: number;
}

export const pushApi = {
  /**
   * Register (or update) an FCM device token for the current user.
   */
  register: (data: RegisterTokenRequest) =>
    api.post<PushTokenResponse>('/api/push/register', data),

  /**
   * Deactivate (unregister) a device token.
   */
  unregister: (token: string) =>
    api.delete('/api/push/unregister', { data: { token } }),

  /**
   * List all active push tokens for the current user.
   */
  getTokens: () => api.get<PushTokenResponse[]>('/api/push/tokens'),

  // Admin endpoints
  admin: {
    /**
     * Admin: send a push notification to specific users.
     */
    send: (data: AdminSendRequest) =>
      api.post<AdminSendResponse>('/api/admin/push/send', data),

    /**
     * Admin: retrieve push token statistics.
     */
    stats: () => api.get<AdminPushStatsResponse>('/api/admin/push/stats'),
  },
};
