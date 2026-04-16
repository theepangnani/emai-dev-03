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
};
