/**
 * Typed API client for the meeting scheduler feature.
 *
 * All datetime strings are UTC ISO-8601.
 */
import apiClient from './client';

// ---------------------------------------------------------------------------
// Enums / types
// ---------------------------------------------------------------------------

export type MeetingStatus = 'pending' | 'confirmed' | 'cancelled' | 'completed';
export type MeetingType = 'in_person' | 'video_call' | 'phone';

export interface TeacherAvailability {
  id: number;
  teacher_id: number;
  weekday: number; // 0=Mon … 6=Sun
  start_time: string; // "HH:MM:SS"
  end_time: string;
  slot_duration_minutes: number;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export interface AvailabilityCreate {
  weekday: number;
  start_time: string; // "HH:MM:SS"
  end_time: string;
  slot_duration_minutes?: number;
  is_active?: boolean;
}

export interface AvailableSlot {
  slot_start: string; // ISO-8601 UTC
  slot_end: string;
  duration_minutes: number;
}

export interface AvailableSlotsResponse {
  teacher_id: number;
  slots: AvailableSlot[];
}

export interface MeetingBooking {
  id: number;
  teacher_id: number;
  parent_id: number;
  student_id?: number;
  proposed_at: string;
  duration_minutes: number;
  meeting_type: MeetingType;
  status: MeetingStatus;
  topic: string;
  notes?: string;
  video_link?: string;
  teacher_notes?: string;
  confirmed_at?: string;
  cancelled_at?: string;
  cancellation_reason?: string;
  completed_at?: string;
  created_at: string;
  updated_at?: string;
  teacher_name?: string;
  parent_name?: string;
  student_name?: string;
}

export interface MeetingBookingCreate {
  teacher_id: number;
  student_id?: number;
  proposed_at: string; // ISO-8601 UTC
  duration_minutes?: number;
  meeting_type?: MeetingType;
  topic: string;
  notes?: string;
}

export interface ConfirmMeetingPayload {
  video_link?: string;
}

export interface CancelMeetingPayload {
  reason?: string;
}

export interface CompleteMeetingPayload {
  teacher_notes?: string;
}

export interface TeacherScheduleResponse {
  week_of: string; // "YYYY-MM-DD"
  bookings: MeetingBooking[];
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

const BASE = '/api/meetings';

/** Teacher: get current availability windows */
export async function getMyAvailability(): Promise<TeacherAvailability[]> {
  const res = await apiClient.get<TeacherAvailability[]>(`${BASE}/availability`);
  return res.data;
}

/** Teacher: replace availability windows */
export async function setMyAvailability(
  slots: AvailabilityCreate[],
): Promise<TeacherAvailability[]> {
  const res = await apiClient.put<TeacherAvailability[]>(`${BASE}/availability`, slots);
  return res.data;
}

/** Any user: get available booking slots for a teacher */
export async function getAvailableSlots(
  teacherId: number,
  dateFrom: Date,
  dateTo: Date,
): Promise<AvailableSlotsResponse> {
  const res = await apiClient.get<AvailableSlotsResponse>(`${BASE}/slots/${teacherId}`, {
    params: {
      date_from: dateFrom.toISOString(),
      date_to: dateTo.toISOString(),
    },
  });
  return res.data;
}

/** Parent: book a meeting */
export async function bookMeeting(payload: MeetingBookingCreate): Promise<MeetingBooking> {
  const res = await apiClient.post<MeetingBooking>(`${BASE}/book`, payload);
  return res.data;
}

/** Parent or teacher: list own meetings */
export async function listMyMeetings(): Promise<MeetingBooking[]> {
  const res = await apiClient.get<MeetingBooking[]>(`${BASE}/`);
  return res.data;
}

/** Teacher: confirm a meeting */
export async function confirmMeeting(
  bookingId: number,
  payload: ConfirmMeetingPayload,
): Promise<MeetingBooking> {
  const res = await apiClient.patch<MeetingBooking>(`${BASE}/${bookingId}/confirm`, payload);
  return res.data;
}

/** Teacher or parent: cancel a meeting */
export async function cancelMeeting(
  bookingId: number,
  payload: CancelMeetingPayload,
): Promise<MeetingBooking> {
  const res = await apiClient.patch<MeetingBooking>(`${BASE}/${bookingId}/cancel`, payload);
  return res.data;
}

/** Teacher: mark meeting completed */
export async function completeMeeting(
  bookingId: number,
  payload: CompleteMeetingPayload,
): Promise<MeetingBooking> {
  const res = await apiClient.patch<MeetingBooking>(`${BASE}/${bookingId}/complete`, payload);
  return res.data;
}

/** Teacher: get week schedule */
export async function getTeacherSchedule(weekOf: Date): Promise<TeacherScheduleResponse> {
  const res = await apiClient.get<TeacherScheduleResponse>(`${BASE}/schedule`, {
    params: { week_of: weekOf.toISOString() },
  });
  return res.data;
}
