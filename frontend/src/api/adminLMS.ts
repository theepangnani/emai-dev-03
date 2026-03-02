/**
 * Admin LMS Management API client (#27, #28).
 *
 * Covers all endpoints under /api/admin/lms/*:
 *   GET    /api/admin/lms/institutions
 *   POST   /api/admin/lms/institutions
 *   PATCH  /api/admin/lms/institutions/{id}
 *   DELETE /api/admin/lms/institutions/{id}
 *   GET    /api/admin/lms/institutions/{id}/connections
 *   GET    /api/admin/lms/stats
 *   POST   /api/admin/lms/sync/trigger
 */

import { api } from './client';
import type { LMSInstitution } from './lmsConnections';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type { LMSInstitution };

export interface AdminConnection {
  id: number;
  user_id: number;
  user_email: string | null;
  user_name: string | null;
  institution_id: number | null;
  provider: string;
  label: string | null;
  status: string;
  last_sync_at: string | null;
  sync_error: string | null;
  courses_synced: number;
  created_at: string;
  updated_at: string | null;
}

export interface ProviderStatusCounts {
  [status: string]: number;
}

export interface InstitutionStat {
  institution_id: number;
  name: string;
  active_connections: number;
}

export interface LMSStats {
  total_connections: number;
  by_provider: Record<string, ProviderStatusCounts>;
  by_institution: InstitutionStat[];
  last_sync_summary: {
    synced_last_hour: number;
    errors_last_hour: number;
  };
}

export interface SyncTriggerResult {
  synced: number;
  errors: number;
  message: string;
}

export interface InstitutionCreatePayload {
  name: string;
  provider: string;
  base_url?: string;
  region?: string;
  is_active?: boolean;
  metadata_json?: string;
}

export interface InstitutionUpdatePayload {
  name?: string;
  provider?: string;
  base_url?: string;
  region?: string;
  is_active?: boolean;
  metadata_json?: string;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export const adminLMSApi = {
  /** List all institutions (including inactive when include_inactive=true). */
  listInstitutions: async (opts?: {
    provider?: string;
    include_inactive?: boolean;
  }): Promise<LMSInstitution[]> => {
    const params: Record<string, string | boolean> = {};
    if (opts?.provider) params.provider = opts.provider;
    if (opts?.include_inactive) params.include_inactive = true;
    const response = await api.get('/api/admin/lms/institutions', { params });
    return response.data as LMSInstitution[];
  },

  /** Create a new institution (admin only). */
  createInstitution: async (data: InstitutionCreatePayload): Promise<LMSInstitution> => {
    const response = await api.post('/api/admin/lms/institutions', data);
    return response.data as LMSInstitution;
  },

  /** Partially update an institution (admin only). */
  updateInstitution: async (
    id: number,
    data: InstitutionUpdatePayload,
  ): Promise<LMSInstitution> => {
    const response = await api.patch(`/api/admin/lms/institutions/${id}`, data);
    return response.data as LMSInstitution;
  },

  /** Soft-delete (deactivate) an institution (admin only). */
  deactivateInstitution: async (id: number): Promise<void> => {
    await api.delete(`/api/admin/lms/institutions/${id}`);
  },

  /** List all user connections for a specific institution (admin only). */
  listInstitutionConnections: async (institutionId: number): Promise<AdminConnection[]> => {
    const response = await api.get(
      `/api/admin/lms/institutions/${institutionId}/connections`,
    );
    return response.data as AdminConnection[];
  },

  /** Get aggregated LMS stats (admin only). */
  getStats: async (): Promise<LMSStats> => {
    const response = await api.get('/api/admin/lms/stats');
    return response.data as LMSStats;
  },

  /** Manually trigger a full LMS sync (admin only). */
  triggerFullSync: async (): Promise<SyncTriggerResult> => {
    const response = await api.post('/api/admin/lms/sync/trigger');
    return response.data as SyncTriggerResult;
  },
};
