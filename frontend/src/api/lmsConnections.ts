/**
 * LMS Connections API client — Multi-LMS Provider Framework (#22, #23).
 *
 * Covers all endpoints under /api/lms/*:
 *   GET  /api/lms/providers
 *   GET  /api/lms/institutions
 *   POST /api/lms/institutions          (admin only)
 *   GET  /api/lms/connections
 *   POST /api/lms/connections
 *   PATCH /api/lms/connections/{id}
 *   DELETE /api/lms/connections/{id}
 *   GET  /api/lms/connections/{id}/status
 */

import { api } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface LMSProvider {
  provider_id: string;
  display_name: string;
  supports_oauth: boolean;
  requires_institution_url: boolean;
}

export interface LMSInstitution {
  id: number;
  name: string;
  provider: string;
  base_url: string | null;
  region: string | null;
  is_active: boolean;
  metadata_json: string | null;
  created_at: string;
}

export interface LMSConnection {
  id: number;
  user_id: number;
  institution_id: number | null;
  provider: string;
  label: string | null;
  status: 'connected' | 'expired' | 'error' | 'disconnected';
  last_sync_at: string | null;
  sync_error: string | null;
  courses_synced: number;
  external_user_id: string | null;
  created_at: string;
  updated_at: string | null;
  // Denormalized institution fields
  institution_name: string | null;
  institution_base_url: string | null;
}

export interface LMSConnectionStatus {
  id: number;
  provider: string;
  status: 'connected' | 'expired' | 'error' | 'disconnected';
  last_sync_at: string | null;
  sync_error: string | null;
  courses_synced: number;
}

export interface InstitutionCreate {
  name: string;
  provider: string;
  base_url?: string;
  region?: string;
  is_active?: boolean;
  metadata_json?: string;
}

export interface ConnectionCreate {
  provider: string;
  institution_id?: number | null;
  label?: string | null;
}

export interface ConnectionUpdate {
  label?: string | null;
  status?: 'connected' | 'expired' | 'error' | 'disconnected';
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export const lmsConnectionsApi = {
  /** List all registered LMS providers. */
  listProviders: async (): Promise<LMSProvider[]> => {
    const response = await api.get('/api/lms/providers');
    return response.data as LMSProvider[];
  },

  /** List all institutions, optionally filtered by provider. */
  listInstitutions: async (provider?: string): Promise<LMSInstitution[]> => {
    const params = provider ? { provider } : undefined;
    const response = await api.get('/api/lms/institutions', { params });
    return response.data as LMSInstitution[];
  },

  /** Create a new institution (admin only). */
  createInstitution: async (data: InstitutionCreate): Promise<LMSInstitution> => {
    const response = await api.post('/api/lms/institutions', data);
    return response.data as LMSInstitution;
  },

  /** List the current user's LMS connections. */
  listConnections: async (): Promise<LMSConnection[]> => {
    const response = await api.get('/api/lms/connections');
    return response.data as LMSConnection[];
  },

  /** Register a new LMS connection. */
  createConnection: async (data: ConnectionCreate): Promise<LMSConnection> => {
    const response = await api.post('/api/lms/connections', data);
    return response.data as LMSConnection;
  },

  /** Update a connection's label or status. */
  updateConnection: async (connectionId: number, data: ConnectionUpdate): Promise<LMSConnection> => {
    const response = await api.patch(`/api/lms/connections/${connectionId}`, data);
    return response.data as LMSConnection;
  },

  /** Delete an LMS connection. */
  deleteConnection: async (connectionId: number): Promise<void> => {
    await api.delete(`/api/lms/connections/${connectionId}`);
  },

  /** Get sync status for a specific connection. */
  getConnectionStatus: async (connectionId: number): Promise<LMSConnectionStatus> => {
    const response = await api.get(`/api/lms/connections/${connectionId}/status`);
    return response.data as LMSConnectionStatus;
  },
};
