import { api } from './client';

export type CSVTemplateType = 'students' | 'courses' | 'assignments';

export interface CSVImportResult {
  imported: number;
  errors: string[];
}

export const csvImportApi = {
  downloadTemplate: async (type: CSVTemplateType): Promise<Blob> => {
    const resp = await api.get(`/api/import/templates/${type}`, { responseType: 'blob' });
    return resp.data;
  },

  uploadCSV: async (type: CSVTemplateType, file: File): Promise<CSVImportResult> => {
    const formData = new FormData();
    formData.append('template_type', type);
    formData.append('file', file);
    const resp = await api.post('/api/import/csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return resp.data;
  },
};
