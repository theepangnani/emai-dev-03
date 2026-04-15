import { api, AI_TIMEOUT } from './client';

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
