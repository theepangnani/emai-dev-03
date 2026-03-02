import { api } from './client';
import type { SubmissionResponse } from './courses';

export type { SubmissionResponse };

export const submissionsApi = {
  /**
   * Submit an assignment (multipart form: text? + file?).
   */
  submit: async (assignmentId: number, data: { text?: string; file?: File }): Promise<SubmissionResponse> => {
    const formData = new FormData();
    if (data.file) {
      formData.append('file', data.file);
    }
    if (data.text) {
      formData.append('notes', data.text);
    }
    const response = await api.post(`/api/assignments/${assignmentId}/submit`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  /**
   * Get the current student's submission for an assignment (404 if none).
   */
  getSubmission: async (assignmentId: number): Promise<SubmissionResponse> => {
    const response = await api.get(`/api/assignments/${assignmentId}/submission`);
    return response.data;
  },

  /**
   * List all submissions for a student (for parent/teacher view).
   */
  getStudentSubmissions: async (
    studentId: number,
    params?: { status?: string; limit?: number; offset?: number }
  ): Promise<SubmissionResponse[]> => {
    const response = await api.get(`/api/students/${studentId}/submissions`, { params });
    return response.data;
  },

  /**
   * Retract a submission (only if not yet returned/graded).
   */
  unsubmit: async (assignmentId: number): Promise<{ detail: string }> => {
    const response = await api.delete(`/api/assignments/${assignmentId}/submission`);
    return response.data;
  },
};
