import { api, AI_TIMEOUT } from './client';

export type PreviewCourse = {
  class_name: string;
  section: string | null;
  teacher_name: string;
  teacher_email: string | null;
  google_classroom_id: string | null;
  existing: boolean;
  existing_course_id: number | null;
};

export type PreviewConnected = {
  connected: true;
  courses: PreviewCourse[];
  error?: string;
};

export type PreviewDisconnected = {
  connected: false;
  connect_url: string;
  courses: [];
  error?: string;
};

export type PreviewResponse = PreviewConnected | PreviewDisconnected;

export type ParsedRow = {
  class_name: string;
  section: string | null;
  teacher_name: string;
  teacher_email: string | null;
};

export type ParseScreenshotResponse = {
  parsed: ParsedRow[];
};

export type BulkCreateRow = {
  class_name: string;
  section: string | null;
  teacher_name: string;
  teacher_email: string | null;
  google_classroom_id: string | null;
};

export type BulkCreatedItem = {
  index: number;
  course_id: number;
  name: string;
};

export type BulkFailedItem = {
  index: number;
  error: string;
  existing_course_id?: number;
};

export type BulkCreateResponse = {
  created: BulkCreatedItem[];
  failed: BulkFailedItem[];
};

export async function fetchGoogleClassroomPreview(): Promise<PreviewResponse> {
  const { data } = await api.get<PreviewResponse>('/api/courses/google-classroom/preview');
  return data;
}

export async function parseScreenshot(file: File): Promise<ParseScreenshotResponse> {
  const form = new FormData();
  form.append('image', file);
  const { data } = await api.post<ParseScreenshotResponse>(
    '/api/courses/parse-screenshot',
    form,
    {
      ...AI_TIMEOUT,
      headers: { 'Content-Type': 'multipart/form-data' },
    },
  );
  return data;
}

export async function bulkCreateClasses(rows: BulkCreateRow[]): Promise<BulkCreateResponse> {
  const { data } = await api.post<BulkCreateResponse>('/api/courses/bulk', { rows });
  return data;
}
