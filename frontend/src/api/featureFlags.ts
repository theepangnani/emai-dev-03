import { api } from './client';

// ─── Types ───────────────────────────────────────────────────────────────────

export type FlagScope = 'global' | 'tier' | 'role' | 'user' | 'beta';

export interface FeatureFlagResponse {
  id: number;
  key: string;
  name: string;
  description: string | null;
  scope: FlagScope;
  is_enabled: boolean;
  enabled_tiers: string[];
  enabled_roles: string[];
  enabled_user_ids: number[];
  rollout_percentage: number;
  metadata_json: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
  created_by_user_id: number | null;
}

export interface FeatureFlagCreate {
  key: string;
  name: string;
  description?: string;
  scope?: FlagScope;
  is_enabled?: boolean;
  enabled_tiers?: string[];
  enabled_roles?: string[];
  enabled_user_ids?: number[];
  rollout_percentage?: number;
  metadata_json?: Record<string, unknown>;
}

export interface OverrideCreate {
  user_id: number;
  flag_key: string;
  is_enabled: boolean;
  reason?: string;
  expires_at?: string | null;
}

export interface OverrideResponse {
  id: number;
  user_id: number;
  flag_key: string;
  is_enabled: boolean;
  reason: string | null;
  expires_at: string | null;
  created_by_user_id: number | null;
  created_at: string | null;
}

export interface OverrideListResponse {
  items: OverrideResponse[];
  total: number;
}

// ─── API client ───────────────────────────────────────────────────────────────

export const featureFlagsApi = {
  /** Get all feature flags evaluated for the current user. */
  getAll: async (): Promise<Record<string, boolean>> => {
    const response = await api.get('/api/feature-flags');
    return response.data as Record<string, boolean>;
  },

  /** Get a single flag evaluation for the current user. */
  get: async (key: string): Promise<{ key: string; enabled: boolean }> => {
    const response = await api.get(`/api/feature-flags/${key}`);
    return response.data as { key: string; enabled: boolean };
  },

  // ─── Admin endpoints ───────────────────────────────────────────────────────

  /** List all flags with full configuration (admin only). */
  adminList: async (): Promise<FeatureFlagResponse[]> => {
    const response = await api.get('/api/admin/feature-flags');
    return response.data as FeatureFlagResponse[];
  },

  /** Create a new feature flag (admin only). */
  create: async (data: FeatureFlagCreate): Promise<FeatureFlagResponse> => {
    const response = await api.post('/api/admin/feature-flags', data);
    return response.data as FeatureFlagResponse;
  },

  /** Update an existing flag (admin only). */
  update: async (key: string, data: Partial<FeatureFlagCreate>): Promise<FeatureFlagResponse> => {
    const response = await api.put(`/api/admin/feature-flags/${key}`, data);
    return response.data as FeatureFlagResponse;
  },

  /** Delete a feature flag and all its overrides (admin only). */
  delete: async (key: string): Promise<void> => {
    await api.delete(`/api/admin/feature-flags/${key}`);
  },

  /** List user overrides with optional filters (admin only). */
  listOverrides: async (params?: {
    user_id?: number;
    flag_key?: string;
    skip?: number;
    limit?: number;
  }): Promise<OverrideListResponse> => {
    const response = await api.get('/api/admin/feature-flags/overrides', { params });
    return response.data as OverrideListResponse;
  },

  /** Create or update a per-user override (admin only). */
  createOverride: async (data: OverrideCreate): Promise<OverrideResponse> => {
    const response = await api.post('/api/admin/feature-flags/overrides', data);
    return response.data as OverrideResponse;
  },

  /** Remove a user override by ID (admin only). */
  deleteOverride: async (id: number): Promise<void> => {
    await api.delete(`/api/admin/feature-flags/overrides/${id}`);
  },

  /** Seed predefined flags (idempotent, admin only). */
  seed: async (): Promise<{ message: string }> => {
    const response = await api.post('/api/admin/feature-flags/seed');
    return response.data as { message: string };
  },
};
