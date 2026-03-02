/**
 * Two-Factor Authentication (TOTP) API client.
 *
 * All calls require the user to be authenticated (Bearer token sent by the
 * Axios interceptor in client.ts).  The sole exception is `login2FA`, which
 * accepts the short-lived temp_token returned by the normal login endpoint
 * when 2FA is required.
 */
import { api } from './client';

export interface TwoFAStatus {
  is_enabled: boolean;
  has_device: boolean;
}

export interface TwoFASetupResponse {
  secret: string;
  qr_code_url: string;
  backup_codes: string[];
}

export interface TwoFALoginResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  onboarding_completed?: boolean;
}

export interface BackupCodesResponse {
  backup_codes: string[];
  used_count: number;
  total: number;
}

export interface RegenerateBackupCodesResponse {
  detail: string;
  backup_codes: string[];
}

/** Check whether 2FA is enabled for the current user. */
export async function get2FAStatus(): Promise<TwoFAStatus> {
  const { data } = await api.get<TwoFAStatus>('/api/2fa/status');
  return data;
}

/** Initiate 2FA setup — returns secret, QR code, and backup codes. */
export async function setup2FA(): Promise<TwoFASetupResponse> {
  const { data } = await api.post<TwoFASetupResponse>('/api/2fa/setup');
  return data;
}

/** Verify a TOTP code and activate 2FA. */
export async function enable2FA(code: string): Promise<{ detail: string }> {
  const { data } = await api.post<{ detail: string }>('/api/2fa/enable', { code });
  return data;
}

/**
 * Verify a TOTP (or backup) code and deactivate 2FA.
 *
 * A valid code is required to prevent accidental / unauthorised disabling.
 */
export async function disable2FA(code: string): Promise<{ detail: string }> {
  const { data } = await api.post<{ detail: string }>('/api/2fa/disable', { code });
  return data;
}

/** Standalone TOTP / backup-code verification (not part of the login flow). */
export async function verify2FA(
  code: string,
): Promise<{ detail: string; backup_code_used: boolean }> {
  const { data } = await api.post<{ detail: string; backup_code_used: boolean }>(
    '/api/2fa/verify',
    { code },
  );
  return data;
}

/** Return masked backup codes for the current user. */
export async function getBackupCodes(): Promise<BackupCodesResponse> {
  const { data } = await api.get<BackupCodesResponse>('/api/2fa/backup-codes');
  return data;
}

/**
 * Regenerate backup codes (requires a valid TOTP code to authorise).
 *
 * Old codes are invalidated immediately.
 */
export async function regenerateBackupCodes(
  code: string,
): Promise<RegenerateBackupCodesResponse> {
  const { data } = await api.post<RegenerateBackupCodesResponse>(
    '/api/2fa/backup-codes/regenerate',
    { code },
  );
  return data;
}

/**
 * Complete the 2FA login flow.
 *
 * Called after POST /api/auth/login returns `{ requires_2fa: true, temp_token }`.
 * Accepts the temp token and the user's TOTP code (or backup code) and returns
 * a full JWT pair on success.
 */
export async function login2FA(
  tempToken: string,
  code: string,
): Promise<TwoFALoginResponse> {
  const { data } = await api.post<TwoFALoginResponse>('/api/auth/login/2fa', {
    temp_token: tempToken,
    code,
  });
  return data;
}
