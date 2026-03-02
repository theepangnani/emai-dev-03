import { useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import { tutorsApi, type TutorProfile, type BookingCreatePayload } from '../api/tutors';
import { useAuth } from '../context/AuthContext';
import './TutorMarketplacePage.css';
import './TutorProfilePage.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getInitials(name: string | null): string {
  if (!name) return '?';
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join('');
}

const AVATAR_COLORS = [
  '#4f46e5', '#0891b2', '#059669', '#d97706',
  '#dc2626', '#7c3aed', '#db2777', '#0284c7',
];

function avatarColor(id: number): string {
  return AVATAR_COLORS[id % AVATAR_COLORS.length];
}

function StarRating({ rating, size = 'md' }: { rating: number | null; size?: 'sm' | 'md' | 'lg' }) {
  if (rating === null) return <span className="no-rating">No reviews yet</span>;
  const fontSize = size === 'lg' ? '1.4rem' : size === 'sm' ? '0.9rem' : '1.1rem';
  return (
    <span className="star-rating" style={{ fontSize }}>
      {[1, 2, 3, 4, 5].map((s) => (
        <span key={s} className={s <= Math.round(rating) ? 'star filled' : 'star'}>
          &#9733;
        </span>
      ))}
      <span className="rating-value" style={{ fontSize: '0.85rem' }}>{rating.toFixed(1)}</span>
    </span>
  );
}

function formatAvailability(profile: TutorProfile): string {
  const days = profile.available_days;
  if (!days || days.length === 0) return 'Contact for availability';

  const dayAbbrevs: Record<string, string> = {
    Monday: 'Mon', Tuesday: 'Tue', Wednesday: 'Wed',
    Thursday: 'Thu', Friday: 'Fri', Saturday: 'Sat', Sunday: 'Sun',
  };
  const abbrevs = days.map((d) => dayAbbrevs[d] || d);

  // Try to represent as a range
  const allWeekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
  const sortedAbbrevs = [...abbrevs].sort((a, b) => allWeekdays.indexOf(a) - allWeekdays.indexOf(b));
  let daysStr = sortedAbbrevs.join(', ');
  if (sortedAbbrevs.join(',') === 'Mon,Tue,Wed,Thu,Fri') daysStr = 'Mon–Fri';

  const start = profile.available_hours_start || '16:00';
  const end = profile.available_hours_end || '20:00';

  const fmt = (t: string): string => {
    const [h, m] = t.split(':').map(Number);
    const suffix = h >= 12 ? 'pm' : 'am';
    const hour12 = h % 12 || 12;
    return m ? `${hour12}:${String(m).padStart(2, '0')}${suffix}` : `${hour12}${suffix}`;
  };

  const tz = profile.timezone?.replace('America/', '').replace('_', ' ') || 'ET';
  return `${daysStr} ${fmt(start)}–${fmt(end)} ${tz}`;
}

// ---------------------------------------------------------------------------
// Booking Modal (inline, shared pattern from Marketplace page)
// ---------------------------------------------------------------------------

interface BookingModalProps {
  tutor: TutorProfile;
  onClose: () => void;
  onSuccess: () => void;
}

function BookingModal({ tutor, onClose, onSuccess }: BookingModalProps) {
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [proposedDate, setProposedDate] = useState('');
  const [proposedTime, setProposedTime] = useState('');
  const [duration, setDuration] = useState(tutor.session_duration_minutes || 60);
  const [error, setError] = useState('');

  const mutation = useMutation({
    mutationFn: (payload: BookingCreatePayload) => tutorsApi.bookTutor(tutor.id, payload),
    onSuccess: () => {
      onSuccess();
      onClose();
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail || 'Failed to send booking request. Please try again.');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!subject.trim()) { setError('Subject is required.'); return; }
    if (!message.trim()) { setError('Message is required.'); return; }
    setError('');

    let proposed_date: string | undefined;
    if (proposedDate && proposedTime) {
      proposed_date = `${proposedDate}T${proposedTime}:00`;
    } else if (proposedDate) {
      proposed_date = `${proposedDate}T00:00:00`;
    }

    mutation.mutate({ subject: subject.trim(), message: message.trim(), proposed_date, duration_minutes: duration });
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal-content booking-modal">
        <div className="modal-header">
          <h2>Book a Session with {tutor.tutor_name}</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">&times;</button>
        </div>
        <form onSubmit={handleSubmit} className="booking-form">
          <label>
            Subject *
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Mathematics — Calculus"
              required
            />
          </label>
          <div className="form-row">
            <label>
              Proposed Date
              <input type="date" value={proposedDate} onChange={(e) => setProposedDate(e.target.value)} />
            </label>
            <label>
              Time
              <input type="time" value={proposedTime} onChange={(e) => setProposedTime(e.target.value)} />
            </label>
          </div>
          <label>
            Duration
            <select value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
              <option value={30}>30 minutes</option>
              <option value={45}>45 minutes</option>
              <option value={60}>60 minutes</option>
              <option value={90}>90 minutes</option>
            </select>
          </label>
          <label>
            Message *
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={4}
              placeholder="Briefly describe what you need help with, your current level, and any specific goals..."
              required
            />
          </label>
          {error && <p className="form-error">{error}</p>}
          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={mutation.isPending}>
              {mutation.isPending ? 'Sending...' : 'Send Booking Request'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function TutorProfilePage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [showBooking, setShowBooking] = useState(false);
  const [bookingSuccess, setBookingSuccess] = useState(false);

  const tutorId = Number(id);

  const { data: tutor, isLoading, isError } = useQuery({
    queryKey: ['tutor', tutorId],
    queryFn: () => tutorsApi.getById(tutorId),
    enabled: !isNaN(tutorId),
    staleTime: 60_000,
  });

  // Get bookings to show reviews
  const { data: bookings = [] } = useQuery({
    queryKey: ['tutorBookings', tutorId, 'completed'],
    queryFn: () => tutorsApi.getTutorBookings(tutorId, { status: 'completed', limit: 20 }),
    enabled: !isNaN(tutorId) && (user?.role === 'teacher' || user?.role === 'admin'),
    staleTime: 60_000,
  });

  const reviewedBookings = bookings.filter((b) => b.rating !== null);

  const handleBookingSuccess = useCallback(() => {
    setBookingSuccess(true);
    queryClient.invalidateQueries({ queryKey: ['myBookings'] });
  }, [queryClient]);

  const canBook = user?.role === 'parent' || user?.role === 'student';

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="tutor-profile-page">
          <div className="tutor-loading">
            <div className="loading-spinner" />
            <p>Loading tutor profile...</p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  if (isError || !tutor) {
    return (
      <DashboardLayout>
        <div className="tutor-profile-page">
          <div className="tutor-error">Tutor not found or an error occurred.</div>
          <Link to="/tutors" className="btn-outline" style={{ marginTop: '1rem', display: 'inline-block' }}>
            Back to Tutors
          </Link>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="tutor-profile-page">
        {/* Back link */}
        <Link to="/tutors" className="back-link">
          &larr; Back to Tutors
        </Link>

        {bookingSuccess && (
          <div className="booking-success-banner" style={{ marginBottom: '1.5rem' }}>
            Booking request sent! The tutor will review your request and respond shortly.
          </div>
        )}

        <div className="tutor-profile-layout">
          {/* Left: Main info */}
          <div className="tutor-profile-main">
            {/* Header */}
            <div className="profile-header">
              <div
                className="tutor-avatar tutor-avatar--lg"
                style={{ backgroundColor: avatarColor(tutor.id) }}
              >
                {getInitials(tutor.tutor_name)}
              </div>
              <div className="profile-header-info">
                <div className="tutor-name-row">
                  <h1 className="profile-name">{tutor.tutor_name || 'Tutor'}</h1>
                  {tutor.is_verified && (
                    <span className="verified-badge">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                        <polyline points="22 4 12 14.01 9 11.01"/>
                      </svg>
                      Verified
                    </span>
                  )}
                </div>
                <p className="profile-headline">{tutor.headline}</p>
                <div className="profile-rating-row">
                  <StarRating rating={tutor.avg_rating} size="lg" />
                  {tutor.review_count > 0 && (
                    <span className="review-count">({tutor.review_count} review{tutor.review_count !== 1 ? 's' : ''})</span>
                  )}
                  <span className="sessions-count">{tutor.total_sessions} session{tutor.total_sessions !== 1 ? 's' : ''} completed</span>
                </div>
              </div>
            </div>

            {/* Bio */}
            <section className="profile-section">
              <h2 className="section-title">About</h2>
              <p className="profile-bio">{tutor.bio}</p>
            </section>

            {/* Subjects & Grades */}
            <section className="profile-section">
              <h2 className="section-title">Subjects & Grade Levels</h2>
              <div className="profile-chips-group">
                {tutor.subjects.map((s) => (
                  <span key={s} className="subject-chip subject-chip--static">{s}</span>
                ))}
              </div>
              <div className="grade-levels-row">
                <strong>Grade levels:</strong>
                <span>{tutor.grade_levels.map((g) => `Grade ${g}`).join(', ')}</span>
              </div>
            </section>

            {/* Reviews */}
            <section className="profile-section">
              <h2 className="section-title">
                Reviews
                {tutor.review_count > 0 && (
                  <span className="section-badge">{tutor.review_count}</span>
                )}
              </h2>
              {reviewedBookings.length === 0 ? (
                <p className="no-reviews">No reviews yet. Be the first to work with this tutor!</p>
              ) : (
                <div className="reviews-list">
                  {reviewedBookings.map((b) => (
                    <div key={b.id} className="review-card">
                      <div className="review-header">
                        <StarRating rating={b.rating} size="sm" />
                        <span className="review-date">
                          {b.reviewed_at ? new Date(b.reviewed_at).toLocaleDateString() : ''}
                        </span>
                      </div>
                      {b.review_text && <p className="review-text">{b.review_text}</p>}
                      <p className="review-subject">Subject: {b.subject}</p>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          {/* Right: Sidebar */}
          <aside className="tutor-profile-sidebar">
            <div className="sidebar-card">
              <div className="rate-display">
                <span className="rate-amount">${tutor.hourly_rate_cad.toFixed(0)}</span>
                <span className="rate-unit"> / hour</span>
              </div>
              <div className="session-duration">
                Default session: {tutor.session_duration_minutes} min
              </div>

              {canBook && (
                <button
                  className="btn-primary btn-book-full"
                  onClick={() => setShowBooking(true)}
                  disabled={!tutor.is_accepting_students}
                >
                  {tutor.is_accepting_students ? 'Book a Session' : 'Not Accepting Students'}
                </button>
              )}

              {!tutor.is_active && (
                <p className="profile-inactive-note">This tutor is currently inactive.</p>
              )}
            </div>

            <div className="sidebar-card">
              <h3 className="sidebar-card-title">Details</h3>
              <ul className="detail-list">
                {tutor.years_experience !== null && (
                  <li>
                    <strong>Experience:</strong>
                    {' '}{tutor.years_experience} year{tutor.years_experience !== 1 ? 's' : ''}
                  </li>
                )}
                {tutor.school_affiliation && (
                  <li>
                    <strong>Affiliation:</strong> {tutor.school_affiliation}
                  </li>
                )}
                <li>
                  <strong>Languages:</strong> {tutor.languages.join(', ')}
                </li>
                <li>
                  <strong>Availability:</strong>{' '}{formatAvailability(tutor)}
                </li>
                {tutor.online_only ? (
                  <li><strong>Mode:</strong> Online sessions only</li>
                ) : tutor.location_city ? (
                  <li><strong>Location:</strong> {tutor.location_city}</li>
                ) : null}
              </ul>
            </div>

            {tutor.certifications && tutor.certifications.length > 0 && (
              <div className="sidebar-card">
                <h3 className="sidebar-card-title">Certifications</h3>
                <ul className="cert-list">
                  {tutor.certifications.map((c) => (
                    <li key={c} className="cert-item">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                        <polyline points="22 4 12 14.01 9 11.01"/>
                      </svg>
                      {c}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </aside>
        </div>
      </div>

      {showBooking && (
        <BookingModal
          tutor={tutor}
          onClose={() => setShowBooking(false)}
          onSuccess={handleBookingSuccess}
        />
      )}
    </DashboardLayout>
  );
}
