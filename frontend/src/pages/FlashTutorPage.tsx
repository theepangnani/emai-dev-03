/**
 * Flash Tutor Launcher — CB-ILE-001
 *
 * Entry point for the Interactive Learning Engine.
 * Students/parents select subject, topic, mode, and configuration.
 */
import { useState, useMemo, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ileApi } from '../api/ile';
import type { ILETopic, ILEMasteryEntry } from '../api/ile';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import { MasteryNode } from '../components/ile/MasteryNode';
import { TutorAvatar } from '../components/ile/TutorAvatar';
import './FlashTutorPage.css';

type Mode = 'learning' | 'testing' | 'parent_teaching';
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
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const contentIdParam = searchParams.get('content_id');
  const autoStartRef = useRef(false);

  // Parent Teaching Mode query params (#3212)
  const queryMode = searchParams.get('mode');
  const queryChildId = searchParams.get('child_id');
  const isParentTeaching = queryMode === 'parent_teaching' && user?.role === 'parent';

  // Form state
  const [mode, setMode] = useState<Mode>(isParentTeaching ? 'parent_teaching' : 'learning');
  const [selectedTopic, setSelectedTopic] = useState<ILETopic | null>(null);
  const [customSubject, setCustomSubject] = useState('');
  const [customTopic, setCustomTopic] = useState('');
  const [useCustom, setUseCustom] = useState(false);
  const [questionCount, setQuestionCount] = useState(5);
  const [difficulty, setDifficulty] = useState<Difficulty>('medium');
  const [creating, setCreating] = useState(false);
  const [abandoning, setAbandoning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPrivatePractice, setIsPrivatePractice] = useState(false);
  const [surpriseLoading, setSurpriseLoading] = useState(false);
  const [surpriseReason, setSurpriseReason] = useState<string | null>(null);
  const [topicSearch, setTopicSearch] = useState('');
  const [showAllTopics, setShowAllTopics] = useState(false);

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

  // Fetch mastery map for Memory Glow (#3210) — non-blocking, OK to fail
  const { data: masteryMap } = useQuery({
    queryKey: ['ile-mastery'],
    queryFn: () => ileApi.getMasteryMap(),
    retry: false,
  });

  const displayedTopics = useMemo(() => {
    let filtered = topics;
    if (topicSearch.trim()) {
      const q = topicSearch.toLowerCase();
      filtered = topics.filter(t =>
        t.topic.toLowerCase().includes(q) ||
        t.subject.toLowerCase().includes(q) ||
        (t.course_name && t.course_name.toLowerCase().includes(q))
      );
    }
    // Sort: weak areas first, then alphabetical
    const sorted = [...filtered].sort((a, b) => {
      if (a.is_weak_area !== b.is_weak_area) return a.is_weak_area ? -1 : 1;
      return a.topic.localeCompare(b.topic);
    });
    return showAllTopics ? sorted : sorted.slice(0, 5);
  }, [topics, topicSearch, showAllTopics]);

  const totalFilteredCount = useMemo(() => {
    if (!topicSearch.trim()) return topics.length;
    const q = topicSearch.toLowerCase();
    return topics.filter(t =>
      t.topic.toLowerCase().includes(q) ||
      t.subject.toLowerCase().includes(q) ||
      (t.course_name && t.course_name.toLowerCase().includes(q))
    ).length;
  }, [topics, topicSearch]);

  useEffect(() => { setShowAllTopics(false); }, [topicSearch]);

  // Auto-start session when content_id query param is provided (#3272)
  useEffect(() => {
    if (!contentIdParam || autoStartRef.current || activeSession) return;
    autoStartRef.current = true;
    setCreating(true);
    setError(null);
    ileApi.createSessionFromStudyGuide({
      course_content_id: parseInt(contentIdParam, 10),
      mode: 'learning',
    })
      .then(session => navigate(`/flash-tutor/session/${session.id}`, { replace: true }))
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Failed to create session from content';
        setError(msg);
      })
      .finally(() => setCreating(false));
  }, [contentIdParam]); // eslint-disable-line react-hooks/exhaustive-deps

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
        is_private_practice: isPrivatePractice,
        course_id: selectedTopic?.course_id ?? undefined,
        timer_enabled: mode === 'parent_teaching' ? false : undefined,
        child_student_id: mode === 'parent_teaching' && queryChildId ? parseInt(queryChildId) : undefined,
      });
      navigate(`/flash-tutor/session/${session.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create session';
      setError(msg);
    } finally {
      setCreating(false);
    }
  };

  const handleSurpriseMe = async () => {
    setSurpriseLoading(true);
    setSurpriseReason(null);
    setError(null);
    try {
      const result = await ileApi.getSurpriseMe();
      setSelectedTopic(result.topic);
      setUseCustom(false);
      setSurpriseReason(result.reason);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to get surprise topic';
      setError(msg);
    } finally {
      setSurpriseLoading(false);
    }
  };

  const handleResume = () => {
    if (activeSession) {
      navigate(`/flash-tutor/session/${activeSession.id}`);
    }
  };

  const handleMasteryClick = (entry: ILEMasteryEntry) => {
    setUseCustom(false);
    setCustomSubject('');
    setCustomTopic('');
    // Find matching topic from course list or set as custom
    const match = topics.find(t => t.subject === entry.subject && t.topic === entry.topic);
    if (match) {
      setSelectedTopic(match);
    } else {
      setUseCustom(true);
      setCustomSubject(entry.subject);
      setCustomTopic(entry.topic);
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
          <TutorAvatar size={56} mood="neutral" />
          <div className="ft-header-text">
            <h1>Flash Tutor</h1>
            <p className="ft-subtitle">Quick AI-powered practice sessions</p>
            <span className="ft-time-badge">5-8 min sessions</span>
          </div>
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

        {/* Mastery — Memory Glow (#3210) */}
        {masteryMap && masteryMap.entries && masteryMap.entries.length > 0 && (
          <div className="ft-section">
            <h2>Your Topics</h2>
            <div className="ft-mastery-grid">
              {/* Show overdue first, then by glow intensity ascending */}
              {[...masteryMap.entries]
                .sort((a, b) => a.glow_intensity - b.glow_intensity)
                .map(entry => (
                  <MasteryNode
                    key={`${entry.subject}-${entry.topic}`}
                    entry={entry}
                    onClick={handleMasteryClick}
                  />
                ))}
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
            {user?.role === 'parent' && (
              <button
                className={`ft-mode-btn ${mode === 'parent_teaching' ? 'active' : ''}`}
                onClick={() => setMode('parent_teaching')}
              >
                <span className="ft-mode-icon">👨‍🏫</span>
                <span className="ft-mode-title">Teach</span>
                <span className="ft-mode-desc">Guide your child</span>
              </button>
            )}
          </div>
        </div>

        {/* Topic selection */}
        <div className="ft-section">
          <div className="ft-topic-header">
            <h2>Topic</h2>
            <button
              className="ft-btn ft-btn-surprise"
              onClick={handleSurpriseMe}
              disabled={surpriseLoading}
            >
              {surpriseLoading ? 'Picking...' : 'Surprise Me'}
            </button>
          </div>

          {surpriseReason && (
            <div className="ft-surprise-reason">{surpriseReason}</div>
          )}

          {!useCustom && (
            <>
              {topics.length > 5 && (
                <input
                  type="text"
                  className="ft-input ft-topic-search"
                  placeholder="Search topics..."
                  value={topicSearch}
                  onChange={e => setTopicSearch(e.target.value)}
                />
              )}
              <div className="ft-topics-grid">
                {topicsLoading ? (
                  <div className="ft-loading">Loading topics...</div>
                ) : displayedTopics.length > 0 ? (
                  displayedTopics.map((t, i) => (
                    <button
                      key={`${t.subject}-${t.topic}-${i}`}
                      className={`ft-topic-card ${selectedTopic?.subject === t.subject && selectedTopic?.topic === t.topic ? 'selected' : ''} ${t.is_weak_area ? 'weak' : ''}`}
                      onClick={() => { setSelectedTopic(t); setSurpriseReason(null); }}
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
              {totalFilteredCount > 5 && (
                <button
                  className="ft-show-all-btn"
                  onClick={() => setShowAllTopics(!showAllTopics)}
                >
                  {showAllTopics ? 'Show less' : `Show all ${totalFilteredCount} topics`}
                </button>
              )}
            </>
          )}

          <button className="ft-toggle-custom" onClick={() => { setUseCustom(!useCustom); setSurpriseReason(null); }}>
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
          {user?.role === 'student' && (
            <div className="ft-config-row">
              <label htmlFor="ft-private-practice">Private Practice</label>
              <label className="ft-checkbox-label">
                <input
                  id="ft-private-practice"
                  type="checkbox"
                  checked={isPrivatePractice}
                  onChange={e => setIsPrivatePractice(e.target.checked)}
                />
                <span>Scores hidden from parents/teachers</span>
              </label>
            </div>
          )}
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
