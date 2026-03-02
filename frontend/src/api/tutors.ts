import { api } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface TutorProfile {
  id: number;
  user_id: number;
  tutor_name: string | null;
  bio: string;
  headline: string;
  subjects: string[];
  grade_levels: string[];
  languages: string[];
  hourly_rate_cad: number;
  session_duration_minutes: number;
  available_days: string[];
  available_hours_start: string;
  available_hours_end: string;
  timezone: string;
  online_only: boolean;
  location_city: string | null;
  is_verified: boolean;
  years_experience: number | null;
  certifications: string[];
  school_affiliation: string | null;
  total_sessions: number;
  avg_rating: number | null;
  review_count: number;
  is_active: boolean;
  is_accepting_students: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface TutorBooking {
  id: number;
  tutor_id: number;
  student_id: number;
  requested_by_user_id: number;
  subject: string;
  message: string | null;
  proposed_date: string | null;
  duration_minutes: number;
  status: 'pending' | 'accepted' | 'declined' | 'completed' | 'cancelled';
  tutor_response: string | null;
  responded_at: string | null;
  rating: number | null;
  review_text: string | null;
  reviewed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  // Denormalized
  tutor_name: string | null;
  student_name: string | null;
  requester_name: string | null;
}

export interface TutorSearchParams {
  subject?: string;
  grade_level?: string;
  max_rate?: number;
  online_only?: boolean;
  min_rating?: number;
  language?: string;
  verified?: boolean;
  skip?: number;
  limit?: number;
}

export interface TutorProfileCreatePayload {
  bio: string;
  headline: string;
  subjects: string[];
  grade_levels: string[];
  languages?: string[];
  hourly_rate_cad: number;
  session_duration_minutes?: number;
  available_days?: string[];
  available_hours_start?: string;
  available_hours_end?: string;
  timezone?: string;
  online_only?: boolean;
  location_city?: string | null;
  years_experience?: number | null;
  certifications?: string[] | null;
  school_affiliation?: string | null;
  is_accepting_students?: boolean;
}

export type TutorProfileUpdatePayload = Partial<TutorProfileCreatePayload> & {
  is_active?: boolean;
};

export interface BookingCreatePayload {
  subject: string;
  message?: string;
  proposed_date?: string | null;
  duration_minutes?: number;
  student_id?: number | null;
}

export interface BookingRespondPayload {
  status: 'accepted' | 'declined';
  tutor_response?: string;
}

export interface BookingReviewPayload {
  rating: number;
  review_text?: string;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export const tutorsApi = {
  /** Search / list active tutor profiles */
  search(params: TutorSearchParams = {}): Promise<TutorProfile[]> {
    const query = new URLSearchParams();
    if (params.subject) query.set('subject', params.subject);
    if (params.grade_level) query.set('grade_level', params.grade_level);
    if (params.max_rate !== undefined) query.set('max_rate', String(params.max_rate));
    if (params.online_only !== undefined) query.set('online_only', String(params.online_only));
    if (params.min_rating !== undefined) query.set('min_rating', String(params.min_rating));
    if (params.language) query.set('language', params.language);
    if (params.verified !== undefined) query.set('verified', String(params.verified));
    if (params.skip !== undefined) query.set('skip', String(params.skip));
    if (params.limit !== undefined) query.set('limit', String(params.limit));
    return api.get<TutorProfile[]>(`/api/tutors/?${query.toString()}`).then((r) => r.data);
  },

  /** Get a tutor profile by ID */
  getById(id: number): Promise<TutorProfile> {
    return api.get<TutorProfile>(`/api/tutors/${id}`).then((r) => r.data);
  },

  /** Get the current teacher's tutor profile */
  getMyProfile(): Promise<TutorProfile> {
    return api.get<TutorProfile>('/api/tutors/profile/me').then((r) => r.data);
  },

  /** Create a tutor profile (teachers only) */
  createProfile(payload: TutorProfileCreatePayload): Promise<TutorProfile> {
    return api.post<TutorProfile>('/api/tutors/profile', payload).then((r) => r.data);
  },

  /** Update my tutor profile */
  updateProfile(payload: TutorProfileUpdatePayload): Promise<TutorProfile> {
    return api.patch<TutorProfile>('/api/tutors/profile', payload).then((r) => r.data);
  },

  /** Get bookings for a specific tutor (teacher-only) */
  getTutorBookings(
    tutorId: number,
    params: { status?: string; skip?: number; limit?: number } = {},
  ): Promise<TutorBooking[]> {
    const query = new URLSearchParams();
    if (params.status) query.set('status', params.status);
    if (params.skip !== undefined) query.set('skip', String(params.skip));
    if (params.limit !== undefined) query.set('limit', String(params.limit));
    return api
      .get<TutorBooking[]>(`/api/tutors/${tutorId}/bookings?${query.toString()}`)
      .then((r) => r.data);
  },

  /** Request a booking with a tutor */
  bookTutor(tutorId: number, payload: BookingCreatePayload): Promise<TutorBooking> {
    return api.post<TutorBooking>(`/api/tutors/${tutorId}/book`, payload).then((r) => r.data);
  },

  /** Get booking requests made by me (parent/student) */
  getMyBookings(params: { status?: string; skip?: number; limit?: number } = {}): Promise<TutorBooking[]> {
    const query = new URLSearchParams();
    if (params.status) query.set('status', params.status);
    if (params.skip !== undefined) query.set('skip', String(params.skip));
    if (params.limit !== undefined) query.set('limit', String(params.limit));
    return api.get<TutorBooking[]>(`/api/tutors/bookings/mine?${query.toString()}`).then((r) => r.data);
  },

  /** Accept or decline a booking (teacher) */
  respondToBooking(bookingId: number, payload: BookingRespondPayload): Promise<TutorBooking> {
    return api
      .patch<TutorBooking>(`/api/tutors/bookings/${bookingId}/respond`, payload)
      .then((r) => r.data);
  },

  /** Leave a rating/review after a completed session */
  reviewBooking(bookingId: number, payload: BookingReviewPayload): Promise<TutorBooking> {
    return api
      .patch<TutorBooking>(`/api/tutors/bookings/${bookingId}/review`, payload)
      .then((r) => r.data);
  },

  /** Verify a tutor profile (admin only) */
  verifyTutor(tutorId: number): Promise<TutorProfile> {
    return api.patch<TutorProfile>(`/api/tutors/${tutorId}/verify`).then((r) => r.data);
  },
};
