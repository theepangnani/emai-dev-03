import { api } from './client';

// Admin Types
export interface AdminUserItem {
  id: number;
  email: string | null;
  full_name: string;
  role: string;
  roles: string[];
  is_active: boolean;
  created_at: string;
}

export interface AdminUserList {
  users: AdminUserItem[];
  total: number;
}

export interface AdminStats {
  total_users: number;
  users_by_role: Record<string, number>;
  total_courses: number;
  total_assignments: number;
}

// Audit Log Types
export interface AuditLogItem {
  id: number;
  user_id: number | null;
  user_name: string | null;
  action: string;
  resource_type: string;
  resource_id: number | null;
  details: string | null;
  ip_address: string | null;
  created_at: string;
}

export interface AuditLogList {
  items: AuditLogItem[];
  total: number;
}

// Broadcast Types
export interface BroadcastResponse {
  id: number;
  subject: string;
  body: string;
  recipient_count: number;
  email_count: number;
  created_at: string;
}

export interface BroadcastItem {
  id: number;
  subject: string;
  recipient_count: number;
  email_count: number;
  created_at: string;
}

// Admin API
export const adminApi = {
  getStats: async () => {
    const response = await api.get('/api/admin/stats');
    return response.data as AdminStats;
  },

  getUsers: async (params?: { role?: string; search?: string; skip?: number; limit?: number }) => {
    const response = await api.get('/api/admin/users', { params });
    return response.data as AdminUserList;
  },

  getAuditLogs: async (params?: { user_id?: number; action?: string; resource_type?: string; date_from?: string; date_to?: string; search?: string; skip?: number; limit?: number }) => {
    const response = await api.get('/api/admin/audit-logs', { params });
    return response.data as AuditLogList;
  },

  addRole: async (userId: number, role: string) => {
    const response = await api.post(`/api/admin/users/${userId}/add-role`, { role });
    return response.data as AdminUserItem;
  },

  removeRole: async (userId: number, role: string) => {
    const response = await api.post(`/api/admin/users/${userId}/remove-role`, { role });
    return response.data as AdminUserItem;
  },

  sendBroadcast: async (subject: string, body: string) => {
    const response = await api.post('/api/admin/broadcast', { subject, body });
    return response.data as BroadcastResponse;
  },

  getBroadcasts: async (skip = 0, limit = 20) => {
    const response = await api.get('/api/admin/broadcasts', { params: { skip, limit } });
    return response.data as BroadcastItem[];
  },

  sendMessage: async (userId: number, subject: string, body: string) => {
    const response = await api.post(`/api/admin/users/${userId}/message`, { subject, body });
    return response.data as { success: boolean; email_sent: boolean };
  },

  getFeatureToggles: async () => {
    const response = await api.get('/api/admin/features');
    return response.data as Record<string, boolean>;
  },

  updateFeatureToggle: async (key: string, enabled: boolean) => {
    const response = await api.patch(`/api/admin/features/${key}`, { enabled });
    return response.data as { feature: string; enabled: boolean };
  },

  getUserStorage: async (userId: number) => {
    const response = await api.get(`/api/admin/users/${userId}/storage`);
    return response.data as UserStorageInfo;
  },

  updateUserStorageLimits: async (userId: number, limits: { storage_limit_bytes?: number; upload_limit_bytes?: number }) => {
    const response = await api.patch(`/api/admin/users/${userId}/storage-limits`, limits);
    return response.data as UserStorageInfo;
  },

  getStorageOverview: async () => {
    const response = await api.get('/api/admin/storage/overview');
    return response.data as StorageOverview;
  },
};

export interface UserStorageInfo {
  storage_used_bytes: number;
  storage_limit_bytes: number;
  upload_limit_bytes: number;
  storage_used_pct: number;
  warning: boolean;
  critical: boolean;
  user_id?: number;
  full_name?: string;
  email?: string;
}

export interface StorageOverview {
  total_storage_used_bytes: number;
  total_storage_limit_bytes: number;
  users_with_files: number;
  total_users: number;
  avg_usage_bytes: number;
}
