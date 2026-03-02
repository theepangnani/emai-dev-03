/**
 * Profile API — BYOK AI key management (#578), subscription info (#1007),
 * account deletion (#964), and data export (#965).
 */
import { api } from './client';

export interface AIKeyStatus {
  has_key: boolean;
  /** Masked preview, e.g. "sk-...abcd", or null if no key is set. */
  key_preview: string | null;
}

export interface DeleteAccountRequest {
  password: string;
}

export interface DeleteAccountResponse {
  message: string;
  scheduled_for: string;
}

export interface CancelDeletionResponse {
  message: string;
}

export const profileApi = {
  /** Check whether the current user has a stored AI API key. */
  getAIKeyStatus: async (): Promise<AIKeyStatus> => {
    const response = await api.get('/api/profile/ai-key');
    return response.data as AIKeyStatus;
  },

  /** Encrypt and save the user's personal AI API key. */
  setAIKey: async (apiKey: string): Promise<void> => {
    await api.put('/api/profile/ai-key', { api_key: apiKey });
  },

  /** Remove the stored AI API key so the platform key is used instead. */
  deleteAIKey: async (): Promise<void> => {
    await api.delete('/api/profile/ai-key');
  },

  /**
   * Request permanent account deletion.
   * Requires current password for confirmation.
   * Returns the date the account will be permanently deleted (30 days from now).
   */
  requestDeletion: async (password: string): Promise<DeleteAccountResponse> => {
    const response = await api.post<DeleteAccountResponse>('/api/auth/account/delete-request', {
      password,
    });
    return response.data;
  },

  /**
   * Cancel a pending account deletion request.
   */
  cancelDeletion: async (): Promise<CancelDeletionResponse> => {
    const response = await api.delete<CancelDeletionResponse>('/api/auth/account/delete-request');
    return response.data;
  },

  /**
   * Export all user data as a JSON file.
   * Rate-limited to 1 export per hour.
   * Returns a Blob suitable for client-side download via URL.createObjectURL().
   */
  requestExport: async (): Promise<Blob> => {
    const response = await api.post('/api/auth/account/export', null, {
      responseType: 'blob',
      timeout: 60000, // Allow up to 60s for large exports
    });
    return response.data as Blob;
  },
};
