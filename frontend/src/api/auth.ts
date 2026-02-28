import { api } from './client';

// Auth API
export const authApi = {
  login: async (identifier: string, password: string) => {
    const formData = new URLSearchParams();
    formData.append('username', identifier);
    formData.append('password', password);

    const response = await api.post('/api/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return response.data;
  },

  register: async (data: { email?: string; username?: string; parent_email?: string; password: string; full_name: string; roles?: string[]; teacher_type?: string; google_id?: string }) => {
    const response = await api.post('/api/auth/register', { roles: [], ...data });
    return response.data;
  },

  getMe: async () => {
    const response = await api.get('/api/users/me');
    return response.data;
  },

  switchRole: async (role: string) => {
    const response = await api.post('/api/users/me/switch-role', { role });
    return response.data;
  },

  acceptInvite: async (token: string, password: string, full_name: string) => {
    const response = await api.post('/api/auth/accept-invite', { token, password, full_name });
    return response.data as { access_token: string; token_type: string; refresh_token?: string };
  },

  forgotPassword: async (email: string) => {
    const response = await api.post('/api/auth/forgot-password', { email });
    return response.data as { message: string };
  },

  logout: async () => {
    const response = await api.post('/api/auth/logout');
    return response.data;
  },

  resetPassword: async (token: string, new_password: string) => {
    const response = await api.post('/api/auth/reset-password', { token, new_password }, { timeout: 15000 });
    return response.data as { message: string };
  },

  completeOnboarding: async (roles: string[], teacherType?: string) => {
    const response = await api.post('/api/auth/onboarding', {
      roles,
      ...(teacherType ? { teacher_type: teacherType } : {}),
    });
    return response.data;
  },

  getOnboardingStatus: async () => {
    const response = await api.get('/api/auth/onboarding-status');
    return response.data as { onboarding_completed: boolean; needs_onboarding: boolean };
  },

  verifyEmail: async (token: string) => {
    const response = await api.post('/api/auth/verify-email', { token });
    return response.data as { message: string };
  },

  resendVerification: async () => {
    const response = await api.post('/api/auth/resend-verification');
    return response.data as { message: string };
  },
};
