import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { PomodoroTimer } from '../components/PomodoroTimer';
import './StudySessionPage.css';

interface Course {
  id: number;
  name: string;
  subject?: string;
}

interface StudySessionItem {
  id: number;
  subject: string | null;
  duration_seconds: number;
  completed: boolean;
  ai_recap: string | null;
  xp_awarded: number | null;
  created_at: string;
}

interface Stats {
  total_sessions: number;
  total_minutes: number;
  xp_earned: number;
}

export function StudySessionPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [sessions, setSessions] = useState<StudySessionItem[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [expandedRecap, setExpandedRecap] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [coursesResp, sessionsResp, statsResp] = await Promise.all([
        api.get('/api/courses'),
        api.get('/api/study-sessions', { params: { limit: 10 } }),
        api.get('/api/study-sessions/stats'),
      ]);
      setCourses(coursesResp.data);
      setSessions(sessionsResp.data.items || []);
      setStats(statsResp.data);
    } catch {
      // Non-critical — component still renders
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadData();
  }, [loadData]);

  const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    return `${m} min`;
  };

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  };

  return (
    <DashboardLayout>
      <div className="study-session-page">
        <h2 className="study-session-title">Study Session</h2>

        <PomodoroTimer courses={courses} onSessionComplete={loadData} />

        {/* Weekly stats */}
        {stats && (
          <div className="study-session-stats">
            <div className="study-session-stat">
              <span className="study-session-stat-value">{stats.total_sessions}</span>
              <span className="study-session-stat-label">Sessions this week</span>
            </div>
            <div className="study-session-stat">
              <span className="study-session-stat-value">{stats.total_minutes}</span>
              <span className="study-session-stat-label">Minutes studied</span>
            </div>
            <div className="study-session-stat">
              <span className="study-session-stat-value">{stats.xp_earned}</span>
              <span className="study-session-stat-label">XP earned</span>
            </div>
          </div>
        )}

        {/* Recent sessions */}
        {sessions.length > 0 && (
          <div className="study-session-history">
            <h3 className="study-session-history-title">Recent Sessions</h3>
            <ul className="study-session-list">
              {sessions.map((s) => (
                <li key={s.id} className="study-session-item">
                  <div className="study-session-item-header">
                    <span className="study-session-item-subject">
                      {s.subject || 'Study Session'}
                    </span>
                    <span className="study-session-item-duration">
                      {formatDuration(s.duration_seconds)}
                    </span>
                  </div>
                  <div className="study-session-item-meta">
                    <span>{formatDate(s.created_at)}</span>
                    {s.completed && <span className="study-session-item-badge">Completed</span>}
                    {s.xp_awarded ? <span className="study-session-item-xp">+{s.xp_awarded} XP</span> : null}
                  </div>
                  {s.ai_recap && (
                    <button
                      className="study-session-recap-toggle"
                      onClick={() => setExpandedRecap(expandedRecap === s.id ? null : s.id)}
                    >
                      {expandedRecap === s.id ? 'Hide recap' : 'Show recap'}
                    </button>
                  )}
                  {expandedRecap === s.id && s.ai_recap && (
                    <div className="study-session-recap-preview">{s.ai_recap}</div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
