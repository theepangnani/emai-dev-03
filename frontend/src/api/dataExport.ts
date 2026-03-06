import { api } from './client';

export interface DataExportRequest {
  id: number;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'expired';
  created_at: string;
  completed_at: string | null;
  expires_at: string | null;
  download_url: string | null;
}

export const dataExportApi = {
  /** Request a new data export */
  async requestExport(): Promise<DataExportRequest> {
    const { data } = await api.post<DataExportRequest>('/api/users/me/export');
    return data;
  },

  /** List recent export requests */
  async listExports(): Promise<DataExportRequest[]> {
    const { data } = await api.get<DataExportRequest[]>('/api/users/me/exports');
    return data;
  },

  /** Download a completed export */
  async downloadExport(token: string): Promise<void> {
    const response = await api.get(`/api/users/me/exports/${token}/download`, {
      responseType: 'blob',
    });
    const blob = new Blob([response.data], { type: 'application/zip' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'classbridge_data_export.zip';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },
};
