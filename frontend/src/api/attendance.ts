import apiClient from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type AttendanceStatus = 'present' | 'absent' | 'late' | 'excused';

export interface AttendanceRecord {
  id: number;
  student_id: number;
  course_id: number;
  teacher_id: number | null;
  date: string; // ISO date string YYYY-MM-DD
  status: AttendanceStatus;
  note: string | null;
  notified_parent: boolean;
  created_at: string;
  updated_at: string | null;
  student_name: string | null;
  course_name: string | null;
}

export interface AttendanceSummary {
  student_id: number;
  student_name: string;
  course_id: number | null;
  course_name: string | null;
  present_count: number;
  absent_count: number;
  late_count: number;
  excused_count: number;
  total_days: number;
  attendance_pct: number;
}

export interface CourseAttendanceReport {
  course_id: number;
  course_name: string;
  start_date: string;
  end_date: string;
  student_summaries: AttendanceSummary[];
}

export interface BulkAttendanceEntry {
  student_id: number;
  status: AttendanceStatus;
  note?: string;
}

export interface BulkAttendancePayload {
  course_id: number;
  date: string;
  records: BulkAttendanceEntry[];
}

export interface BulkAttendanceResponse {
  created: number;
  updated: number;
  records: AttendanceRecord[];
}

export interface SingleAttendancePayload {
  student_id: number;
  course_id: number;
  date: string;
  status: AttendanceStatus;
  note?: string;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/** Mark attendance for a single student. */
export async function markAttendance(payload: SingleAttendancePayload): Promise<AttendanceRecord> {
  const { data } = await apiClient.post<AttendanceRecord>('/api/attendance/', payload);
  return data;
}

/** Bulk-mark attendance for a whole class. */
export async function bulkMarkAttendance(payload: BulkAttendancePayload): Promise<BulkAttendanceResponse> {
  const { data } = await apiClient.post<BulkAttendanceResponse>('/api/attendance/bulk', payload);
  return data;
}

/** Get all attendance records for a course on a given date. */
export async function getCourseAttendance(
  courseId: number,
  recordDate?: string,
): Promise<AttendanceRecord[]> {
  const params = recordDate ? { date: recordDate } : {};
  const { data } = await apiClient.get<AttendanceRecord[]>(`/api/attendance/course/${courseId}`, {
    params,
  });
  return data;
}

/** Get attendance summary for a student (teacher/admin). */
export async function getStudentSummary(
  studentId: number,
  opts?: { courseId?: number; startDate?: string; endDate?: string },
): Promise<AttendanceSummary> {
  const params: Record<string, string | number> = {};
  if (opts?.courseId) params.course_id = opts.courseId;
  if (opts?.startDate) params.start_date = opts.startDate;
  if (opts?.endDate) params.end_date = opts.endDate;
  const { data } = await apiClient.get<AttendanceSummary>(`/api/attendance/student/${studentId}/summary`, {
    params,
  });
  return data;
}

/** Get full course attendance report for a date range (teacher/admin). */
export async function getCourseReport(
  courseId: number,
  startDate: string,
  endDate: string,
): Promise<CourseAttendanceReport> {
  const { data } = await apiClient.get<CourseAttendanceReport>(
    `/api/attendance/course/${courseId}/report`,
    { params: { start: startDate, end: endDate } },
  );
  return data;
}

/** Student retrieves their own attendance summary. */
export async function getMyAttendanceSummary(opts?: {
  courseId?: number;
  startDate?: string;
  endDate?: string;
}): Promise<AttendanceSummary> {
  const params: Record<string, string | number> = {};
  if (opts?.courseId) params.course_id = opts.courseId;
  if (opts?.startDate) params.start_date = opts.startDate;
  if (opts?.endDate) params.end_date = opts.endDate;
  const { data } = await apiClient.get<AttendanceSummary>('/api/attendance/my-summary', { params });
  return data;
}

/** Parent retrieves attendance summary for a child. */
export async function getParentChildAttendance(studentId: number): Promise<AttendanceSummary> {
  const { data } = await apiClient.get<AttendanceSummary>(`/api/attendance/parent/${studentId}`);
  return data;
}
