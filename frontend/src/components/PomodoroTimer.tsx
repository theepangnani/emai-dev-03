import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../api/client';
import './PomodoroTimer.css';

interface Course {
  id: number;
  name: string;
  subject?: string;
}

interface SessionResult {
  id: number;
  completed: boolean;
  ai_recap: string | null;
  xp_awarded: number | null;
  duration_seconds: number;
}

interface PomodoroTimerProps {
  courses: Course[];
  onSessionComplete?: () => void;
}

type TimerState = 'setup' | 'running' | 'paused' | 'done';

const TARGET_DURATION = 1500; // 25 min
const RING_RADIUS = 108;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

export function PomodoroTimer({ courses, onSessionComplete }: PomodoroTimerProps) {
  const [timerState, setTimerState] = useState<TimerState>('setup');
  const [secondsLeft, setSecondsLeft] = useState(TARGET_DURATION);
  const [elapsed, setElapsed] = useState(0);
  const [courseId, setCourseId] = useState<number | undefined>(undefined);
  const [subject, setSubject] = useState('');
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [result, setResult] = useState<SessionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  // Timer tick
  useEffect(() => {
    if (timerState === 'running') {
      intervalRef.current = setInterval(() => {
        setSecondsLeft((prev) => {
          if (prev <= 1) {
            // Timer finished
            if (intervalRef.current) clearInterval(intervalRef.current);
            setTimerState('done');
            return 0;
          }
          return prev - 1;
        });
        setElapsed((prev) => prev + 1);
      }, 1000);
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [timerState]);

  // Auto-complete when timer reaches 0
  useEffect(() => {
    if (timerState === 'done' && sessionId && !result) {
      handleComplete();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timerState]);

  // Play a short beep when done
  useEffect(() => {
    if (timerState === 'done') {
      try {
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = 800;
        gain.gain.value = 0.3;
        osc.start();
        osc.stop(ctx.currentTime + 0.3);
      } catch {
        // Audio not available — ignore
      }
    }
  }, [timerState]);

  const handleStart = useCallback(async () => {
    setError(null);
    try {
      const resp = await api.post('/api/study-sessions/start', {
        course_id: courseId || null,
        subject: subject.trim() || null,
        target_duration: TARGET_DURATION,
      });
      setSessionId(resp.data.id);
      setTimerState('running');
    } catch {
      setError('Failed to start session');
    }
  }, [courseId, subject]);

  const handlePause = () => setTimerState('paused');
  const handleResume = () => setTimerState('running');

  const handleComplete = useCallback(async () => {
    if (!sessionId) return;
    setError(null);
    try {
      const resp = await api.post(`/api/study-sessions/${sessionId}/complete`, {
        duration_seconds: elapsed,
      });
      setResult(resp.data);
      setTimerState('done');
      onSessionComplete?.();
    } catch {
      setError('Failed to save session');
    }
  }, [sessionId, elapsed, onSessionComplete]);

  const handleReset = () => {
    setTimerState('setup');
    setSecondsLeft(TARGET_DURATION);
    setElapsed(0);
    setSessionId(null);
    setResult(null);
    setError(null);
  };

  const handleStopEarly = async () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setTimerState('done');
    if (sessionId) {
      try {
        const resp = await api.post(`/api/study-sessions/${sessionId}/complete`, {
          duration_seconds: elapsed,
        });
        setResult(resp.data);
        onSessionComplete?.();
      } catch {
        setError('Failed to save session');
      }
    }
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
  };

  const progress = elapsed / TARGET_DURATION;
  const strokeDashoffset = RING_CIRCUMFERENCE * (1 - Math.min(progress, 1));

  // Auto-fill subject from selected course
  const handleCourseChange = (id: string) => {
    const numId = id ? parseInt(id, 10) : undefined;
    setCourseId(numId);
    if (numId) {
      const course = courses.find((c) => c.id === numId);
      if (course?.subject && !subject) {
        setSubject(course.subject);
      }
    }
  };

  return (
    <div className="pomodoro-container">
      {timerState === 'setup' && (
        <div className="pomodoro-setup">
          <label>
            Class (optional)
            <select
              value={courseId ?? ''}
              onChange={(e) => handleCourseChange(e.target.value)}
            >
              <option value="">-- Select --</option>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Subject / Topic
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Math Chapter 5"
              maxLength={100}
            />
          </label>
          <button className="pomodoro-btn pomodoro-btn--primary" onClick={handleStart}>
            Start Study Session
          </button>
        </div>
      )}

      {timerState !== 'setup' && (
        <>
          <div className="pomodoro-timer-ring">
            <svg viewBox="0 0 240 240">
              <circle className="pomodoro-ring-bg" cx="120" cy="120" r={RING_RADIUS} />
              <circle
                className="pomodoro-ring-progress"
                cx="120"
                cy="120"
                r={RING_RADIUS}
                strokeDasharray={RING_CIRCUMFERENCE}
                strokeDashoffset={strokeDashoffset}
              />
            </svg>
            <div className="pomodoro-time-display">
              <div className="pomodoro-time">{formatTime(secondsLeft)}</div>
              <div className="pomodoro-label">
                {subject || 'Study Session'}
              </div>
            </div>
          </div>

          <div className="pomodoro-controls">
            {timerState === 'running' && (
              <>
                <button className="pomodoro-btn pomodoro-btn--secondary" onClick={handlePause}>
                  Pause
                </button>
                <button className="pomodoro-btn pomodoro-btn--secondary" onClick={handleStopEarly}>
                  Stop
                </button>
              </>
            )}
            {timerState === 'paused' && (
              <>
                <button className="pomodoro-btn pomodoro-btn--primary" onClick={handleResume}>
                  Resume
                </button>
                <button className="pomodoro-btn pomodoro-btn--secondary" onClick={handleStopEarly}>
                  Stop
                </button>
              </>
            )}
            {timerState === 'done' && (
              <button className="pomodoro-btn pomodoro-btn--primary" onClick={handleReset}>
                New Session
              </button>
            )}
          </div>

          {/* Recap card */}
          {result && (
            <div className="pomodoro-recap">
              <h4>Session Complete</h4>
              {result.ai_recap ? (
                <div className="pomodoro-recap-text">{result.ai_recap}</div>
              ) : result.completed ? (
                <div className="pomodoro-recap-text">Great job completing your study session!</div>
              ) : (
                <div className="pomodoro-no-xp">
                  Study for at least 20 minutes to earn XP and get an AI recap.
                </div>
              )}
              {result.xp_awarded ? (
                <span className="pomodoro-xp-badge">+{result.xp_awarded} XP</span>
              ) : null}
            </div>
          )}
        </>
      )}

      {error && <p style={{ color: 'var(--color-error, #ef4444)' }}>{error}</p>}
    </div>
  );
}
