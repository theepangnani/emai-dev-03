/**
 * Typed API client for API key management (#905).
 *
 * Endpoints:
 *   POST   /api/auth/api-keys           — create (returns full key once)
 *   GET    /api/auth/api-keys           — list
 *   DELETE /api/auth/api-keys/{id}      — revoke
 */
import { apiClient } from './client';

export interface APIKeyListItem {
  id: number;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
  is_active: boolean;
}

export interface APIKeyCreatedResponse {
  id: number;
  name: string;
  /** Full plaintext key — shown ONCE. Never stored by the client. */
  key: string;
  prefix: string;
  created_at: string;
  expires_at: string | null;
}

export interface CreateAPIKeyPayload {
  name: string;
  expires_days?: number | null;
}

export const apiKeysApi = {
  list(): Promise<APIKeyListItem[]> {
    return apiClient.get<APIKeyListItem[]>('/api/auth/api-keys').then((r) => r.data);
  },

  create(payload: CreateAPIKeyPayload): Promise<APIKeyCreatedResponse> {
    return apiClient
      .post<APIKeyCreatedResponse>('/api/auth/api-keys', payload)
      .then((r) => r.data);
  },

  revoke(id: number): Promise<void> {
    return apiClient.delete(`/api/auth/api-keys/${id}`).then(() => undefined);
  },
};
