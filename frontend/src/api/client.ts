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

// Study Tools API
export interface StudyGuide {
  id: number;
  user_id: number;
  assignment_id: number | null;
  course_id: number | null;
  title: string;
  content: string;
  guide_type: string;
  created_at: string;
}

export interface QuizQuestion {
  question: string;
  options: { A: string; B: string; C: string; D: string };
  correct_answer: string;
  explanation: string;
}

export interface Quiz {
  id: number;
  title: string;
  questions: QuizQuestion[];
  guide_type: string;
  created_at: string;
}

export interface Flashcard {
  front: string;
  back: string;
}

export interface FlashcardSet {
  id: number;
  title: string;
  cards: Flashcard[];
  guide_type: string;
  created_at: string;
}

export interface SupportedFormats {
  documents: string[];
  spreadsheets: string[];
  presentations: string[];
  images: string[];
  archives: string[];
  max_file_size_mb: number;
  ocr_available: boolean;
}

export interface ExtractedText {
  filename: string;
  text: string;
  character_count: number;
  word_count: number;
}

export const studyApi = {
  generateGuide: async (params: { assignment_id?: number; course_id?: number; title?: string; content?: string }) => {
    const response = await api.post('/api/study/generate', params);
    return response.data as StudyGuide;
  },

  generateQuiz: async (params: { assignment_id?: number; course_id?: number; topic?: string; content?: string; num_questions?: number }) => {
    const response = await api.post('/api/study/quiz/generate', params);
    return response.data as Quiz;
  },

  generateFlashcards: async (params: { assignment_id?: number; course_id?: number; topic?: string; content?: string; num_cards?: number }) => {
    const response = await api.post('/api/study/flashcards/generate', params);
    return response.data as FlashcardSet;
  },

  listGuides: async (guideType?: string) => {
    const params = guideType ? { guide_type: guideType } : {};
    const response = await api.get('/api/study/guides', { params });
    return response.data as StudyGuide[];
  },

  getGuide: async (id: number) => {
    const response = await api.get(`/api/study/guides/${id}`);
    return response.data as StudyGuide;
  },

  deleteGuide: async (id: number) => {
    await api.delete(`/api/study/guides/${id}`);
  },

  // File Upload Methods
  getSupportedFormats: async () => {
    const response = await api.get('/api/study/upload/formats');
    return response.data as SupportedFormats;
  },

  generateFromFile: async (params: {
    file: File;
    title?: string;
    guide_type: 'study_guide' | 'quiz' | 'flashcards';
    num_questions?: number;
    num_cards?: number;
  }) => {
    const formData = new FormData();
    formData.append('file', params.file);
    if (params.title) formData.append('title', params.title);
    formData.append('guide_type', params.guide_type);
    if (params.num_questions) formData.append('num_questions', params.num_questions.toString());
    if (params.num_cards) formData.append('num_cards', params.num_cards.toString());

    const response = await api.post('/api/study/upload/generate', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data as StudyGuide;
  },

  extractTextFromFile: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post('/api/study/upload/extract-text', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data as ExtractedText;
  },
};
