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
};
