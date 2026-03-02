import { useState, useCallback, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { tutorsApi, type TutorProfile, type BookingCreatePayload } from '../api/tutors';
import './TutorMarketplacePage.css';

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

function StarRating({ rating }: { rating: number | null }) {
  if (rating === null) return <span className="no-rating">No reviews yet</span>;
  return (
    <span className="star-rating">
      {[1, 2, 3, 4, 5].map((s) => (
        <span key={s} className={s <= Math.round(rating) ? 'star filled' : 'star'}>
          &#9733;
        </span>
      ))}
      <span className="rating-value">{rating.toFixed(1)}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Booking Modal
// ---------------------------------------------------------------------------

interface BookingModalProps {
  tutor: TutorProfile;
  initialSubject?: string;
  onClose: () => void;
  onSuccess: () => void;
}

function BookingModal({ tutor, initialSubject, onClose, onSuccess }: BookingModalProps) {
  const [subject, setSubject] = useState(initialSubject || '');
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
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Book a Session">
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
// Tutor Card
// ---------------------------------------------------------------------------

interface TutorCardProps {
  tutor: TutorProfile;
  onBook: (tutor: TutorProfile, subject?: string) => void;
}

function TutorCard({ tutor, onBook }: TutorCardProps) {
  const visibleSubjects = tutor.subjects.slice(0, 3);
  const extraSubjects = tutor.subjects.length - 3;

  return (
    <div className="tutor-card">
      <div className="tutor-card-header">
        <div
          className="tutor-avatar"
          style={{ backgroundColor: avatarColor(tutor.id) }}
          aria-hidden="true"
        >
          {getInitials(tutor.tutor_name)}
        </div>
        <div className="tutor-card-info">
          <div className="tutor-name-row">
            <h3 className="tutor-name">{tutor.tutor_name || 'Tutor'}</h3>
            {tutor.is_verified && (
              <span className="verified-badge" title="Verified tutor">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                  <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
                Verified
              </span>
            )}
          </div>
          <p className="tutor-headline">{tutor.headline}</p>
        </div>
      </div>

      <div className="tutor-card-subjects">
        {visibleSubjects.map((s) => (
          <button
            key={s}
            className="subject-chip"
            onClick={() => onBook(tutor, s)}
            title={`Book a session for ${s}`}
          >
            {s}
          </button>
        ))}
        {extraSubjects > 0 && (
          <span className="subject-chip subject-chip--more">+{extraSubjects} more</span>
        )}
      </div>

      <div className="tutor-card-meta">
        <div className="meta-item">
          <span className="meta-label">Grades:</span>
          <span className="meta-value">{tutor.grade_levels.join(', ')}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Languages:</span>
          <span className="meta-value">{tutor.languages.join(', ')}</span>
        </div>
        {tutor.location_city && !tutor.online_only && (
          <div className="meta-item">
            <span className="meta-label">Location:</span>
            <span className="meta-value">{tutor.location_city}</span>
          </div>
        )}
        {tutor.online_only && (
          <div className="meta-item online-badge">Online sessions only</div>
        )}
      </div>

      <div className="tutor-card-footer">
        <div className="tutor-rate">
          <span className="rate-amount">${tutor.hourly_rate_cad.toFixed(0)}</span>
          <span className="rate-unit">/hr</span>
        </div>
        <div className="tutor-rating">
          <StarRating rating={tutor.avg_rating} />
          {tutor.review_count > 0 && (
            <span className="review-count">({tutor.review_count})</span>
          )}
        </div>
      </div>

      <div className="tutor-card-actions">
        <Link to={`/tutors/${tutor.id}`} className="btn-outline">
          View Profile
        </Link>
        <button
          className="btn-primary"
          onClick={() => onBook(tutor)}
          disabled={!tutor.is_accepting_students}
          title={!tutor.is_accepting_students ? 'Not accepting new students' : undefined}
        >
          {tutor.is_accepting_students ? 'Book a Session' : 'Not Accepting'}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function TutorMarketplacePage() {
  const queryClient = useQueryClient();

  // Filters
  const [subject, setSubject] = useState('');
  const [gradeLevel, setGradeLevel] = useState('');
  const [maxRate, setMaxRate] = useState(200);
  const [onlineOnly, setOnlineOnly] = useState(false);
  const [verifiedOnly, setVerifiedOnly] = useState(false);

  // Booking modal
  const [bookingTutor, setBookingTutor] = useState<TutorProfile | null>(null);
  const [bookingSubject, setBookingSubject] = useState<string | undefined>(undefined);
  const [bookingSuccess, setBookingSuccess] = useState(false);

  // Build query params — debounce via useMemo
  const searchParams = useMemo(() => ({
    subject: subject.trim() || undefined,
    grade_level: gradeLevel || undefined,
    max_rate: maxRate < 200 ? maxRate : undefined,
    online_only: onlineOnly || undefined,
    verified: verifiedOnly || undefined,
    limit: 50,
  }), [subject, gradeLevel, maxRate, onlineOnly, verifiedOnly]);

  const { data: tutors = [], isLoading, isError } = useQuery({
    queryKey: ['tutors', searchParams],
    queryFn: () => tutorsApi.search(searchParams),
    staleTime: 60_000,
  });

  const handleBook = useCallback((tutor: TutorProfile, sub?: string) => {
    setBookingTutor(tutor);
    setBookingSubject(sub);
    setBookingSuccess(false);
  }, []);

  const handleBookingSuccess = useCallback(() => {
    setBookingSuccess(true);
    queryClient.invalidateQueries({ queryKey: ['myBookings'] });
  }, [queryClient]);

  return (
    <DashboardLayout welcomeSubtitle="Find a qualified tutor for personalized learning">
      <div className="tutor-marketplace">
        {/* Filter bar */}
        <div className="tutor-filters">
          <div className="filter-group">
            <label className="filter-label" htmlFor="filter-subject">Subject</label>
            <input
              id="filter-subject"
              type="text"
              className="filter-input"
              placeholder="e.g. Mathematics"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />
          </div>

          <div className="filter-group">
            <label className="filter-label" htmlFor="filter-grade">Grade Level</label>
            <select
              id="filter-grade"
              className="filter-select"
              value={gradeLevel}
              onChange={(e) => setGradeLevel(e.target.value)}
            >
              <option value="">Any grade</option>
              <option value="9">Grade 9</option>
              <option value="10">Grade 10</option>
              <option value="11">Grade 11</option>
              <option value="12">Grade 12</option>
            </select>
          </div>

          <div className="filter-group filter-group--slider">
            <label className="filter-label" htmlFor="filter-rate">
              Max Rate: {maxRate >= 200 ? 'Any' : `$${maxRate}/hr`}
            </label>
            <input
              id="filter-rate"
              type="range"
              className="filter-slider"
              min={0}
              max={200}
              step={10}
              value={maxRate}
              onChange={(e) => setMaxRate(Number(e.target.value))}
            />
          </div>

          <div className="filter-group filter-group--toggle">
            <label className="filter-toggle">
              <input
                type="checkbox"
                checked={onlineOnly}
                onChange={(e) => setOnlineOnly(e.target.checked)}
              />
              <span>Online only</span>
            </label>
            <label className="filter-toggle">
              <input
                type="checkbox"
                checked={verifiedOnly}
                onChange={(e) => setVerifiedOnly(e.target.checked)}
              />
              <span>Verified only</span>
            </label>
          </div>

          <div className="filter-results-count">
            {isLoading ? 'Searching...' : `${tutors.length} tutor${tutors.length !== 1 ? 's' : ''} found`}
          </div>
        </div>

        {/* Success banner */}
        {bookingSuccess && (
          <div className="booking-success-banner">
            Booking request sent! The tutor will review your request and respond shortly.
            <button
              className="banner-dismiss"
              onClick={() => setBookingSuccess(false)}
              aria-label="Dismiss"
            >
              &times;
            </button>
          </div>
        )}

        {/* Content */}
        {isLoading && (
          <div className="tutor-loading">
            <div className="loading-spinner" aria-label="Loading tutors" />
            <p>Finding available tutors...</p>
          </div>
        )}

        {isError && (
          <div className="tutor-error">
            Failed to load tutors. Please try again later.
          </div>
        )}

        {!isLoading && !isError && tutors.length === 0 && (
          <div className="tutor-empty">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="11" cy="11" r="8"/>
              <line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <h3>No tutors found</h3>
            <p>No tutors available matching your criteria. Check back soon!</p>
          </div>
        )}

        {!isLoading && !isError && tutors.length > 0 && (
          <div className="tutor-grid" role="list">
            {tutors.map((tutor) => (
              <div key={tutor.id} role="listitem">
                <TutorCard tutor={tutor} onBook={handleBook} />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Booking Modal */}
      {bookingTutor && (
        <BookingModal
          tutor={bookingTutor}
          initialSubject={bookingSubject}
          onClose={() => setBookingTutor(null)}
          onSuccess={handleBookingSuccess}
        />
      )}
    </DashboardLayout>
  );
}
