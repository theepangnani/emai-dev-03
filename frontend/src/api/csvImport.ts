import { api } from './client';

export interface TemplateColumn {
  name: string;
  required: boolean;
  description: string;
}

export interface TemplateInfo {
  type: string;
  columns: TemplateColumn[];
}

export interface CsvPreviewResult {
  preview: true;
  template_type: string;
  rows: Record<string, string>[];
  errors: string[];
  total: number;
  valid: number;
}

export interface CsvImportResult {
  preview: false;
  template_type: string;
  created: number;
  skipped: number;
  errors: string[];
}

export type CsvUploadResult = CsvPreviewResult | CsvImportResult;

export const csvImportApi = {
  async listTemplates(): Promise<TemplateInfo[]> {
    const { data } = await api.get<TemplateInfo[]>('/api/import/templates');
    return data;
  },

  async downloadTemplate(templateType: string): Promise<void> {
    const { data } = await api.get<string>(`/api/import/templates/${templateType}`, {
      responseType: 'blob' as const,
    });
    const blob = new Blob([data as unknown as BlobPart], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${templateType}_template.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  },

  async uploadCsv(templateType: string, file: File, confirm: boolean = false): Promise<CsvUploadResult> {
    const formData = new FormData();
    formData.append('file', file);
    const { data } = await api.post<CsvUploadResult>(
      `/api/import/csv?template_type=${encodeURIComponent(templateType)}&confirm=${confirm}`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
    return data;
  },
};
