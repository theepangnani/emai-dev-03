import { useState, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import { useAuth } from '../context/AuthContext';
import {
  wellnessApi,
  type MoodLevel,
  type EnergyLevel,
  type WellnessCheckInCreate,
  type WellnessTrendResponse,
  type DayTrendPoint,
  type WellnessSummary,
} from '../api/wellness';
import './WellnessPage.css';

// ── Constants ────────────────────────────────────────────────────────────────

const MOOD_OPTIONS: { value: MoodLevel; emoji: string; label: string }[] = [
  { value: 'great',      emoji: '😊', label: 'Great' },
  { value: 'good',       emoji: '🙂', label: 'Good' },
  { value: 'okay',       emoji: '😐', label: 'Okay' },
  { value: 'struggling', emoji: '😔', label: 'Struggling' },
  { value: 'overwhelmed',emoji: '😰', label: 'Overwhelmed' },
];

const ENERGY_OPTIONS: { value: EnergyLevel; label: string }[] = [
  { value: 'high',   label: 'High Energy' },
  { value: 'medium', label: 'Medium' },
  { value: 'low',    label: 'Low Energy' },
];

const DAY_ABBR = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function moodEmoji(mood: MoodLevel | null): string {
  if (!mood) return '';
  return MOOD_OPTIONS.find(m => m.value === mood)?.emoji ?? '';
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return DAY_ABBR[d.getDay()];
}

// ── Trend Chart (pure CSS) ────────────────────────────────────────────────────

function TrendChart({ trend }: { trend: WellnessTrendResponse }) {
  return (
    <div>
      <div className="trend-timeline">
        {trend.days.map((day: DayTrendPoint) => (
          <div key={day.date} className="trend-day">
            <span className="trend-day__label">{formatDate(day.date)}</span>
            <div
              className={`trend-day__dot ${
                day.has_entry
                  ? `trend-day__dot--${day.mood}`
                  : 'trend-day__dot--empty'
              }`}
              title={day.has_entry ? `Mood: ${day.mood}, Stress: ${day.stress_level}` : 'No entry'}
            >
              {day.has_entry ? moodEmoji(day.mood) : '·'}
            </div>
            {day.has_entry && day.stress_level != null && (
              <div className="trend-day__stress-bar">
                <div
                  className="trend-day__stress-fill"
                  style={{ width: `${(day.stress_level / 5) * 100}%` }}
                />
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="wellness-stats-row">
        <div className="wellness-stat-tile">
          <div className="wellness-stat-tile__val">
            {trend.avg_stress != null ? trend.avg_stress.toFixed(1) : '—'}
          </div>
          <div className="wellness-stat-tile__label">Avg Stress</div>
        </div>
        <div className="wellness-stat-tile">
          <div className="wellness-stat-tile__val">
            {trend.avg_sleep != null ? `${trend.avg_sleep.toFixed(1)}h` : '—'}
          </div>
          <div className="wellness-stat-tile__label">Avg Sleep</div>
        </div>
        <div className="wellness-stat-tile">
          <div className="wellness-stat-tile__val">{trend.streak_days}</div>
          <div className="wellness-stat-tile__label">Streak Days</div>
        </div>
      </div>
    </div>
  );
}

// ── Student view ──────────────────────────────────────────────────────────────

function StudentWellnessView() {
  const qc = useQueryClient();

  const [mood, setMood] = useState<MoodLevel | null>(null);
  const [energy, setEnergy] = useState<EnergyLevel | null>(null);
  const [stress, setStress] = useState<number>(3);
  const [sleepHours, setSleepHours] = useState<string>('');
  const [notes, setNotes] = useState<string>('');
  const [isPrivate, setIsPrivate] = useState<boolean>(false);
  const [submitted, setSubmitted] = useState<boolean>(false);

  const { data: todayEntry, isLoading: loadingToday } = useQuery({
    queryKey: ['wellness-today'],
    queryFn: wellnessApi.getToday,
  });

  const { data: trend, isLoading: loadingTrend } = useQuery({
    queryKey: ['wellness-trend', 7],
    queryFn: () => wellnessApi.getTrend(7),
  });

  // Pre-populate form if today's entry already exists
  useEffect(() => {
    if (todayEntry) {
      setMood(todayEntry.mood);
      setEnergy(todayEntry.energy);
      setStress(todayEntry.stress_level);
      setSleepHours(todayEntry.sleep_hours != null ? String(todayEntry.sleep_hours) : '');
      setNotes(todayEntry.notes ?? '');
      setIsPrivate(todayEntry.is_private);
    }
  }, [todayEntry]);

  const mutation = useMutation({
    mutationFn: (data: WellnessCheckInCreate) => wellnessApi.submitCheckIn(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['wellness-today'] });
      qc.invalidateQueries({ queryKey: ['wellness-trend'] });
      setSubmitted(true);
      setTimeout(() => setSubmitted(false), 3000);
    },
  });

  const handleSubmit = useCallback(() => {
    if (!mood || !energy) return;
    const payload: WellnessCheckInCreate = {
      mood,
      energy,
      stress_level: stress,
      sleep_hours: sleepHours !== '' ? parseFloat(sleepHours) : null,
      notes: notes.trim() || null,
      is_private: isPrivate,
    };
    mutation.mutate(payload);
  }, [mood, energy, stress, sleepHours, notes, isPrivate, mutation]);

  return (
    <>
      {/* Check-in form */}
      <div className="wellness-card">
        <h2 className="wellness-card__heading">How are you feeling today?</h2>

        {submitted ? (
          <div className="wellness-confirm">
            <div className="wellness-confirm__icon">✅</div>
            <div className="wellness-confirm__msg">Check-in saved!</div>
          </div>
        ) : (
          <>
            {/* Mood */}
            <p className="wellness-section-label">Mood</p>
            <div className="mood-selector">
              {MOOD_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  className={`mood-btn${mood === opt.value ? ' mood-btn--selected' : ''}`}
                  data-mood={opt.value}
                  onClick={() => setMood(opt.value)}
                  type="button"
                  aria-pressed={mood === opt.value}
                >
                  <span className="mood-btn__emoji">{opt.emoji}</span>
                  {opt.label}
                </button>
              ))}
            </div>

            {/* Energy */}
            <p className="wellness-section-label" style={{ marginTop: '1.1rem' }}>Energy Level</p>
            <div className="energy-selector">
              {ENERGY_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  className={`energy-btn${energy === opt.value ? ' energy-btn--selected' : ''}`}
                  data-energy={opt.value}
                  onClick={() => setEnergy(opt.value)}
                  type="button"
                  aria-pressed={energy === opt.value}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {/* Stress */}
            <p className="wellness-section-label" style={{ marginTop: '1.1rem' }}>
              Stress Level &nbsp;
              <span className="stress-value-badge">{stress}</span>
            </p>
            <div className="stress-slider-row">
              <div className="stress-slider-labels">
                <span>Calm</span>
                <span>Very Stressed</span>
              </div>
              <input
                type="range"
                min={1}
                max={5}
                step={1}
                value={stress}
                onChange={(e) => setStress(Number(e.target.value))}
                className="stress-slider"
                aria-label="Stress level"
              />
            </div>

            {/* Optional fields */}
            <div className="wellness-optional-grid" style={{ marginTop: '1.1rem' }}>
              <div className="wellness-field">
                <label htmlFor="wl-sleep">Sleep Hours (optional)</label>
                <input
                  id="wl-sleep"
                  type="number"
                  min={0}
                  max={24}
                  step={0.5}
                  value={sleepHours}
                  onChange={(e) => setSleepHours(e.target.value)}
                  placeholder="e.g. 7.5"
                />
              </div>
              <div className="wellness-field">
                <label htmlFor="wl-notes">Notes (optional)</label>
                <textarea
                  id="wl-notes"
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Anything on your mind..."
                  maxLength={1000}
                />
              </div>
            </div>

            {/* Private toggle */}
            <div className="private-toggle-row" style={{ marginTop: '0.9rem' }}>
              <input
                type="checkbox"
                id="wl-private"
                checked={isPrivate}
                onChange={(e) => setIsPrivate(e.target.checked)}
              />
              <label htmlFor="wl-private">
                Keep private (parents won't see this entry)
              </label>
            </div>

            <button
              className="wellness-submit-btn"
              onClick={handleSubmit}
              disabled={!mood || !energy || mutation.isPending}
              type="button"
            >
              {mutation.isPending
                ? 'Saving...'
                : todayEntry
                  ? 'Update Today\'s Check-in'
                  : 'Submit Check-in'}
            </button>

            {mutation.isError && (
              <p style={{ color: '#ef4444', marginTop: '0.5rem', fontSize: '0.85rem' }}>
                Something went wrong. Please try again.
              </p>
            )}
          </>
        )}
      </div>

      {/* 7-day trend */}
      <div className="wellness-card">
        <h2 className="wellness-card__heading">Your 7-Day Trend</h2>
        {loadingTrend ? (
          <div className="wellness-loading">Loading trend...</div>
        ) : trend ? (
          <TrendChart trend={trend} />
        ) : (
          <div className="wellness-empty">No data yet. Start checking in daily!</div>
        )}
      </div>
    </>
  );
}

// ── Parent view ───────────────────────────────────────────────────────────────

interface LinkedChild {
  id: number;
  name: string;
}

function ParentWellnessView() {
  const { user } = useAuth();
  const [selectedChildId, setSelectedChildId] = useState<number | null>(null);
  const [children, setChildren] = useState<LinkedChild[]>([]);
  const [loadingChildren, setLoadingChildren] = useState(true);

  // Fetch linked children via the existing my-kids endpoint
  useEffect(() => {
    import('../api/client').then(({ api }) => {
      api.get<{ students: { user_id: number; name: string }[] }>('/api/parent/students')
        .then((res) => {
          const kids: LinkedChild[] = (res.data.students || []).map((s) => ({
            id: s.user_id,
            name: s.name,
          }));
          setChildren(kids);
          if (kids.length > 0) setSelectedChildId(kids[0].id);
        })
        .catch(() => setChildren([]))
        .finally(() => setLoadingChildren(false));
    });
  }, [user]);

  const { data: childTrend, isLoading: loadingTrend } = useQuery({
    queryKey: ['wellness-child-trend', selectedChildId],
    queryFn: () => wellnessApi.getChildTrend(selectedChildId!, 7),
    enabled: selectedChildId != null,
  });

  const { data: childSummary } = useQuery<WellnessSummary>({
    queryKey: ['wellness-child-summary', selectedChildId],
    queryFn: () => wellnessApi.getStudentSummary(selectedChildId!),
    enabled: selectedChildId != null,
  });

  if (loadingChildren) {
    return <div className="wellness-loading">Loading children...</div>;
  }

  if (children.length === 0) {
    return (
      <div className="wellness-card">
        <div className="wellness-empty">
          No linked children found. Link a child to your account to view their wellness.
        </div>
      </div>
    );
  }

  return (
    <>
      {childSummary?.alert_active && (
        <div className="wellness-alert-banner">
          <span className="wellness-alert-banner__icon">⚠️</span>
          <span>
            Your child has had multiple days of low mood recently. Consider checking in with them.
          </span>
        </div>
      )}

      <div className="wellness-card">
        <h2 className="wellness-card__heading">Child Wellness Overview</h2>

        <div className="child-selector-row">
          <label htmlFor="child-select">Viewing:</label>
          <select
            id="child-select"
            value={selectedChildId ?? ''}
            onChange={(e) => setSelectedChildId(Number(e.target.value))}
          >
            {children.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>

        {childSummary && (
          <div className="wellness-stats-row" style={{ marginBottom: '1.25rem' }}>
            <div className="wellness-stat-tile">
              <div className="wellness-stat-tile__val">
                {childSummary.dominant_mood
                  ? moodEmoji(childSummary.dominant_mood)
                  : '—'}
              </div>
              <div className="wellness-stat-tile__label">Dominant Mood</div>
            </div>
            <div className="wellness-stat-tile">
              <div className="wellness-stat-tile__val">
                {childSummary.week_avg_stress != null
                  ? childSummary.week_avg_stress.toFixed(1)
                  : '—'}
              </div>
              <div className="wellness-stat-tile__label">Avg Stress</div>
            </div>
            <div className="wellness-stat-tile">
              <div className="wellness-stat-tile__val">
                {childSummary.total_check_ins_this_week}
              </div>
              <div className="wellness-stat-tile__label">Check-ins This Week</div>
            </div>
          </div>
        )}

        {loadingTrend ? (
          <div className="wellness-loading">Loading trend...</div>
        ) : childTrend ? (
          <TrendChart trend={childTrend} />
        ) : (
          <div className="wellness-empty">No check-in data available for this child.</div>
        )}
      </div>
    </>
  );
}

// ── Page entry-point ──────────────────────────────────────────────────────────

export function WellnessPage() {
  const { user } = useAuth();
  const isParent = user?.role === 'parent';

  return (
    <DashboardLayout welcomeSubtitle="Daily wellness check-in">
      <div className="wellness-page">
        <h1 className="wellness-page__title">Wellness</h1>
        <p className="wellness-page__subtitle">
          {isParent
            ? 'Monitor your child\'s daily wellbeing.'
            : 'Track your mood, energy, and stress each day.'}
        </p>

        {isParent ? <ParentWellnessView /> : <StudentWellnessView />}
      </div>
    </DashboardLayout>
  );
}

export default WellnessPage;
