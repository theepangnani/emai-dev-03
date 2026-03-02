import { useState, useEffect, useCallback } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import {
  personalizationApi,
  type PersonalizationProfile,
  type SubjectMastery,
  type StudyRecommendations,
  type LearningStyle,
  type PersonalizationProfileUpdate,
} from '../api/personalization';
import './PersonalizationPage.css';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function masteryColor(level: string): string {
  switch (level) {
    case 'advanced':    return 'mastery-advanced';
    case 'proficient':  return 'mastery-proficient';
    case 'developing':  return 'mastery-developing';
    default:            return 'mastery-beginner';
  }
}

function trendIcon(trend: string): string {
  switch (trend) {
    case 'improving': return '↑';
    case 'declining': return '↓';
    default:          return '→';
  }
}

function trendClass(trend: string): string {
  switch (trend) {
    case 'improving': return 'trend-up';
    case 'declining': return 'trend-down';
    default:          return 'trend-stable';
  }
}

function styleIcon(style: LearningStyle | null): string {
  switch (style) {
    case 'visual':      return '👁️';
    case 'auditory':    return '🎵';
    case 'reading':     return '📚';
    case 'kinesthetic': return '✋';
    default:            return '🎓';
  }
}

function styleLabel(style: LearningStyle | null): string {
  switch (style) {
    case 'visual':      return 'Visual Learner';
    case 'auditory':    return 'Auditory Learner';
    case 'reading':     return 'Reading/Writing Learner';
    case 'kinesthetic': return 'Kinesthetic Learner';
    default:            return 'Learning Style Unknown';
  }
}

function styleDescription(style: LearningStyle | null): string {
  switch (style) {
    case 'visual':      return 'You learn best with diagrams, charts, and visual examples.';
    case 'auditory':    return 'You learn best through explanations, discussion, and verbal reasoning.';
    case 'reading':     return 'You learn best through detailed notes, text, and written study guides.';
    case 'kinesthetic': return 'You learn best through practice, hands-on exercises, and examples.';
    default:            return 'Run an analysis to detect your learning style.';
  }
}

function difficultyAdjLabel(adj: string): string {
  switch (adj) {
    case 'increase': return 'Increase difficulty';
    case 'decrease': return 'Decrease difficulty';
    default:         return 'Maintain current difficulty';
  }
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function LoadingSkeleton() {
  return (
    <div className="pers-skeleton-grid" aria-busy="true" aria-label="Loading personalization data">
      <div className="skeleton pers-sk-card" />
      <div className="skeleton pers-sk-card pers-sk-card--wide" />
      <div className="skeleton pers-sk-card pers-sk-card--full" />
      <div className="skeleton pers-sk-card pers-sk-card--full" />
    </div>
  );
}

interface LearningStyleCardProps {
  profile: PersonalizationProfile;
  onChangeStyle: (style: LearningStyle) => void;
}

function LearningStyleCard({ profile, onChangeStyle }: LearningStyleCardProps) {
  const [editing, setEditing] = useState(false);
  const [selected, setSelected] = useState<LearningStyle>(
    (profile.learning_style as LearningStyle) || 'reading'
  );

  const styles: LearningStyle[] = ['visual', 'auditory', 'reading', 'kinesthetic'];

  function handleSave() {
    onChangeStyle(selected);
    setEditing(false);
  }

  return (
    <div className="pers-card pers-style-card">
      <h2 className="pers-card-title">Learning Style</h2>

      {editing ? (
        <div className="pers-style-edit">
          {styles.map(s => (
            <button
              key={s}
              className={`pers-style-option${selected === s ? ' pers-style-option--active' : ''}`}
              onClick={() => setSelected(s)}
              type="button"
            >
              <span className="pers-style-option-icon">{styleIcon(s)}</span>
              <span className="pers-style-option-label">{styleLabel(s)}</span>
            </button>
          ))}
          <div className="pers-style-edit-actions">
            <button className="pers-btn pers-btn--primary" onClick={handleSave} type="button">
              Save
            </button>
            <button className="pers-btn pers-btn--ghost" onClick={() => setEditing(false)} type="button">
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="pers-style-display">
          <div className="pers-style-icon-large" aria-hidden="true">
            {styleIcon(profile.learning_style as LearningStyle)}
          </div>
          <p className="pers-style-label">{styleLabel(profile.learning_style as LearningStyle)}</p>
          <p className="pers-style-desc">{styleDescription(profile.learning_style as LearningStyle)}</p>

          {profile.learning_style && (
            <div className="pers-confidence-row">
              <span className="pers-confidence-label">AI Confidence</span>
              <div className="pers-confidence-bar-wrap">
                <div
                  className="pers-confidence-bar"
                  style={{ width: `${Math.round(profile.learning_style_confidence * 100)}%` }}
                />
              </div>
              <span className="pers-confidence-pct">
                {Math.round(profile.learning_style_confidence * 100)}%
              </span>
            </div>
          )}

          <button
            className="pers-btn pers-btn--ghost pers-style-change-btn"
            onClick={() => setEditing(true)}
            type="button"
          >
            Change Style
          </button>
        </div>
      )}
    </div>
  );
}

interface MasteryPanelProps {
  masteries: SubjectMastery[];
  onRefresh: () => void;
  refreshing: boolean;
}

function MasteryPanel({ masteries, onRefresh, refreshing }: MasteryPanelProps) {
  const [expanded, setExpanded] = useState<number | null>(null);

  const sorted = [...masteries].sort((a, b) => b.mastery_score - a.mastery_score);

  return (
    <div className="pers-card pers-mastery-card">
      <div className="pers-mastery-header">
        <h2 className="pers-card-title">Subject Mastery</h2>
        <button
          className="pers-btn pers-btn--ghost pers-btn--sm"
          onClick={onRefresh}
          disabled={refreshing}
          type="button"
        >
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {sorted.length === 0 ? (
        <p className="pers-empty-text">
          No mastery data yet. Complete quizzes and earn grades to see your scores.
        </p>
      ) : (
        <ul className="pers-mastery-list" role="list">
          {sorted.map(m => (
            <li key={m.id} className="pers-mastery-item">
              <button
                className="pers-mastery-row"
                onClick={() => setExpanded(expanded === m.id ? null : m.id)}
                aria-expanded={expanded === m.id}
                type="button"
              >
                <span className="pers-mastery-name">{m.subject_name}</span>
                <div className="pers-mastery-bar-wrap">
                  <div
                    className={`pers-mastery-bar ${masteryColor(m.mastery_level)}`}
                    style={{ width: `${m.mastery_score}%` }}
                    role="progressbar"
                    aria-valuenow={m.mastery_score}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`${m.subject_name} mastery: ${m.mastery_score}%`}
                  />
                </div>
                <span className="pers-mastery-pct">{m.mastery_score.toFixed(0)}%</span>
                <span className={`pers-mastery-trend ${trendClass(m.trend)}`} aria-hidden="true">
                  {trendIcon(m.trend)}
                </span>
              </button>

              {expanded === m.id && (
                <div className="pers-mastery-detail">
                  <div className="pers-mastery-detail-grid">
                    <div className="pers-detail-item">
                      <span className="pers-detail-label">Level</span>
                      <span className={`pers-mastery-badge ${masteryColor(m.mastery_level)}`}>
                        {m.mastery_level}
                      </span>
                    </div>
                    <div className="pers-detail-item">
                      <span className="pers-detail-label">Quiz avg</span>
                      <span className="pers-detail-value">{m.quiz_score_avg.toFixed(0)}%</span>
                    </div>
                    <div className="pers-detail-item">
                      <span className="pers-detail-label">Quiz attempts</span>
                      <span className="pers-detail-value">{m.quiz_attempts}</span>
                    </div>
                    <div className="pers-detail-item">
                      <span className="pers-detail-label">Grade avg</span>
                      <span className="pers-detail-value">{m.grade_avg.toFixed(0)}%</span>
                    </div>
                  </div>

                  {m.recommended_next_topics.length > 0 && (
                    <div className="pers-next-topics">
                      <span className="pers-detail-label">Recommended next:</span>
                      <ul className="pers-topics-list">
                        {m.recommended_next_topics.map((t, i) => (
                          <li key={i} className="pers-topic-item">{t}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

interface RecommendationsPanelProps {
  recommendations: StudyRecommendations | null;
}

function RecommendationsPanel({ recommendations: recs }: RecommendationsPanelProps) {
  if (!recs) {
    return (
      <div className="pers-card pers-recs-card">
        <h2 className="pers-card-title">Personalized Recommendations</h2>
        <p className="pers-empty-text">
          Run an analysis to generate personalised study recommendations.
        </p>
      </div>
    );
  }

  return (
    <div className="pers-card pers-recs-card">
      <h2 className="pers-card-title">Personalized Recommendations</h2>

      {recs.summary && (
        <p className="pers-recs-summary">{recs.summary}</p>
      )}

      <div className="pers-recs-grid">
        {recs.weak_areas.length > 0 && (
          <div className="pers-recs-section">
            <h3 className="pers-recs-section-title">Focus Areas</h3>
            <ul className="pers-recs-list">
              {recs.weak_areas.map((area, i) => (
                <li key={i} className="pers-recs-item pers-recs-item--weak">
                  {area}
                </li>
              ))}
            </ul>
          </div>
        )}

        {recs.recommended_topics.length > 0 && (
          <div className="pers-recs-section">
            <h3 className="pers-recs-section-title">Next Topics</h3>
            <ul className="pers-recs-list">
              {recs.recommended_topics.map((topic, i) => (
                <li key={i} className="pers-recs-item pers-recs-item--topic">
                  {topic}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="pers-recs-section">
          <h3 className="pers-recs-section-title">Study Tips</h3>
          <ul className="pers-recs-list">
            <li className="pers-recs-item">
              Preferred format: <strong>{recs.preferred_format.replace('_', ' ')}</strong>
            </li>
            <li className="pers-recs-item">
              Difficulty: <strong>{difficultyAdjLabel(recs.difficulty_adjustment)}</strong>
            </li>
          </ul>
        </div>
      </div>

      {recs.study_schedule && Object.keys(recs.study_schedule).length > 0 && (
        <div className="pers-schedule">
          <h3 className="pers-recs-section-title">Suggested Weekly Schedule</h3>
          <div className="pers-schedule-grid">
            {Object.entries(recs.study_schedule).map(([day, suggestion]) => (
              <div key={day} className="pers-schedule-day">
                <span className="pers-schedule-day-name">{day}</span>
                <span className="pers-schedule-day-task">{suggestion}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {recs.generated_at && (
        <p className="pers-recs-generated">
          Generated {new Date(recs.generated_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}

interface PreferencesPanelProps {
  profile: PersonalizationProfile;
  onSave: (data: PersonalizationProfileUpdate) => Promise<void>;
}

function PreferencesPanel({ profile, onSave }: PreferencesPanelProps) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sessionLength, setSessionLength] = useState(profile.study_session_length);
  const [studyTime, setStudyTime] = useState(profile.preferred_study_time);
  const [difficulty, setDifficulty] = useState(profile.preferred_difficulty);

  async function handleSave() {
    setSaving(true);
    try {
      await onSave({
        study_session_length: sessionLength,
        preferred_study_time: studyTime,
        preferred_difficulty: difficulty,
      });
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="pers-card pers-prefs-card">
      <div className="pers-prefs-header">
        <h2 className="pers-card-title">Study Preferences</h2>
        {!editing && (
          <button
            className="pers-btn pers-btn--ghost pers-btn--sm"
            onClick={() => setEditing(true)}
            type="button"
          >
            Edit
          </button>
        )}
      </div>

      {editing ? (
        <div className="pers-prefs-form">
          <div className="pers-prefs-field">
            <label className="pers-prefs-label" htmlFor="session-length">
              Session length (minutes)
            </label>
            <input
              id="session-length"
              type="number"
              min={5}
              max={120}
              value={sessionLength}
              onChange={e => setSessionLength(Number(e.target.value))}
              className="pers-prefs-input"
            />
          </div>

          <div className="pers-prefs-field">
            <label className="pers-prefs-label" htmlFor="study-time">
              Preferred study time
            </label>
            <select
              id="study-time"
              value={studyTime}
              onChange={e => setStudyTime(e.target.value)}
              className="pers-prefs-select"
            >
              <option value="morning">Morning</option>
              <option value="afternoon">Afternoon</option>
              <option value="evening">Evening</option>
            </select>
          </div>

          <div className="pers-prefs-field">
            <label className="pers-prefs-label" htmlFor="difficulty">
              Difficulty mode
            </label>
            <select
              id="difficulty"
              value={difficulty}
              onChange={e => setDifficulty(e.target.value)}
              className="pers-prefs-select"
            >
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
              <option value="adaptive">Adaptive (AI-controlled)</option>
            </select>
          </div>

          <div className="pers-prefs-actions">
            <button
              className="pers-btn pers-btn--primary"
              onClick={handleSave}
              disabled={saving}
              type="button"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button
              className="pers-btn pers-btn--ghost"
              onClick={() => setEditing(false)}
              type="button"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="pers-prefs-display">
          <div className="pers-prefs-item">
            <span className="pers-prefs-key">Session length</span>
            <span className="pers-prefs-val">{profile.study_session_length} min</span>
          </div>
          <div className="pers-prefs-item">
            <span className="pers-prefs-key">Preferred time</span>
            <span className="pers-prefs-val pers-prefs-val--cap">{profile.preferred_study_time}</span>
          </div>
          <div className="pers-prefs-item">
            <span className="pers-prefs-key">Difficulty mode</span>
            <span className="pers-prefs-val pers-prefs-val--cap">{profile.preferred_difficulty}</span>
          </div>
          <div className="pers-prefs-item">
            <span className="pers-prefs-key">Analysis count</span>
            <span className="pers-prefs-val">{profile.ai_analysis_count}</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

export default function PersonalizationPage() {
  const [profile, setProfile] = useState<PersonalizationProfile | null>(null);
  const [masteries, setMasteries] = useState<SubjectMastery[]>([]);
  const [recommendations, setRecommendations] = useState<StudyRecommendations | null>(null);

  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [refreshingMastery, setRefreshingMastery] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load initial data
  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [prof, mast] = await Promise.all([
          personalizationApi.getProfile(),
          personalizationApi.getMastery(),
        ]);
        setProfile(prof);
        setMasteries(mast);

        // Load recommendations if they exist
        try {
          const recs = await personalizationApi.getRecommendations();
          setRecommendations(recs);
        } catch {
          // 404 is expected when no analysis has been run — ignore
        }
      } catch (err: unknown) {
        setError('Failed to load personalization data. Please try again.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleAnalyze = useCallback(async () => {
    setAnalyzing(true);
    setError(null);
    try {
      const result = await personalizationApi.analyze();
      setProfile(result.profile);
      setRecommendations(result.recommendations);
      // Also refresh mastery after analysis
      const mast = await personalizationApi.getMastery();
      setMasteries(mast);
    } catch (err: unknown) {
      setError('Analysis failed. Please try again.');
      console.error(err);
    } finally {
      setAnalyzing(false);
    }
  }, []);

  const handleRefreshMastery = useCallback(async () => {
    setRefreshingMastery(true);
    try {
      const mast = await personalizationApi.refreshMastery();
      setMasteries(mast);
    } catch (err: unknown) {
      setError('Failed to refresh mastery scores.');
      console.error(err);
    } finally {
      setRefreshingMastery(false);
    }
  }, []);

  const handleChangeStyle = useCallback(async (style: LearningStyle) => {
    if (!profile) return;
    try {
      const updated = await personalizationApi.updateProfile({ learning_style: style });
      setProfile(updated);
    } catch (err: unknown) {
      setError('Failed to update learning style.');
      console.error(err);
    }
  }, [profile]);

  const handleSavePreferences = useCallback(async (data: PersonalizationProfileUpdate) => {
    const updated = await personalizationApi.updateProfile(data);
    setProfile(updated);
  }, []);

  return (
    <DashboardLayout>
      <div className="pers-page">
        {/* Header */}
        <div className="pers-header">
          <div className="pers-header-left">
            <h1 className="pers-title">My Learning Profile</h1>
            <p className="pers-subtitle">
              AI-powered insights tailored to how you study best
            </p>
          </div>
          <button
            className="pers-btn pers-btn--primary pers-analyze-btn"
            onClick={handleAnalyze}
            disabled={analyzing}
            type="button"
          >
            {analyzing ? (
              <>
                <span className="pers-spinner" aria-hidden="true" />
                Analyzing…
              </>
            ) : (
              'Refresh Analysis'
            )}
          </button>
        </div>

        {/* Error banner */}
        {error && (
          <div className="pers-error" role="alert">
            {error}
            <button
              className="pers-error-dismiss"
              onClick={() => setError(null)}
              aria-label="Dismiss error"
              type="button"
            >
              ×
            </button>
          </div>
        )}

        {/* Content */}
        {loading ? (
          <LoadingSkeleton />
        ) : profile ? (
          <>
            {/* Top row: style card + mastery panel */}
            <div className="pers-top-grid">
              <LearningStyleCard
                profile={profile}
                onChangeStyle={handleChangeStyle}
              />
              <MasteryPanel
                masteries={masteries}
                onRefresh={handleRefreshMastery}
                refreshing={refreshingMastery}
              />
            </div>

            {/* Recommendations */}
            <RecommendationsPanel recommendations={recommendations} />

            {/* Preferences */}
            <PreferencesPanel
              profile={profile}
              onSave={handleSavePreferences}
            />
          </>
        ) : (
          <p className="pers-empty-text">No profile data available.</p>
        )}
      </div>
    </DashboardLayout>
  );
}
