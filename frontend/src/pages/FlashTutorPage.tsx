/**
 * Flash Tutor Launcher — CB-ILE-001
 *
 * Entry point for the Interactive Learning Engine.
 * Students/parents select subject, topic, mode, and configuration.
 */
import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ileApi } from '../api/ile';
import type { ILETopic } from '../api/ile';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import './FlashTutorPage.css';

type Mode = 'learning' | 'testing';
type Difficulty = 'easy' | 'medium' | 'challenging';

/** Format remaining time as a human-readable string (e.g. "12h left", "45m left"). */
function formatTimeRemaining(expiresAt: string | null | undefined): string | null {
  if (!expiresAt) return null;
  const diff = new Date(expiresAt).getTime() - Date.now();
  if (diff <= 0) return null;
  const hours = Math.floor(diff / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
  if (hours > 0) return `${hours}h ${minutes}m left`;
  return `${minutes}m left`;
}

export function FlashTutorPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Form state
  const [mode, setMode] = useState<Mode>('learning');
  const [selectedTopic, setSelectedTopic] = useState<ILETopic | null>(null);
  const [customSubject, setCustomSubject] = useState('');
  const [customTopic, setCustomTopic] = useState('');
  const [useCustom, setUseCustom] = useState(false);
  const [questionCount, setQuestionCount] = useState(5);
  const [difficulty, setDifficulty] = useState<Difficulty>('medium');
  const [creating, setCreating] = useState(false);
  const [abandoning, setAbandoning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch available topics
  const { data: topics = [], isLoading: topicsLoading } = useQuery({
    queryKey: ['ile-topics'],
    queryFn: () => ileApi.getTopics(),
  });

  // Check for active session
  const { data: activeSession } = useQuery({
    queryKey: ['ile-active-session'],
    queryFn: () => ileApi.getActiveSession(),
  });

  const timeRemaining = useMemo(
    () => formatTimeRemaining(activeSession?.expires_at),
    [activeSession?.expires_at],
  );

  const handleStartFresh = async () => {
    if (!activeSession || abandoning) return;
    setAbandoning(true);
    setError(null);
    try {
      await ileApi.abandonSession(activeSession.id);
      queryClient.invalidateQueries({ queryKey: ['ile-active-session'] });
    } catch {
      setError('Failed to abandon session');
    } finally {
      setAbandoning(false);
    }
  };

  const handleStart = async () => {
    const subject = useCustom ? customSubject : selectedTopic?.subject;
    const topic = useCustom ? customTopic : selectedTopic?.topic;

    if (!subject || !topic) {
      setError('Please select or enter a subject and topic');
      return;
    }

    setCreating(true);
    setError(null);

    try {
      const session = await ileApi.createSession({
        mode,
        subject,
        topic,
        question_count: questionCount,
        difficulty,
        course_id: selectedTopic?.course_id ?? undefined,
      });
      navigate(`/flash-tutor/session/${session.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create session';
      setError(msg);
    } finally {
      setCreating(false);
    }
  };

  const handleResume = () => {
    if (activeSession) {
      navigate(`/flash-tutor/session/${activeSession.id}`);
    }
  };

  return (
    <DashboardLayout showBackButton headerSlot={() => null}>
      <div className="flash-tutor-page">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Flash Tutor' },
        ]} />

        <div className="ft-header">
          <h1>Flash Tutor</h1>
          <p className="ft-subtitle">Quick AI-powered practice sessions — 5 to 8 minutes</p>
        </div>

        {/* Resume banner */}
        {activeSession && activeSession.status === 'in_progress' && (
          <div className="ft-resume-banner">
            <div className="ft-resume-info">
              <span className="ft-resume-label">Session in progress</span>
              <span className="ft-resume-detail">
                {activeSession.subject} — {activeSession.topic}
              </span>
              <span className="ft-resume-meta">
                Question {activeSession.current_question_index + 1}/{activeSession.question_count}
                {timeRemaining && <> &middot; {timeRemaining}</>}
              </span>
            </div>
            <div className="ft-resume-actions">
              <button className="ft-btn ft-btn-primary" onClick={handleResume}>
                Resume Session
              </button>
              <button
                className="ft-btn ft-btn-ghost"
                onClick={handleStartFresh}
                disabled={abandoning}
              >
                {abandoning ? 'Abandoning...' : 'Start Fresh'}
              </button>
            </div>
          </div>
        )}

        {/* Mode selector */}
        <div className="ft-section">
          <h2>Mode</h2>
          <div className="ft-mode-selector">
            <button
              className={`ft-mode-btn ${mode === 'learning' ? 'active' : ''}`}
              onClick={() => setMode('learning')}
            >
              <span className="ft-mode-icon">📖</span>
              <span className="ft-mode-title">Learning</span>
              <span className="ft-mode-desc">Hints & explanations</span>
            </button>
            <button
              className={`ft-mode-btn ${mode === 'testing' ? 'active' : ''}`}
              onClick={() => setMode('testing')}
            >
              <span className="ft-mode-icon">📝</span>
              <span className="ft-mode-title">Testing</span>
              <span className="ft-mode-desc">No hints, timed</span>
            </button>
          </div>
        </div>

        {/* Topic selection */}
        <div className="ft-section">
          <h2>Topic</h2>

          {!useCustom && (
            <div className="ft-topics-grid">
              {topicsLoading ? (
                <div className="ft-loading">Loading topics...</div>
              ) : topics.length > 0 ? (
                topics.map((t, i) => (
                  <button
                    key={`${t.subject}-${t.topic}-${i}`}
                    className={`ft-topic-card ${selectedTopic?.subject === t.subject && selectedTopic?.topic === t.topic ? 'selected' : ''} ${t.is_weak_area ? 'weak' : ''}`}
                    onClick={() => setSelectedTopic(t)}
                  >
                    <span className="ft-topic-subject">{t.subject}</span>
                    <span className="ft-topic-name">{t.topic}</span>
                    {t.is_weak_area && <span className="ft-weak-badge">Needs review</span>}
                  </button>
                ))
              ) : (
                <p className="ft-empty">No course topics found. You can enter a custom topic below.</p>
              )}
            </div>
          )}

          <button className="ft-toggle-custom" onClick={() => setUseCustom(!useCustom)}>
            {useCustom ? 'Choose from my courses' : 'Enter custom topic'}
          </button>

          {useCustom && (
            <div className="ft-custom-inputs">
              <input
                type="text"
                placeholder="Subject (e.g. Math, Science)"
                value={customSubject}
                onChange={e => setCustomSubject(e.target.value)}
                className="ft-input"
                maxLength={100}
              />
              <input
                type="text"
                placeholder="Topic (e.g. Fractions, Cell Division)"
                value={customTopic}
                onChange={e => setCustomTopic(e.target.value)}
                className="ft-input"
                maxLength={200}
              />
            </div>
          )}
        </div>

        {/* Configuration */}
        <div className="ft-section">
          <h2>Settings</h2>
          <div className="ft-config-row">
            <label>Questions</label>
            <div className="ft-btn-group">
              {[3, 5, 7].map(n => (
                <button
                  key={n}
                  className={`ft-config-btn ${questionCount === n ? 'active' : ''}`}
                  onClick={() => setQuestionCount(n)}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>
          <div className="ft-config-row">
            <label>Difficulty</label>
            <div className="ft-btn-group">
              {(['easy', 'medium', 'challenging'] as Difficulty[]).map(d => (
                <button
                  key={d}
                  className={`ft-config-btn ${difficulty === d ? 'active' : ''}`}
                  onClick={() => setDifficulty(d)}
                >
                  {d.charAt(0).toUpperCase() + d.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </div>

        {error && <div className="ft-error">{error}</div>}

        <button
          className="ft-btn ft-btn-start"
          onClick={handleStart}
          disabled={creating || (!selectedTopic && !useCustom) || (useCustom && (!customSubject || !customTopic))}
        >
          {creating ? 'Generating questions...' : 'Start Session'}
        </button>
      </div>
    </DashboardLayout>
  );
}
