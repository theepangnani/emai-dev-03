import { api } from './client';

// Notification Types
export interface NotificationResponse {
  id: number;
  user_id: number;
  type:
    | 'assignment_due'
    | 'grade_posted'
    | 'message'
    | 'system'
    | 'task_due'
    | 'link_request'
    | 'material_uploaded'
    | 'study_guide_created'
    | 'parent_request'
    | 'assessment_upcoming'
    | 'project_due';
  title: string;
  content: string | null;
  link: string | null;
  read: boolean;
  created_at: string;

  // ACK system fields
  requires_ack: boolean;
  acked_at: string | null;
  source_type: string | null;
  source_id: number | null;
  reminder_count: number;
}

export interface NotificationPreferences {
  email_notifications: boolean;
  assignment_reminder_days: string;
  task_reminder_days: string;
}

export interface ChannelPreference {
  in_app: boolean;
  email: boolean;
}

export interface AdvancedNotificationPreferences {
  assignments: ChannelPreference;
  messages: ChannelPreference;
  study_guides: ChannelPreference;
  tasks: ChannelPreference;
  system: ChannelPreference;
  parent_email_digest: ChannelPreference;
}

export interface NotificationSuppressionResponse {
  id: number;
  user_id: number;
  source_type: string;
  source_id: number;
  suppressed_at: string;
}

// Notifications API
export const notificationsApi = {
  list: async (skip = 0, limit = 20, unreadOnly = false) => {
    const response = await api.get('/api/notifications/', { params: { skip, limit, unread_only: unreadOnly } });
    return response.data as NotificationResponse[];
  },

  getUnreadCount: async () => {
    const response = await api.get('/api/notifications/unread-count');
    return response.data as { count: number };
  },

  markAsRead: async (id: number) => {
    const response = await api.put(`/api/notifications/${id}/read`);
    return response.data as NotificationResponse;
  },

  markAllAsRead: async () => {
    await api.put('/api/notifications/read-all');
  },

  delete: async (id: number) => {
    await api.delete(`/api/notifications/${id}`);
  },

  ack: async (id: number) => {
    const response = await api.put(`/api/notifications/${id}/ack`);
    return response.data as NotificationResponse;
  },

  suppress: async (id: number) => {
    const response = await api.put(`/api/notifications/${id}/suppress`);
    return response.data as NotificationResponse;
  },

  getSettings: async () => {
    const response = await api.get('/api/notifications/settings');
    return response.data as NotificationPreferences;
  },

  updateSettings: async (settings: NotificationPreferences) => {
    const response = await api.put('/api/notifications/settings', settings);
    return response.data as NotificationPreferences;
  },

  listSuppressions: async () => {
    const response = await api.get('/api/notifications/suppressions');
    return response.data as NotificationSuppressionResponse[];
  },

  deleteSuppression: async (suppressionId: number) => {
    await api.delete(`/api/notifications/suppressions/${suppressionId}`);
  },

  getAdvancedPreferences: async () => {
    const response = await api.get('/api/notifications/preferences');
    return response.data as AdvancedNotificationPreferences;
  },

  updateAdvancedPreferences: async (update: Partial<AdvancedNotificationPreferences>) => {
    const response = await api.patch('/api/notifications/preferences', update);
    return response.data as AdvancedNotificationPreferences;
  },
};
