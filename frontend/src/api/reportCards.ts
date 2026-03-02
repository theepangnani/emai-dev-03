import { api } from './client';

// --- Types ---

export interface MarkItem {
  subject: string;
  mark: number;
  max_mark: number;
  percentage: number;
}

export interface ReportCardSummary {
  id: number;
  student_id: number;
  student_name: string | null;
  term: string;
  academic_year: string | null;
  file_name: string;
  file_size_bytes: number | null;
  overall_average: number | null;
  status: 'uploaded' | 'processing' | 'analyzed' | 'failed';
  uploaded_at: string;
  analyzed_at: string | null;
}

export interface ReportCardDetail extends ReportCardSummary {
  extracted_marks: MarkItem[] | null;
  ai_observations: string | null;
  ai_strengths: string[] | null;
  ai_improvement_areas: string[] | null;
  error_message: string | null;
}

export interface UploadReportCardParams {
  student_id: number;
  term: string;
  academic_year?: string;
  file: File;
}

export interface ListReportCardsParams {
  student_id?: number;
  academic_year?: string;
}

// --- API ---

export const reportCardsApi = {
  upload: async (params: UploadReportCardParams): Promise<ReportCardDetail> => {
    const formData = new FormData();
    formData.append('student_id', String(params.student_id));
    formData.append('term', params.term);
    if (params.academic_year) {
      formData.append('academic_year', params.academic_year);
    }
    formData.append('file', params.file);

    const resp = await api.post('/api/report-cards/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return resp.data as ReportCardDetail;
  },

  list: async (params?: ListReportCardsParams): Promise<ReportCardSummary[]> => {
    const queryParams: Record<string, unknown> = {};
    if (params?.student_id !== undefined) queryParams.student_id = params.student_id;
    if (params?.academic_year) queryParams.academic_year = params.academic_year;
    const resp = await api.get('/api/report-cards/', { params: queryParams });
    return resp.data as ReportCardSummary[];
  },

  get: async (id: number): Promise<ReportCardDetail> => {
    const resp = await api.get(`/api/report-cards/${id}`);
    return resp.data as ReportCardDetail;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/report-cards/${id}`);
  },
};
