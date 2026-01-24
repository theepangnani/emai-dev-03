import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  login: async (email: string, password: string) => {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await api.post('/api/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return response.data;
  },

  register: async (data: { email: string; password: string; full_name: string; role: string }) => {
    const response = await api.post('/api/auth/register', data);
    return response.data;
  },

  getMe: async () => {
    const response = await api.get('/api/users/me');
    return response.data;
  },
};

// Courses API
export const coursesApi = {
  list: async () => {
    const response = await api.get('/api/courses/');
    return response.data;
  },

  get: async (id: number) => {
    const response = await api.get(`/api/courses/${id}`);
    return response.data;
  },
};

// Assignments API
export const assignmentsApi = {
  list: async (courseId?: number) => {
    const params = courseId ? { course_id: courseId } : {};
    const response = await api.get('/api/assignments/', { params });
    return response.data;
  },

  get: async (id: number) => {
    const response = await api.get(`/api/assignments/${id}`);
    return response.data;
  },
};

// Google Classroom API
export const googleApi = {
  getAuthUrl: async () => {
    const response = await api.get('/api/google/auth');
    return response.data;
  },

  getConnectUrl: async () => {
    const response = await api.get('/api/google/connect');
    return response.data;
  },

  getStatus: async () => {
    const response = await api.get('/api/google/status');
    return response.data;
  },

  disconnect: async () => {
    const response = await api.delete('/api/google/disconnect');
    return response.data;
  },

  getCourses: async () => {
    const response = await api.get('/api/google/courses');
    return response.data;
  },

  syncCourses: async () => {
    const response = await api.post('/api/google/courses/sync');
    return response.data;
  },

  getAssignments: async (courseId: string) => {
    const response = await api.get(`/api/google/courses/${courseId}/assignments`);
    return response.data;
  },

  syncAssignments: async (courseId: string) => {
    const response = await api.post(`/api/google/courses/${courseId}/assignments/sync`);
    return response.data;
  },
};
