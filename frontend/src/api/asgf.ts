import { api, AI_TIMEOUT } from './client';

export interface IntentClassifyResponse {
  subject: string;
  grade_level: string;
  topic: string;
  confidence: number;
  bloom_tier: string;
}

export interface FileUploadResponse {
  file_id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  text_preview: string;
}

export interface MultiFileUploadResponse {
  files: FileUploadResponse[];
  total_size_bytes: number;
}

export interface AssignmentOption {
  key: string;
  label: string;
  description: string;
}

export interface CourseSuggestion {
  course_id: string | null;
  course_name: string | null;
  confidence: number;
}

export interface AssignmentOptionsResponse {
  role: string;
  options: AssignmentOption[];
  suggested_course: CourseSuggestion | null;
}

export interface AssignRequest {
  assignment_type: string;
  course_id?: string | null;
  due_date?: string | null;
}

export interface AssignResponse {
  success: boolean;
  message: string;
}

export interface ComprehensionSignalRequest {
  slide_number: number;
  signal: 'got_it' | 'still_confused';
}

export interface ComprehensionSignalResponse {
  acknowledged: boolean;
  re_explanation_slide: Record<string, unknown> | null;
}

export interface CreateSessionResponse {
  session_id: string;
  topic: string;
  subject: string;
  grade_level: string;
  slide_count: number;
  quiz_count: number;
  estimated_time_min: number;
}

export interface ASGFQuizQuestion {
  question_text: string;
  options: string[];
  correct_index: number;
  bloom_tier: string;
  slide_reference: number;
  hint_text: string;
  explanation: string;
}

export interface ASGFQuizResponse {
  session_id: string;
  questions: ASGFQuizQuestion[];
}

export interface ResumeSessionResponse {
  session_id: string;
  current_slide_index: number;
  signals_given: Array<{ slide_number: number; signal: string }>;
  quiz_progress: Array<Record<string, unknown>>;
  slides: Array<Record<string, unknown>>;
  created_at: string;
  expires_at: string;
}

export interface ActiveSessionItem {
  session_id: string;
  question: string;
  subject: string;
  created_at: string;
  slide_count: number;
}

export interface ActiveSessionsResponse {
  sessions: ActiveSessionItem[];
}

export const asgfApi = {
  classifyIntent: async (question: string): Promise<IntentClassifyResponse> => {
    const response = await api.post<IntentClassifyResponse>('/api/asgf/classify-intent', { question });
    return response.data;
  },

  /** Upload multiple documents for an ASGF study session. */
  uploadDocuments(
    files: File[],
    onUploadProgress?: (progressEvent: { loaded: number; total?: number }) => void,
  ): Promise<MultiFileUploadResponse> {
    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));
    return api
      .post<MultiFileUploadResponse>('/api/asgf/upload', formData, {
        ...AI_TIMEOUT,
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress,
      })
      .then((r) => r.data);
  },

  /** Create a new ASGF session with context assembly + plan generation. */
  async createSession(body: {
    question: string;
    file_ids?: string[];
    child_id?: string;
    subject?: string;
    grade?: string;
    course_id?: string;
  }): Promise<CreateSessionResponse> {
    const response = await api.post<CreateSessionResponse>('/api/asgf/session', body, AI_TIMEOUT);
    return response.data;
  },

  /** Stream slide generation via SSE. Returns an EventSource-compatible URL. */
  generateSlidesUrl(sessionId: string): string {
    const baseUrl = api.defaults.baseURL || '';
    return `${baseUrl}/api/asgf/generate-slides?session_id=${encodeURIComponent(sessionId)}`;
  },

  /** Fetch role-aware assignment options and course suggestion for a session. */
  async getAssignmentOptions(sessionId: string): Promise<AssignmentOptionsResponse> {
    const response = await api.get<AssignmentOptionsResponse>(
      `/api/asgf/session/${sessionId}/assignment-options`,
    );
    return response.data;
  },

  /** Assign session material with the chosen option. */
  async assignMaterial(
    sessionId: string,
    body: AssignRequest,
  ): Promise<AssignResponse> {
    const response = await api.post<AssignResponse>(
      `/api/asgf/session/${sessionId}/assign`,
      body,
    );
    return response.data;
  },

  /** Record a per-slide comprehension signal (got_it / still_confused). */
  async sendComprehensionSignal(
    sessionId: string,
    body: ComprehensionSignalRequest,
  ): Promise<ComprehensionSignalResponse> {
    const response = await api.post<ComprehensionSignalResponse>(
      `/api/asgf/session/${sessionId}/signal`,
      body,
      AI_TIMEOUT,
    );
    return response.data;
  },

  /** Generate slide-anchored quiz questions for a completed session. */
  async generateQuiz(sessionId: string): Promise<ASGFQuizResponse> {
    const response = await api.post<ASGFQuizResponse>(
      `/api/asgf/session/${sessionId}/quiz`,
      {},
      AI_TIMEOUT,
    );
    return response.data;
  },

  /** Get session state for resumption (within 24h). */
  async resumeSession(sessionId: string): Promise<ResumeSessionResponse> {
    const response = await api.get<ResumeSessionResponse>(
      `/api/asgf/session/${sessionId}/resume`,
    );
    return response.data;
  },

  /** Get list of active (resumable) ASGF sessions for the current user. */
  async getActiveSessions(): Promise<ActiveSessionsResponse> {
    const response = await api.get<ActiveSessionsResponse>(
      '/api/asgf/active-sessions',
    );
    return response.data;
  },
};
