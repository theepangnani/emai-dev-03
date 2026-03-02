import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import { studyTimerApi, type SessionType, type StudyStatsResponse } from '../api/studyTimer';
import './StudyTimerPage.css';

// ─── Timer configuration ───────────────────────────────────────────────────

const SESSION_DURATIONS: Record<SessionType, number> = {
  work: 25 * 60,        // 25 minutes in seconds
  short_break: 5 * 60,  // 5 minutes
  long_break: 15 * 60,  // 15 minutes
};

const SESSION_LABELS: Record<SessionType, string> = {
  work: 'Focus',
  short_break: 'Short Break',
  long_break: 'Long Break',
};

const DAY_ABBREV = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

// ─── Web Audio beep ───────────────────────────────────────────────────────

function playCompletionBeep() {
  try {
    const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    const oscillator = ctx.createOscillator();
    const gainNode = ctx.createGain();
    oscillator.connect(gainNode);
    gainNode.connect(ctx.destination);
    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(880, ctx.currentTime);
    oscillator.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.3);
    gainNode.gain.setValueAtTime(0.4, ctx.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6);
    oscillator.start(ctx.currentTime);
    oscillator.stop(ctx.currentTime + 0.6);
  } catch {
    // Silently ignore if Web Audio API is unavailable
  }
}

// ─── SVG Circular timer ────────────────────────────────────────────────────

const RADIUS = 110;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function CircularTimer({
  secondsLeft,
  totalSeconds,
  mode,
}: {
  secondsLeft: number;
  totalSeconds: number;
  mode: SessionType;
}) {
  const progress = totalSeconds > 0 ? secondsLeft / totalSeconds : 1;
  const dashOffset = CIRCUMFERENCE * (1 - progress);

  const minutes = Math.floor(secondsLeft / 60);
  const secs = secondsLeft % 60;
  const timeStr = `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;

  const svgSize = (RADIUS + 14) * 2;

  return (
    <div className="timer-circle-container">
      <svg
        className="timer-svg"
        width={svgSize}
        height={svgSize}
        viewBox={`0 0 ${svgSize} ${svgSize}`}
        aria-label={`Timer: ${timeStr}`}
      >
        <circle
          className="timer-track"
          cx={svgSize / 2}
          cy={svgSize / 2}
          r={RADIUS}
          strokeWidth={14}
        />
        <circle
          className={`timer-progress${mode !== 'work' ? ' break-mode' : ''}`}
          cx={svgSize / 2}
          cy={svgSize / 2}
          r={RADIUS}
          strokeWidth={14}
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={dashOffset}
        />
      </svg>
      <div className="timer-center-text">
        <span className="timer-time-display">{timeStr}</span>
        <span className="timer-label">{SESSION_LABELS[mode]}</span>
      </div>
    </div>
  );
}

// ─── 7-day bar chart ───────────────────────────────────────────────────────

function BarChart({ data }: { data: StudyStatsResponse['sessions_by_day'] }) {
  const maxMinutes = Math.max(...data.map((d) => d.minutes), 1);
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className="timer-chart-section">
      <div className="timer-chart-title">7-Day Focus (minutes)</div>
      <div className="timer-bar-chart" role="img" aria-label="7-day focus chart">
        {data.map((day) => {
          const heightPct = (day.minutes / maxMinutes) * 100;
          const d = new Date(day.date + 'T00:00:00');
          const dayLabel = DAY_ABBREV[d.getDay()];
          const isToday = day.date === today;
          return (
            <div key={day.date} className="timer-bar-col" title={`${day.date}: ${day.minutes} min`}>
              <div
                className={`timer-bar${isToday ? ' today-bar' : ''}`}
                style={{ height: `${Math.max(heightPct, day.minutes > 0 ? 4 : 2)}%` }}
              />
              <span className="timer-bar-day">{dayLabel}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Main page component ───────────────────────────────────────────────────

export function StudyTimerPage() {
  const queryClient = useQueryClient();

  // Timer state
  const [mode, setMode] = useState<SessionType>('work');
  const [secondsLeft, setSecondsLeft] = useState(SESSION_DURATIONS.work);
  const [isRunning, setIsRunning] = useState(false);
  const [sessionComplete, setSessionComplete] = useState(false);
  const [selectedCourseId, setSelectedCourseId] = useState<number | undefined>();
  const [currentSessionId, setCurrentSessionId] = useState<number | null>(null);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch stats and courses
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['study-timer-stats'],
    queryFn: studyTimerApi.getStats,
  });

  const { data: streak } = useQuery({
    queryKey: ['study-timer-streak'],
    queryFn: studyTimerApi.getStreak,
  });

  // Fetch courses from the API (reuse existing courses list)
  const { data: coursesData } = useQuery({
    queryKey: ['courses-list-simple'],
    queryFn: async () => {
      const { api } = await import('../api/client');
      const res = await api.get<Array<{ id: number; name: string }>>('/api/courses');
      return res.data;
    },
  });

  // Mutations
  const startMutation = useMutation({
    mutationFn: () => studyTimerApi.startSession(mode, selectedCourseId),
    onSuccess: (session) => {
      setCurrentSessionId(session.id);
    },
  });

  const endMutation = useMutation({
    mutationFn: (sessionId: number) => studyTimerApi.endSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['study-timer-stats'] });
      queryClient.invalidateQueries({ queryKey: ['study-timer-streak'] });
    },
  });

  // ── Timer tick ─────────────────────────────────────────────────────────

  const handleSessionComplete = useCallback(async () => {
    setIsRunning(false);
    setSessionComplete(true);
    playCompletionBeep();

    if (currentSessionId !== null) {
      try {
        await endMutation.mutateAsync(currentSessionId);
      } catch {
        // Silently ignore network errors — session will expire naturally
      }
      setCurrentSessionId(null);
    }
  }, [currentSessionId, endMutation]);

  useEffect(() => {
    if (isRunning) {
      intervalRef.current = setInterval(() => {
        setSecondsLeft((prev) => {
          if (prev <= 1) {
            clearInterval(intervalRef.current!);
            handleSessionComplete();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isRunning, handleSessionComplete]);

  // ── Mode switch ────────────────────────────────────────────────────────

  const switchMode = (newMode: SessionType) => {
    if (isRunning) return; // Don't switch while running
    setMode(newMode);
    setSecondsLeft(SESSION_DURATIONS[newMode]);
    setSessionComplete(false);
    setCurrentSessionId(null);
  };

  // ── Start / Pause ──────────────────────────────────────────────────────

  const handleStart = async () => {
    if (!isRunning && secondsLeft === SESSION_DURATIONS[mode]) {
      // Fresh start — log session to backend
      try {
        await startMutation.mutateAsync();
      } catch {
        // Continue running even if backend call fails
      }
    }
    setSessionComplete(false);
    setIsRunning(true);
  };

  const handlePause = () => {
    setIsRunning(false);
  };

  // ── Reset ──────────────────────────────────────────────────────────────

  const handleReset = () => {
    setIsRunning(false);
    setSecondsLeft(SESSION_DURATIONS[mode]);
    setSessionComplete(false);
    setCurrentSessionId(null);
  };

  // ── Render ─────────────────────────────────────────────────────────────

  const totalSeconds = SESSION_DURATIONS[mode];

  return (
    <DashboardLayout welcomeSubtitle="Stay focused with the Pomodoro technique">
      <div className="study-timer-page">

        {/* Mode tabs */}
        <div className="timer-mode-tabs" role="tablist" aria-label="Timer mode">
          {(['work', 'short_break', 'long_break'] as SessionType[]).map((m) => (
            <button
              key={m}
              role="tab"
              aria-selected={mode === m}
              className={`timer-mode-tab${mode === m ? ' active' : ''}`}
              onClick={() => switchMode(m)}
              disabled={isRunning}
            >
              {SESSION_LABELS[m]}
            </button>
          ))}
        </div>

        {/* Circular countdown */}
        <div className="timer-circle-wrapper">
          <CircularTimer secondsLeft={secondsLeft} totalSeconds={totalSeconds} mode={mode} />
        </div>

        {/* Session complete banner */}
        {sessionComplete && (
          <div className="timer-complete-banner" role="status">
            {mode === 'work'
              ? 'Great work! Session complete. Take a break!'
              : 'Break over — ready to focus?'}
          </div>
        )}

        {/* Controls */}
        <div className="timer-controls">
          {isRunning ? (
            <button className="timer-btn timer-btn-primary" onClick={handlePause}>
              Pause
            </button>
          ) : (
            <button
              className="timer-btn timer-btn-primary"
              onClick={handleStart}
              disabled={startMutation.isPending}
            >
              {secondsLeft === SESSION_DURATIONS[mode] ? 'Start' : 'Resume'}
            </button>
          )}
          <button className="timer-btn timer-btn-secondary" onClick={handleReset} disabled={isRunning}>
            Reset
          </button>
        </div>

        {/* Course selector */}
        {mode === 'work' && (
          <div className="timer-course-selector">
            <label htmlFor="timer-course">What are you studying?</label>
            <select
              id="timer-course"
              className="timer-course-select"
              value={selectedCourseId ?? ''}
              onChange={(e) =>
                setSelectedCourseId(e.target.value ? Number(e.target.value) : undefined)
              }
              disabled={isRunning}
            >
              <option value="">— Select a course (optional) —</option>
              {coursesData?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Streak card */}
        <div className="timer-streak-card" aria-label="Study streak">
          <div className="timer-streak-flame" aria-hidden="true">🔥</div>
          <div className="timer-streak-info">
            <div className="timer-streak-current">
              {streak?.current_streak ?? 0} day{(streak?.current_streak ?? 0) !== 1 ? 's' : ''}
            </div>
            <div className="timer-streak-label">Current Streak</div>
            <div className="timer-streak-best">
              Best: {streak?.longest_streak ?? 0} day{(streak?.longest_streak ?? 0) !== 1 ? 's' : ''}
            </div>
          </div>
        </div>

        {/* Stats panel */}
        {statsLoading ? (
          <div className="timer-loading">Loading stats...</div>
        ) : stats ? (
          <div className="timer-stats-panel">
            <div className="timer-stats-grid">
              <div className="timer-stat-card">
                <div className="timer-stat-value">{stats.today_minutes}</div>
                <div className="timer-stat-label">Today (min)</div>
              </div>
              <div className="timer-stat-card">
                <div className="timer-stat-value">{stats.week_minutes}</div>
                <div className="timer-stat-label">This Week</div>
              </div>
              <div className="timer-stat-card">
                <div className="timer-stat-value">{stats.total_sessions}</div>
                <div className="timer-stat-label">All Sessions</div>
              </div>
            </div>

            {/* 7-day bar chart */}
            <BarChart data={stats.sessions_by_day} />
          </div>
        ) : null}

      </div>
    </DashboardLayout>
  );
}

export default StudyTimerPage;
