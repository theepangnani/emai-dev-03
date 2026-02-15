import { api } from './client';
import type { User } from '../types/user';

export const authApi = {
  login: async (email: string, password: string) => {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await api.post('/api/auth/login', formData.toString(), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return response.data as {
      access_token: string;
      token_type: string;
      refresh_token?: string;
    };
  },

  getMe: async () => {
    const response = await api.get('/api/users/me');
    return response.data as User;
  },

  logout: async () => {
    const response = await api.post('/api/auth/logout');
    return response.data;
  },
};
