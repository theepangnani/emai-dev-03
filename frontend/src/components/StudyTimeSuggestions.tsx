import { useState, useEffect } from 'react';
import { api } from '../api/client';
import './StudyTimeSuggestions.css';

interface StudyTimeSlot {
  day_of_week: string;
  time_of_day: string;
  period: string;
  score: number;
  label: string;
}

interface DailyStudyMinutes {
  day: string;
  date: string;
  minutes: number;
}

interface StudySuggestionsData {
  top_slots: StudyTimeSlot[];
  weekly_chart: DailyStudyMinutes[];
  current_week_minutes: number;
  previous_week_minutes: number;
  weekly_trend: string;
  next_suggested_session: string | null;
}

const PERIOD_ICONS: Record<string, string> = {
  morning: '\u2600\uFE0F',
  afternoon: '\u{1F324}\uFE0F',
  evening: '\u{1F319}',
};

interface Props {
  /** For parent view: pass the student_id (students table PK) */
  studentId?: number;
}

export function StudyTimeSuggestions({ studentId }: Props) {
  const [data, setData] = useState<StudySuggestionsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      const v = localStorage.getItem('study-suggestions-collapsed');
      return v !== null ? v === '1' : false;
    } catch {
      return false;
    }
  });

  useEffect(() => {
    let ignore = false;
    const url = studentId
      ? `/api/students/${studentId}/study-suggestions`
      : '/api/students/me/study-suggestions';

    api.get(url)
      .then(resp => {
        if (!ignore) setData(resp.data);
      })
      .catch(() => {
        // Silently fail -- widget is non-critical
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });

    return () => { ignore = true; };
  }, [studentId]);

  const toggleCollapsed = () => {
    setCollapsed(prev => {
      const next = !prev;
      try { localStorage.setItem('study-suggestions-collapsed', next ? '1' : '0'); } catch { /* ignore */ }
      return next;
    });
  };

  if (loading) return null;
  if (!data) return null;

  const maxMinutes = Math.max(...data.weekly_chart.map(d => d.minutes), 1);

  const trendIcon = data.weekly_trend === 'up' ? '\u2191' : data.weekly_trend === 'down' ? '\u2193' : '\u2192';
  const trendClass = data.weekly_trend === 'up' ? 'trend-up' : data.weekly_trend === 'down' ? 'trend-down' : 'trend-steady';

  return (
    <section className="sts-widget">
      <div
        className="sts-header"
        onClick={toggleCollapsed}
        role="button"
        tabIndex={0}
        aria-expanded={!collapsed}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleCollapsed(); } }}
      >
        <h3 className="sts-title">
          <span className="sts-title-icon" aria-hidden="true">&#128337;</span>
          Best Study Times
        </h3>
        <svg
          className={`sts-chevron${collapsed ? ' sts-chevron--collapsed' : ''}`}
          width="16" height="16" viewBox="0 0 24 24"
          fill="none" stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      <div className={`sts-body${collapsed ? ' sts-body--collapsed' : ''}`}>
        {/* Top 3 recommended time slots */}
        {data.top_slots.length > 0 ? (
          <div className="sts-slots">
            {data.top_slots.map((slot, i) => (
              <div key={i} className={`sts-slot sts-slot--${slot.period}`}>
                <span className="sts-slot-icon" aria-hidden="true">
                  {PERIOD_ICONS[slot.period] || '\u{1F4DA}'}
                </span>
                <div className="sts-slot-info">
                  <span className="sts-slot-time">{slot.day_of_week} {slot.time_of_day}</span>
                  <div className="sts-slot-bar-track">
                    <div
                      className="sts-slot-bar-fill"
                      style={{ width: `${slot.score}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="sts-empty">Start studying to see your best times here.</p>
        )}

        {/* Next suggested session */}
        {data.next_suggested_session && (
          <div className="sts-next">
            <span className="sts-next-label">Next recommended session:</span>
            <span className="sts-next-time">{data.next_suggested_session}</span>
          </div>
        )}

        {/* 7-day bar chart */}
        <div className="sts-chart">
          <div className="sts-chart-label">
            <span>Your study pattern (last 7 days)</span>
            <span className={`sts-trend ${trendClass}`}>
              {trendIcon} {data.current_week_minutes} min this week
            </span>
          </div>
          <div className="sts-bars">
            {data.weekly_chart.map((day, i) => (
              <div key={i} className="sts-bar-col">
                <div className="sts-bar-track">
                  <div
                    className="sts-bar"
                    style={{ height: `${maxMinutes > 0 ? (day.minutes / maxMinutes) * 100 : 0}%` }}
                    title={`${day.minutes} min`}
                  />
                </div>
                <span className="sts-bar-label">{day.day}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
