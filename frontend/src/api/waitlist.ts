import { api } from './client';

export const waitlistApi = {
  join: async (data: { name: string; email: string; roles: string[] }) => {
    const response = await api.post('/api/waitlist', data);
    return response.data;
  },

  verifyToken: async (token: string) => {
    const response = await api.get(`/api/waitlist/verify/${token}`);
    return response.data;
  },
};
