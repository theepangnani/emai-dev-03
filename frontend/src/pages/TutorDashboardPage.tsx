import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import {
  tutorsApi,
  type TutorProfile,
  type TutorBooking,
  type TutorProfileCreatePayload,
  type TutorProfileUpdatePayload,
} from '../api/tutors';
import './TutorDashboardPage.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  accepted: 'Accepted',
  declined: 'Declined',
  completed: 'Completed',
  cancelled: 'Cancelled',
};

const STATUS_CLASSES: Record<string, string> = {
  pending: 'badge-pending',
  accepted: 'badge-accepted',
  declined: 'badge-declined',
  completed: 'badge-completed',
  cancelled: 'badge-cancelled',
};

function StarDisplay({ rating }: { rating: number | null }) {
  if (!rating) return null;
  return (
    <span className="stars-display">
      {[1, 2, 3, 4, 5].map((s) => (
        <span key={s} style={{ color: s <= rating ? '#f59e0b' : '#d1d5db' }}>&#9733;</span>
      ))}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Profile Form
// ---------------------------------------------------------------------------

const DEFAULT_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
const ALL_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const COMMON_SUBJECTS = [
  'Mathematics', 'Physics', 'Chemistry', 'Biology', 'English', 'French',
  'History', 'Geography', 'Computer Science', 'Economics', 'Accounting',
];

interface ProfileFormProps {
  existing: TutorProfile | null;
  onSaved: () => void;
}

function ProfileForm({ existing, onSaved }: ProfileFormProps) {
  const [bio, setBio] = useState(existing?.bio || '');
  const [headline, setHeadline] = useState(existing?.headline || '');
  const [subjectsInput, setSubjectsInput] = useState(
    existing?.subjects.join(', ') || '',
  );
  const [gradeLevels, setGradeLevels] = useState<string[]>(
    existing?.grade_levels || ['9', '10', '11', '12'],
  );
  const [languages, setLanguages] = useState(existing?.languages.join(', ') || 'English');
  const [rate, setRate] = useState(existing?.hourly_rate_cad || 60);
  const [sessionDuration, setSessionDuration] = useState(existing?.session_duration_minutes || 60);
  const [availableDays, setAvailableDays] = useState<string[]>(
    existing?.available_days || DEFAULT_DAYS,
  );
  const [hoursStart, setHoursStart] = useState(existing?.available_hours_start || '16:00');
  const [hoursEnd, setHoursEnd] = useState(existing?.available_hours_end || '20:00');
  const [timezone, setTimezone] = useState(existing?.timezone || 'America/Toronto');
  const [onlineOnly, setOnlineOnly] = useState(existing?.online_only || false);
  const [locationCity, setLocationCity] = useState(existing?.location_city || '');
  const [yearsExp, setYearsExp] = useState(existing?.years_experience?.toString() || '');
  const [schoolAffil, setSchoolAffil] = useState(existing?.school_affiliation || '');
  const [isAccepting, setIsAccepting] = useState(existing?.is_accepting_students ?? true);
  const [error, setError] = useState('');

  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (payload: TutorProfileCreatePayload) => tutorsApi.createProfile(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myTutorProfile'] });
      onSaved();
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail || 'Failed to save profile.');
    },
  });

  const updateMutation = useMutation({
    mutationFn: (payload: TutorProfileUpdatePayload) => tutorsApi.updateProfile(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myTutorProfile'] });
      onSaved();
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail || 'Failed to save profile.');
    },
  });

  const isPending = createMutation.isPending || updateMutation.isPending;

  const handleDayToggle = (day: string) => {
    setAvailableDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day],
    );
  };

  const handleGradeLevelToggle = (grade: string) => {
    setGradeLevels((prev) =>
      prev.includes(grade) ? prev.filter((g) => g !== grade) : [...prev, grade],
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const subjects = subjectsInput
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    if (subjects.length === 0) { setError('Please enter at least one subject.'); return; }
    if (!bio.trim()) { setError('Bio is required.'); return; }
    if (!headline.trim()) { setError('Headline is required.'); return; }
    if (gradeLevels.length === 0) { setError('Select at least one grade level.'); return; }
    if (availableDays.length === 0) { setError('Select at least one available day.'); return; }

    const langList = languages.split(',').map((l) => l.trim()).filter(Boolean);
    if (langList.length === 0) { setError('Please enter at least one language.'); return; }

    const payload: TutorProfileCreatePayload = {
      bio: bio.trim(),
      headline: headline.trim(),
      subjects,
      grade_levels: gradeLevels,
      languages: langList,
      hourly_rate_cad: rate,
      session_duration_minutes: sessionDuration,
      available_days: availableDays,
      available_hours_start: hoursStart,
      available_hours_end: hoursEnd,
      timezone,
      online_only: onlineOnly,
      location_city: locationCity.trim() || null,
      years_experience: yearsExp ? parseInt(yearsExp, 10) : null,
      school_affiliation: schoolAffil.trim() || null,
      is_accepting_students: isAccepting,
    };

    if (existing) {
      updateMutation.mutate(payload as TutorProfileUpdatePayload);
    } else {
      createMutation.mutate(payload);
    }
  };

  return (
    <form className="profile-form" onSubmit={handleSubmit}>
      <div className="form-grid">
        <label className="form-label full-width">
          Headline *
          <input
            type="text"
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            placeholder="e.g. Certified Math Teacher with 8 years experience"
            required
          />
        </label>

        <label className="form-label full-width">
          Bio *
          <textarea
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            rows={5}
            placeholder="Tell students about your background, teaching style, and what makes you an effective tutor..."
            required
          />
        </label>

        <label className="form-label full-width">
          Subjects (comma-separated) *
          <input
            type="text"
            value={subjectsInput}
            onChange={(e) => setSubjectsInput(e.target.value)}
            placeholder="e.g. Mathematics, Physics, Chemistry"
          />
          <div className="quick-add-chips">
            {COMMON_SUBJECTS.map((s) => (
              <button
                key={s}
                type="button"
                className="quick-chip"
                onClick={() => {
                  const current = subjectsInput.split(',').map((x) => x.trim()).filter(Boolean);
                  if (!current.includes(s)) {
                    setSubjectsInput([...current, s].join(', '));
                  }
                }}
              >
                + {s}
              </button>
            ))}
          </div>
        </label>

        <div className="form-label">
          <span className="label-text">Grade Levels *</span>
          <div className="toggle-group">
            {['9', '10', '11', '12'].map((g) => (
              <label key={g} className="toggle-label">
                <input
                  type="checkbox"
                  checked={gradeLevels.includes(g)}
                  onChange={() => handleGradeLevelToggle(g)}
                />
                Grade {g}
              </label>
            ))}
          </div>
        </div>

        <label className="form-label">
          Languages (comma-separated) *
          <input
            type="text"
            value={languages}
            onChange={(e) => setLanguages(e.target.value)}
            placeholder="e.g. English, French"
          />
        </label>

        <label className="form-label">
          Hourly Rate (CAD) *
          <div className="input-prefix-group">
            <span className="input-prefix">$</span>
            <input
              type="number"
              value={rate}
              onChange={(e) => setRate(Number(e.target.value))}
              min={1}
              step={5}
              required
            />
          </div>
        </label>

        <label className="form-label">
          Default Session Duration
          <select value={sessionDuration} onChange={(e) => setSessionDuration(Number(e.target.value))}>
            <option value={30}>30 minutes</option>
            <option value={45}>45 minutes</option>
            <option value={60}>60 minutes</option>
            <option value={90}>90 minutes</option>
          </select>
        </label>

        <div className="form-label full-width">
          <span className="label-text">Available Days *</span>
          <div className="toggle-group">
            {ALL_DAYS.map((d) => (
              <label key={d} className="toggle-label">
                <input
                  type="checkbox"
                  checked={availableDays.includes(d)}
                  onChange={() => handleDayToggle(d)}
                />
                {d.slice(0, 3)}
              </label>
            ))}
          </div>
        </div>

        <label className="form-label">
          Available From
          <input type="time" value={hoursStart} onChange={(e) => setHoursStart(e.target.value)} />
        </label>

        <label className="form-label">
          Available Until
          <input type="time" value={hoursEnd} onChange={(e) => setHoursEnd(e.target.value)} />
        </label>

        <label className="form-label">
          Timezone
          <select value={timezone} onChange={(e) => setTimezone(e.target.value)}>
            <option value="America/Toronto">Eastern (Toronto)</option>
            <option value="America/Winnipeg">Central (Winnipeg)</option>
            <option value="America/Edmonton">Mountain (Edmonton)</option>
            <option value="America/Vancouver">Pacific (Vancouver)</option>
          </select>
        </label>

        <label className="form-label">
          Years of Experience
          <input
            type="number"
            value={yearsExp}
            onChange={(e) => setYearsExp(e.target.value)}
            min={0}
            max={60}
            placeholder="e.g. 5"
          />
        </label>

        <label className="form-label">
          School / Board Affiliation
          <input
            type="text"
            value={schoolAffil}
            onChange={(e) => setSchoolAffil(e.target.value)}
            placeholder="e.g. TDSB, OCDSB"
          />
        </label>

        <label className="form-label">
          Location (City, Province)
          <input
            type="text"
            value={locationCity}
            onChange={(e) => setLocationCity(e.target.value)}
            placeholder="e.g. Toronto, ON"
            disabled={onlineOnly}
          />
        </label>

        <div className="form-label checkbox-label">
          <label className="toggle-label">
            <input
              type="checkbox"
              checked={onlineOnly}
              onChange={(e) => setOnlineOnly(e.target.checked)}
            />
            Online sessions only
          </label>
        </div>

        <div className="form-label checkbox-label">
          <label className="toggle-label">
            <input
              type="checkbox"
              checked={isAccepting}
              onChange={(e) => setIsAccepting(e.target.checked)}
            />
            Currently accepting new students
          </label>
        </div>
      </div>

      {error && <p className="form-error">{error}</p>}

      <div className="form-actions">
        <button type="submit" className="btn-primary" disabled={isPending}>
          {isPending ? 'Saving...' : existing ? 'Update Profile' : 'Create Profile'}
        </button>
      </div>

      {!existing && (
        <p className="form-note">
          Your profile will be reviewed and verified by an admin before appearing as verified in search results.
        </p>
      )}
    </form>
  );
}

// ---------------------------------------------------------------------------
// Booking Request Card
// ---------------------------------------------------------------------------

interface BookingCardProps {
  booking: TutorBooking;
  onRespond: (id: number, status: 'accepted' | 'declined', response: string) => void;
  responding: number | null;
}

function BookingCard({ booking, onRespond, responding }: BookingCardProps) {
  const [response, setResponse] = useState('');
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`booking-card booking-card--${booking.status}`}>
      <div className="booking-card-header">
        <div>
          <h4 className="booking-subject">{booking.subject}</h4>
          <p className="booking-meta">
            From: {booking.requester_name || 'Unknown'} &middot;
            Student: {booking.student_name || 'Unknown'}
          </p>
          {booking.proposed_date && (
            <p className="booking-meta">
              Proposed: {new Date(booking.proposed_date).toLocaleString()}
            </p>
          )}
          <p className="booking-meta">Duration: {booking.duration_minutes} min</p>
        </div>
        <span className={`status-badge ${STATUS_CLASSES[booking.status] || ''}`}>
          {STATUS_LABELS[booking.status] || booking.status}
        </span>
      </div>

      {booking.message && (
        <p className="booking-message">"{booking.message}"</p>
      )}

      {booking.rating !== null && (
        <div className="booking-review">
          <StarDisplay rating={booking.rating} />
          {booking.review_text && <p className="review-text">{booking.review_text}</p>}
        </div>
      )}

      {booking.status === 'pending' && (
        <div className="booking-respond">
          <button
            className="respond-toggle"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? 'Hide response' : 'Respond to request'}
          </button>
          {expanded && (
            <div className="respond-form">
              <textarea
                value={response}
                onChange={(e) => setResponse(e.target.value)}
                rows={3}
                placeholder="Optional: add a message to the student..."
              />
              <div className="respond-actions">
                <button
                  className="btn-accept"
                  disabled={responding === booking.id}
                  onClick={() => onRespond(booking.id, 'accepted', response)}
                >
                  Accept
                </button>
                <button
                  className="btn-decline"
                  disabled={responding === booking.id}
                  onClick={() => onRespond(booking.id, 'declined', response)}
                >
                  Decline
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {booking.tutor_response && booking.status !== 'pending' && (
        <p className="tutor-response">Your response: "{booking.tutor_response}"</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function TutorDashboardPage() {
  const queryClient = useQueryClient();
  const [editingProfile, setEditingProfile] = useState(false);
  const [respondingId, setRespondingId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<'pending' | 'all'>('pending');
  const [respondError, setRespondError] = useState('');

  const {
    data: profile,
    isLoading: profileLoading,
    isError: profileError,
  } = useQuery({
    queryKey: ['myTutorProfile'],
    queryFn: () => tutorsApi.getMyProfile(),
    retry: false,
  });

  const {
    data: pendingBookings = [],
    isLoading: bookingsLoading,
  } = useQuery({
    queryKey: ['myTutorBookings', 'pending'],
    queryFn: () => profile ? tutorsApi.getTutorBookings(profile.id, { status: 'pending', limit: 50 }) : [],
    enabled: !!profile,
  });

  const {
    data: allBookings = [],
  } = useQuery({
    queryKey: ['myTutorBookings', 'all'],
    queryFn: () => profile ? tutorsApi.getTutorBookings(profile.id, { limit: 50 }) : [],
    enabled: !!profile && activeTab === 'all',
  });

  const respondMutation = useMutation({
    mutationFn: ({ id, status, response }: { id: number; status: 'accepted' | 'declined'; response: string }) =>
      tutorsApi.respondToBooking(id, { status, tutor_response: response }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myTutorBookings'] });
      setRespondingId(null);
    },
    onError: (err: any) => {
      setRespondError(err?.response?.data?.detail || 'Failed to respond to booking.');
      setRespondingId(null);
    },
  });

  const handleRespond = (id: number, status: 'accepted' | 'declined', response: string) => {
    setRespondingId(id);
    setRespondError('');
    respondMutation.mutate({ id, status, response });
  };

  const noProfile = profileError || (!profileLoading && !profile);
  const displayedBookings = activeTab === 'pending' ? pendingBookings : allBookings;

  return (
    <DashboardLayout welcomeSubtitle="Manage your tutor profile and incoming booking requests">
      <div className="tutor-dashboard">
        <h1 className="page-title">Tutor Dashboard</h1>

        {/* ── Profile Section ── */}
        <section className="dashboard-section">
          <div className="section-header">
            <h2 className="section-title">My Tutor Profile</h2>
            {profile && !editingProfile && (
              <button className="btn-outline" onClick={() => setEditingProfile(true)}>
                Edit Profile
              </button>
            )}
            {editingProfile && (
              <button className="btn-secondary" onClick={() => setEditingProfile(false)}>
                Cancel
              </button>
            )}
          </div>

          {profileLoading && <div className="loading-text">Loading profile...</div>}

          {profile && !editingProfile && (
            <div className="profile-summary">
              <div className="profile-summary-header">
                <div>
                  <h3 className="profile-summary-headline">{profile.headline}</h3>
                  <p className="profile-summary-rate">${profile.hourly_rate_cad}/hr</p>
                </div>
                <div className="profile-summary-badges">
                  {profile.is_verified ? (
                    <span className="verified-badge">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                        <polyline points="22 4 12 14.01 9 11.01"/>
                      </svg>
                      Verified
                    </span>
                  ) : (
                    <span className="pending-badge">Pending verification</span>
                  )}
                  <span className={profile.is_accepting_students ? 'accepting-badge' : 'not-accepting-badge'}>
                    {profile.is_accepting_students ? 'Accepting students' : 'Not accepting'}
                  </span>
                </div>
              </div>
              <p className="profile-summary-bio">{profile.bio}</p>
              <div className="profile-summary-meta">
                <div><strong>Subjects:</strong> {profile.subjects.join(', ')}</div>
                <div><strong>Grades:</strong> {profile.grade_levels.map((g) => `Grade ${g}`).join(', ')}</div>
                <div><strong>Sessions:</strong> {profile.total_sessions} completed</div>
                {profile.avg_rating && (
                  <div><strong>Rating:</strong> {profile.avg_rating.toFixed(1)} ({profile.review_count} reviews)</div>
                )}
              </div>
            </div>
          )}

          {(noProfile || editingProfile) && (
            <>
              {noProfile && !editingProfile && (
                <div className="no-profile-prompt">
                  <p>You don't have a tutor profile yet. Create one to appear in the tutor marketplace.</p>
                  <button className="btn-primary" onClick={() => setEditingProfile(true)}>
                    Create Profile
                  </button>
                </div>
              )}
              {editingProfile && (
                <ProfileForm
                  existing={profile || null}
                  onSaved={() => setEditingProfile(false)}
                />
              )}
            </>
          )}
        </section>

        {/* ── Bookings Section ── */}
        {profile && (
          <section className="dashboard-section">
            <div className="section-header">
              <h2 className="section-title">
                Booking Requests
                {pendingBookings.length > 0 && (
                  <span className="pending-count">{pendingBookings.length}</span>
                )}
              </h2>
              <div className="tab-switcher">
                <button
                  className={activeTab === 'pending' ? 'tab-btn active' : 'tab-btn'}
                  onClick={() => setActiveTab('pending')}
                >
                  Pending ({pendingBookings.length})
                </button>
                <button
                  className={activeTab === 'all' ? 'tab-btn active' : 'tab-btn'}
                  onClick={() => setActiveTab('all')}
                >
                  All Bookings
                </button>
              </div>
            </div>

            {respondError && <p className="form-error">{respondError}</p>}

            {bookingsLoading && <div className="loading-text">Loading bookings...</div>}

            {!bookingsLoading && displayedBookings.length === 0 && (
              <p className="empty-text">
                {activeTab === 'pending'
                  ? 'No pending booking requests.'
                  : 'No booking history yet.'}
              </p>
            )}

            <div className="bookings-list">
              {displayedBookings.map((booking) => (
                <BookingCard
                  key={booking.id}
                  booking={booking}
                  onRespond={handleRespond}
                  responding={respondingId}
                />
              ))}
            </div>
          </section>
        )}
      </div>
    </DashboardLayout>
  );
}
