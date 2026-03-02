import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { tutorMatchingApi, type TutorMatch, type TutorMatchPreference } from '../api/tutorMatching';
import { tutorsApi, type BookingCreatePayload } from '../api/tutors';
import './TutorMatchPage.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const AVATAR_COLORS = [
  '#4f46e5', '#0891b2', '#059669', '#d97706',
  '#dc2626', '#7c3aed', '#db2777', '#0284c7',
];

function avatarColor(id: number): string {
  return AVATAR_COLORS[id % AVATAR_COLORS.length];
}

function getInitials(name: string | null): string {
  if (!name) return '?';
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join('');
}

function ScoreBar({
  label,
  value,
  max,
  colorClass = 'bar-primary',
}: {
  label: string;
  value: number;
  max: number;
  colorClass?: string;
}) {
  const pct = Math.round((value / max) * 100);
  return (
    <div className="score-bar-row">
      <span className="score-bar-label">{label}</span>
      <div className="score-bar-track" role="progressbar" aria-valuenow={value} aria-valuemax={max} aria-label={`${label}: ${value} of ${max}`}>
        <div
          className={`score-bar-fill ${colorClass}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="score-bar-value">
        {Math.round(value)}/{max}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Match Breakdown Widget
// ---------------------------------------------------------------------------

function MatchBreakdown({ match }: { match: TutorMatch }) {
  const { breakdown } = match;
  return (
    <div className="match-breakdown">
      <ScoreBar label="Subject Coverage" value={breakdown.subject_match} max={breakdown.subject_match_max} colorClass="bar-blue" />
      <ScoreBar label="Grade Match" value={breakdown.grade_match} max={breakdown.grade_match_max} colorClass="bar-green" />
      <ScoreBar label="Rating" value={breakdown.rating_score} max={breakdown.rating_score_max} colorClass="bar-yellow" />
      <ScoreBar label="Learning Style" value={breakdown.style_match} max={breakdown.style_match_max} colorClass="bar-purple" />
      <ScoreBar label="Price" value={breakdown.price_score} max={breakdown.price_score_max} colorClass="bar-teal" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Booking Modal (inline, minimal)
// ---------------------------------------------------------------------------

function BookingModal({
  tutorId,
  tutorName,
  onClose,
  onSuccess,
}: {
  tutorId: number;
  tutorName: string | null;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const mutation = useMutation({
    mutationFn: (payload: BookingCreatePayload) => tutorsApi.bookTutor(tutorId, payload),
    onSuccess: () => { onSuccess(); onClose(); },
    onError: (err: any) => setError(err?.response?.data?.detail || 'Failed to send booking request.'),
  });

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal-content">
        <div className="modal-header">
          <h2>Book a Session with {tutorName || 'Tutor'}</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">&times;</button>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!subject.trim()) { setError('Subject is required'); return; }
            if (!message.trim()) { setError('Message is required'); return; }
            setError('');
            mutation.mutate({ subject: subject.trim(), message: message.trim() });
          }}
          className="booking-form"
        >
          <label>
            Subject *
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Mathematics — Quadratic Equations"
              required
            />
          </label>
          <label>
            Message *
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={4}
              placeholder="What do you need help with? Describe your current level and goals..."
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
// Preferences Modal
// ---------------------------------------------------------------------------

function PreferencesModal({
  current,
  onClose,
  onSave,
}: {
  current: TutorMatchPreference;
  onClose: () => void;
  onSave: (prefs: Partial<TutorMatchPreference>) => void;
}) {
  const [maxRate, setMaxRate] = useState<number | ''>(current.max_hourly_rate_cad ?? '');
  const [minRating, setMinRating] = useState(current.min_rating ?? 3.0);
  const [verifiedOnly, setVerifiedOnly] = useState(current.prefer_verified_only ?? false);
  const [subjectInput, setSubjectInput] = useState(current.preferred_subjects.join(', '));

  const handleSave = () => {
    const subjects = subjectInput
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    onSave({
      max_hourly_rate_cad: maxRate === '' ? null : Number(maxRate),
      min_rating: minRating,
      prefer_verified_only: verifiedOnly,
      preferred_subjects: subjects,
    });
    onClose();
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal-content prefs-modal">
        <div className="modal-header">
          <h2>Matching Preferences</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">&times;</button>
        </div>
        <div className="prefs-form">
          <label>
            Max Hourly Rate (CAD)
            <div className="rate-input-row">
              <input
                type="range"
                min={20}
                max={200}
                step={5}
                value={maxRate === '' ? 200 : maxRate}
                onChange={(e) => setMaxRate(Number(e.target.value))}
              />
              <span className="rate-display">
                {maxRate === '' || maxRate === 200 ? 'No limit' : `$${maxRate}/hr`}
              </span>
            </div>
          </label>

          <label>
            Minimum Rating: {minRating.toFixed(1)} stars
            <input
              type="range"
              min={1}
              max={5}
              step={0.5}
              value={minRating}
              onChange={(e) => setMinRating(Number(e.target.value))}
            />
          </label>

          <label>
            Preferred Subjects (comma-separated)
            <input
              type="text"
              value={subjectInput}
              onChange={(e) => setSubjectInput(e.target.value)}
              placeholder="e.g. Mathematics, Science, English"
            />
          </label>

          <label className="toggle-label">
            <input
              type="checkbox"
              checked={verifiedOnly}
              onChange={(e) => setVerifiedOnly(e.target.checked)}
            />
            Verified tutors only
          </label>
        </div>

        <div className="modal-actions">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={handleSave}>Save Preferences</button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Match Card
// ---------------------------------------------------------------------------

function MatchCard({
  match,
  rank,
  onBook,
}: {
  match: TutorMatch;
  rank: number;
  onBook: (match: TutorMatch) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const tutor = match.tutor;
  const scorePct = Math.round(match.score);

  return (
    <div className="match-card">
      <div className="match-card-rank">#{rank}</div>

      <div className="match-card-header">
        <div
          className="tutor-avatar"
          style={{ backgroundColor: avatarColor(tutor.id) }}
          aria-hidden="true"
        >
          {getInitials(tutor.tutor_name)}
        </div>

        <div className="match-card-info">
          <div className="match-name-row">
            <h3 className="match-tutor-name">{tutor.tutor_name || 'Tutor'}</h3>
            {tutor.is_verified && (
              <span className="verified-badge" title="Verified tutor">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
                Verified
              </span>
            )}
            <span className="match-rating">
              {tutor.avg_rating !== null ? (
                <>&#9733; {tutor.avg_rating.toFixed(1)}</>
              ) : (
                'New'
              )}
            </span>
            <span className="match-rate">${tutor.hourly_rate_cad.toFixed(0)}/hr</span>
          </div>
          <p className="match-headline">{tutor.headline}</p>
        </div>

        <div className="match-score-pill" title={`${scorePct}% overall match`}>
          <span className="score-number">{scorePct}%</span>
          <span className="score-label">match</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="match-progress-track" role="progressbar" aria-valuenow={scorePct} aria-valuemax={100} aria-label={`Match score: ${scorePct}%`}>
        <div className="match-progress-fill" style={{ width: `${scorePct}%` }} />
      </div>

      {/* Subject coverage chips */}
      <div className="match-subjects">
        {tutor.subjects.map((s) => {
          const isCovered = match.covered_weak_subjects.some(
            (ws) => ws.toLowerCase().includes(s.toLowerCase()) || s.toLowerCase().includes(ws.toLowerCase()),
          );
          return (
            <span key={s} className={`subject-chip ${isCovered ? 'subject-chip--covered' : ''}`}>
              {isCovered && <span aria-label="covered">&#10003; </span>}
              {s}
            </span>
          );
        })}
      </div>

      {/* Explanation */}
      <p className="match-explanation">{match.explanation}</p>

      {/* Breakdown (expandable) */}
      <button
        className="breakdown-toggle"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        {expanded ? 'Hide breakdown' : 'Show score breakdown'}
      </button>

      {expanded && <MatchBreakdown match={match} />}

      {/* Actions */}
      <div className="match-card-actions">
        <Link to={`/tutors/${tutor.id}`} className="btn-outline">
          View Profile
        </Link>
        <button
          className="btn-primary"
          onClick={() => onBook(match)}
          disabled={!tutor.is_accepting_students}
        >
          {tutor.is_accepting_students ? 'Book Session' : 'Not Accepting'}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function TutorMatchPage() {
  const queryClient = useQueryClient();
  const [showPrefs, setShowPrefs] = useState(false);
  const [bookingMatch, setBookingMatch] = useState<TutorMatch | null>(null);
  const [bookingSuccess, setBookingSuccess] = useState(false);
  const [includeAi, setIncludeAi] = useState(false);

  const { data: prefsData, isLoading: prefsLoading } = useQuery({
    queryKey: ['tutorMatchPreferences'],
    queryFn: () => tutorMatchingApi.getPreferences(),
    staleTime: 300_000,
  });

  const { data: recommendations, isLoading, isError, refetch } = useQuery({
    queryKey: ['tutorMatchRecommendations', includeAi],
    queryFn: () => tutorMatchingApi.getRecommendations({ limit: 10, include_ai: includeAi }),
    staleTime: 60_000,
  });

  const prefsMutation = useMutation({
    mutationFn: (prefs: Partial<TutorMatchPreference>) => tutorMatchingApi.updatePreferences(prefs),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tutorMatchPreferences'] });
      queryClient.invalidateQueries({ queryKey: ['tutorMatchRecommendations'] });
    },
  });

  const handleBook = useCallback((match: TutorMatch) => {
    setBookingMatch(match);
    setBookingSuccess(false);
  }, []);

  const handleBookingSuccess = useCallback(() => {
    setBookingSuccess(true);
    queryClient.invalidateQueries({ queryKey: ['myBookings'] });
  }, [queryClient]);

  const matches = recommendations?.matches ?? [];
  const totalWeak = matches[0]?.total_weak_subjects ?? 0;
  const coveredSubjects = matches[0]?.covered_weak_subjects ?? [];

  return (
    <DashboardLayout welcomeSubtitle="AI-powered tutor matching based on your learning profile">
      <div className="tutor-match-page">
        {/* Header */}
        <div className="match-page-header">
          <div className="match-page-title">
            <h1>AI Tutor Match</h1>
            {!isLoading && !isError && totalWeak > 0 && (
              <p className="match-page-subtitle">
                Based on your learning profile and {totalWeak} weak area{totalWeak !== 1 ? 's' : ''}, we found these top matches:
              </p>
            )}
            {!isLoading && !isError && totalWeak === 0 && (
              <p className="match-page-subtitle">
                Here are the best available tutors for you:
              </p>
            )}
          </div>
          <div className="match-page-actions">
            <label className="ai-toggle-label">
              <input
                type="checkbox"
                checked={includeAi}
                onChange={(e) => setIncludeAi(e.target.checked)}
              />
              AI explanations
            </label>
            <button
              className="btn-outline"
              onClick={() => setShowPrefs(true)}
              disabled={prefsLoading}
            >
              Set Preferences
            </button>
            <button className="btn-secondary" onClick={() => refetch()} disabled={isLoading}>
              {isLoading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </div>

        {/* Booking success banner */}
        {bookingSuccess && (
          <div className="booking-success-banner">
            Booking request sent! The tutor will review and respond shortly.
            <button
              className="banner-dismiss"
              onClick={() => setBookingSuccess(false)}
              aria-label="Dismiss"
            >
              &times;
            </button>
          </div>
        )}

        {/* Covered subjects summary */}
        {coveredSubjects.length > 0 && (
          <div className="covered-summary">
            <strong>Top match covers:</strong>{' '}
            {coveredSubjects.map((s) => (
              <span key={s} className="subject-chip subject-chip--covered">&#10003; {s}</span>
            ))}
          </div>
        )}

        {/* Loading */}
        {isLoading && (
          <div className="match-loading">
            <div className="loading-spinner" aria-label="Finding matches" />
            <p>Analysing your learning profile and finding the best matches...</p>
          </div>
        )}

        {/* Error */}
        {isError && (
          <div className="match-error">
            <p>Failed to load recommendations. Please try again.</p>
            <button className="btn-primary" onClick={() => refetch()}>Retry</button>
          </div>
        )}

        {/* Empty */}
        {!isLoading && !isError && matches.length === 0 && (
          <div className="match-empty">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <h3>No tutors found</h3>
            <p>Try adjusting your preferences or check back soon as new tutors join.</p>
            <button className="btn-primary" onClick={() => setShowPrefs(true)}>
              Adjust Preferences
            </button>
          </div>
        )}

        {/* Match cards */}
        {!isLoading && !isError && matches.length > 0 && (
          <div className="match-list">
            {matches.map((match, idx) => (
              <MatchCard
                key={match.tutor_id}
                match={match}
                rank={idx + 1}
                onBook={handleBook}
              />
            ))}
          </div>
        )}

        <div className="match-page-footer">
          <Link to="/tutors" className="btn-outline">
            Browse All Tutors
          </Link>
        </div>
      </div>

      {/* Modals */}
      {showPrefs && prefsData && (
        <PreferencesModal
          current={prefsData}
          onClose={() => setShowPrefs(false)}
          onSave={(prefs) => prefsMutation.mutate(prefs)}
        />
      )}

      {bookingMatch && (
        <BookingModal
          tutorId={bookingMatch.tutor_id}
          tutorName={bookingMatch.tutor.tutor_name}
          onClose={() => setBookingMatch(null)}
          onSuccess={handleBookingSuccess}
        />
      )}
    </DashboardLayout>
  );
}
