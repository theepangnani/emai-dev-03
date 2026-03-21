import { api } from './client';

export const bugReportsApi = {
  submit: async (data: { description?: string; screenshot?: File; pageUrl?: string; userAgent?: string; website?: string }) => {
    const formData = new FormData();
    if (data.description) formData.append('description', data.description);
    if (data.screenshot) formData.append('screenshot', data.screenshot);
    if (data.pageUrl) formData.append('page_url', data.pageUrl);
    if (data.userAgent) formData.append('user_agent', data.userAgent);
    if (data.website) formData.append('website', data.website);

    const response = await api.post('/api/bug-reports', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
};
