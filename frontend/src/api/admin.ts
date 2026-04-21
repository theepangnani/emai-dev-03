import { api } from './client';

// Feature Flag Types
// Legacy CB-DEMO-001 scheme: 'on_50' | 'on_for_all' (#3601)
// CB-LAND-001 percentage-ramp scheme: 'on_5' | 'on_25' | 'on_100' (#3802)
export type FeatureVariantValue =
  | 'off'
  | 'on_50'
  | 'on_for_all'
  | 'on_5'
  | 'on_25'
  | 'on_100';

export interface FeatureFlagItem {
  key: string;
  name: string;
  description: string | null;
  enabled: boolean;
  variant: FeatureVariantValue | null;  // null for config-based flags (#3601)
  updated_at: string | null;
}

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
  // New v2 fields:
  total_materials: number;
  new_registrations_today: number;
  ai_generations_last_hour: number;
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
    // New format returns array of objects; convert to flat dict for backward compat
    const data = response.data;
    if (Array.isArray(data)) {
      const result: Record<string, boolean> = {};
      for (const f of data) result[f.key] = f.enabled;
      return result;
    }
    return data as Record<string, boolean>;
  },

  getFeatures: async () => {
    const response = await api.get('/api/admin/features');
    return response.data as FeatureFlagItem[];
  },

  updateFeatureToggle: async (key: string, enabled: boolean) => {
    const response = await api.patch(`/api/admin/features/${key}`, { enabled });
    return response.data as { feature: string; enabled: boolean; variant: FeatureVariantValue | null };
  },

  // Update A/B variant for a DB-backed feature flag (#3601)
  updateFeatureVariant: async (key: string, variant: FeatureVariantValue) => {
    const response = await api.patch(`/api/admin/features/${key}`, { variant });
    return response.data as { feature: string; enabled: boolean; variant: FeatureVariantValue | null };
  },

  // Storage limits (#1007)
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

  // Demo Sessions (CB-DEMO-001 FE5 — #3611)
  listDemoSessions: async (params?: {
    page?: number;
    per_page?: number;
    status?: string;
    verified?: boolean;
    search?: string;
  }) => {
    const response = await api.get('/api/admin/demo-sessions', { params });
    return response.data as DemoSessionListResponse;
  },

  approveDemoSession: async (id: string) => {
    const response = await api.post(`/api/admin/demo-sessions/${id}/approve`);
    return response.data as DemoSessionItem;
  },

  rejectDemoSession: async (id: string) => {
    const response = await api.post(`/api/admin/demo-sessions/${id}/reject`);
    return response.data as DemoSessionItem;
  },

  blocklistDemoSession: async (id: string) => {
    const response = await api.post(`/api/admin/demo-sessions/${id}/blocklist`);
    return response.data as DemoSessionItem;
  },

  downloadDemoSessionsCsv: async () => {
    const response = await api.get('/api/admin/demo-sessions/export.csv', {
      responseType: 'blob',
    });
    return response.data as Blob;
  },
};

// Demo Session Types (CB-DEMO-001 FE5 — #3611)
export interface DemoMoatSummary {
  tm_beats_seen: number;
  rs_roles_switched: number;
  pw_viewport_reached: boolean;
}

export interface DemoSessionItem {
  id: string;
  created_at: string;
  email: string | null;
  full_name: string | null;
  role: string | null;
  verified: boolean;
  verified_ts: string | null;
  generations_count: number;
  admin_status: string | null;
  source_ip_hash: string | null;
  user_agent: string | null;
  archived_at: string | null;
  moat_engagement_json: Record<string, unknown> | null;
  moat_summary: DemoMoatSummary;
}

export interface DemoSessionStatusCounts {
  pending: number;
  approved: number;
  rejected: number;
  blocklisted: number;
}

export interface DemoSessionListResponse {
  items: DemoSessionItem[];
  total: number;
  page: number;
  per_page: number;
  counts: DemoSessionStatusCounts;
}

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
