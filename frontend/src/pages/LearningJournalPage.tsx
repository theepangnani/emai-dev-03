/**
 * LearningJournalPage — personal learning journal for students with AI reflection
 * prompts, mood tagging, and teacher-sharing controls.
 */
import { useState, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import {
  learningJournalApi,
  MOOD_META,
  type JournalEntry,
  type JournalEntryCreate,
  type JournalMood,
} from '../api/learningJournal';
import './LearningJournalPage.css';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseTags(raw: string): string[] {
  return raw
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean);
}

function snippet(text: string, max = 120): string {
  return text.length > max ? text.slice(0, max) + '…' : text;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

const MOODS = Object.entries(MOOD_META) as [JournalMood, (typeof MOOD_META)[JournalMood]][];

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface EntryCardProps {
  entry: JournalEntry;
  onOpen: (e: JournalEntry) => void;
}

function EntryCard({ entry, onOpen }: EntryCardProps) {
  const moodMeta = entry.mood ? MOOD_META[entry.mood] : null;
  return (
    <article
      className="jj-card"
      onClick={() => onOpen(entry)}
      style={moodMeta ? { borderTopColor: moodMeta.color } : undefined}
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onOpen(entry)}
      role="button"
      aria-label={`Journal entry: ${entry.title || 'Untitled'}`}
    >
      {moodMeta && (
        <span className="jj-card__mood" title={moodMeta.label}>
          {moodMeta.emoji}
        </span>
      )}
      <h3 className="jj-card__title">{entry.title || 'Untitled Entry'}</h3>
      <p className="jj-card__snippet">{snippet(entry.content)}</p>
      <div className="jj-card__meta">
        <span className="jj-card__date">{formatDate(entry.created_at)}</span>
        <span className="jj-card__words">{entry.word_count} words</span>
        {entry.is_teacher_visible && (
          <span className="jj-card__shared" title="Shared with teacher">
            Shared
          </span>
        )}
      </div>
      {entry.tags && entry.tags.length > 0 && (
        <div className="jj-card__tags">
          {entry.tags.map((t) => (
            <span key={t} className="jj-tag">
              {t}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}

// ---------------------------------------------------------------------------
// Stats sidebar
// ---------------------------------------------------------------------------

interface StatsSidebarProps {
  onClose: () => void;
}

function StatsSidebar({ onClose }: StatsSidebarProps) {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['journal-stats'],
    queryFn: () => learningJournalApi.getStats(),
  });

  if (isLoading) return <div className="jj-stats-panel"><p>Loading stats…</p></div>;
  if (!stats) return null;

  const totalMoods = Object.values(stats.mood_distribution).reduce((a, b) => a + b, 0);

  return (
    <aside className="jj-stats-panel">
      <button className="jj-stats-panel__close" onClick={onClose} aria-label="Close stats">
        &times;
      </button>
      <h2 className="jj-stats-panel__title">My Journal Stats</h2>

      <div className="jj-stat">
        <span className="jj-stat__label">Total Entries</span>
        <span className="jj-stat__value">{stats.total_entries}</span>
      </div>
      <div className="jj-stat">
        <span className="jj-stat__label">Avg Words</span>
        <span className="jj-stat__value">{stats.avg_words}</span>
      </div>
      <div className="jj-stat">
        <span className="jj-stat__label">Current Streak</span>
        <span className="jj-stat__value">{stats.streak_days} day{stats.streak_days !== 1 ? 's' : ''}</span>
      </div>
      <div className="jj-stat">
        <span className="jj-stat__label">This Week</span>
        <span className="jj-stat__value">{stats.entries_this_week}</span>
      </div>

      {totalMoods > 0 && (
        <div className="jj-mood-chart">
          <h3 className="jj-mood-chart__title">Mood Breakdown</h3>
          {MOODS.map(([mood, meta]) => {
            const count = stats.mood_distribution[mood] ?? 0;
            const pct = totalMoods ? Math.round((count / totalMoods) * 100) : 0;
            return (
              <div key={mood} className="jj-mood-bar">
                <span className="jj-mood-bar__label">
                  {meta.emoji} {meta.label}
                </span>
                <div className="jj-mood-bar__track">
                  <div
                    className="jj-mood-bar__fill"
                    style={{ width: `${pct}%`, backgroundColor: meta.color }}
                  />
                </div>
                <span className="jj-mood-bar__pct">{pct}%</span>
              </div>
            );
          })}
        </div>
      )}
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Entry editor (new / edit)
// ---------------------------------------------------------------------------

interface EditorProps {
  onClose: () => void;
  onSaved: () => void;
  courses: Array<{ id: number; name: string }>;
}

function EntryEditor({ onClose, onSaved, courses }: EditorProps) {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [mood, setMood] = useState<JournalMood | ''>('');
  const [tags, setTags] = useState('');
  const [courseId, setCourseId] = useState<number | ''>('');
  const [isTeacherVisible, setIsTeacherVisible] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [promptLoading, setPromptLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const fetchPrompt = useCallback(async (ai: boolean) => {
    setPromptLoading(true);
    try {
      const p = await learningJournalApi.getPrompt({ ai });
      setPrompt(p.prompt_text);
    } catch {
      setPrompt('What did you learn today?');
    } finally {
      setPromptLoading(false);
    }
  }, []);

  const handleSave = async () => {
    if (!content.trim()) {
      setError('Content cannot be empty.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const payload: JournalEntryCreate = {
        title: title.trim() || undefined,
        content: content.trim(),
        mood: mood || undefined,
        tags: parseTags(tags),
        course_id: courseId ? Number(courseId) : undefined,
        is_teacher_visible: isTeacherVisible,
        ai_prompt_used: prompt || undefined,
      };
      await learningJournalApi.createEntry(payload);
      onSaved();
    } catch (e: unknown) {
      setError('Failed to save entry. Please try again.');
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="jj-editor-overlay" role="dialog" aria-modal="true" aria-label="New journal entry">
      <div className="jj-editor">
        <div className="jj-editor__header">
          <h2>New Journal Entry</h2>
          <button className="jj-editor__close" onClick={onClose} aria-label="Close editor">
            &times;
          </button>
        </div>

        {/* Reflection prompt */}
        <div className="jj-editor__prompt-section">
          <div className="jj-editor__prompt-actions">
            <button
              className="jj-btn jj-btn--outline"
              onClick={() => fetchPrompt(false)}
              disabled={promptLoading}
            >
              Random Prompt
            </button>
            <button
              className="jj-btn jj-btn--outline jj-btn--ai"
              onClick={() => fetchPrompt(true)}
              disabled={promptLoading}
            >
              AI Prompt
            </button>
          </div>
          {promptLoading && <p className="jj-editor__prompt-loading">Generating prompt…</p>}
          {prompt && !promptLoading && (
            <blockquote className="jj-editor__prompt-text">{prompt}</blockquote>
          )}
        </div>

        {/* Title */}
        <input
          className="jj-editor__title-input"
          type="text"
          placeholder="Entry title (optional)"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />

        {/* Course */}
        {courses.length > 0 && (
          <select
            className="jj-editor__select"
            value={courseId}
            onChange={(e) => setCourseId(e.target.value ? Number(e.target.value) : '')}
          >
            <option value="">No course selected</option>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        )}

        {/* Content */}
        <textarea
          className="jj-editor__textarea"
          placeholder="Write your reflection here…"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={8}
        />

        {/* Mood selector */}
        <div className="jj-editor__mood-row">
          <span className="jj-editor__mood-label">How are you feeling?</span>
          <div className="jj-mood-picker">
            {MOODS.map(([m, meta]) => (
              <button
                key={m}
                className={`jj-mood-btn${mood === m ? ' selected' : ''}`}
                title={meta.label}
                onClick={() => setMood(mood === m ? '' : m)}
                style={mood === m ? { borderColor: meta.color, backgroundColor: meta.color + '22' } : undefined}
              >
                <span className="jj-mood-btn__emoji">{meta.emoji}</span>
                <span className="jj-mood-btn__label">{meta.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Tags */}
        <input
          className="jj-editor__tags-input"
          type="text"
          placeholder="Tags (comma-separated, e.g. math, exam, concepts)"
          value={tags}
          onChange={(e) => setTags(e.target.value)}
        />

        {/* Share with teacher */}
        <label className="jj-editor__share-toggle">
          <input
            type="checkbox"
            checked={isTeacherVisible}
            onChange={(e) => setIsTeacherVisible(e.target.checked)}
          />
          <span>Share with Teacher</span>
        </label>

        {error && <p className="jj-editor__error">{error}</p>}

        <div className="jj-editor__footer">
          <button className="jj-btn jj-btn--ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="jj-btn jj-btn--primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : 'Save Entry'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Entry detail modal
// ---------------------------------------------------------------------------

interface DetailModalProps {
  entry: JournalEntry;
  onClose: () => void;
  onDelete: (id: number) => void;
}

function DetailModal({ entry, onClose, onDelete }: DetailModalProps) {
  const moodMeta = entry.mood ? MOOD_META[entry.mood] : null;
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    if (!confirm('Delete this entry permanently?')) return;
    setDeleting(true);
    try {
      await learningJournalApi.deleteEntry(entry.id);
      onDelete(entry.id);
      onClose();
    } catch {
      alert('Failed to delete entry.');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="jj-detail-overlay" role="dialog" aria-modal="true" aria-label="Journal entry detail">
      <div className="jj-detail">
        <div className="jj-detail__header">
          <div>
            {moodMeta && (
              <span className="jj-detail__mood" style={{ color: moodMeta.color }}>
                {moodMeta.emoji} {moodMeta.label}
              </span>
            )}
            <h2 className="jj-detail__title">{entry.title || 'Untitled Entry'}</h2>
            <p className="jj-detail__meta">
              {formatDate(entry.created_at)} &bull; {entry.word_count} words
              {entry.is_teacher_visible && ' · Shared with teacher'}
            </p>
          </div>
          <button className="jj-detail__close" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>

        {entry.ai_prompt_used && (
          <blockquote className="jj-detail__prompt">
            Prompt: {entry.ai_prompt_used}
          </blockquote>
        )}

        <div className="jj-detail__content">{entry.content}</div>

        {entry.tags && entry.tags.length > 0 && (
          <div className="jj-detail__tags">
            {entry.tags.map((t) => (
              <span key={t} className="jj-tag">
                {t}
              </span>
            ))}
          </div>
        )}

        <div className="jj-detail__footer">
          <button
            className="jj-btn jj-btn--danger"
            onClick={handleDelete}
            disabled={deleting}
          >
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
          <button className="jj-btn jj-btn--ghost" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function LearningJournalPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [courseFilter, setCourseFilter] = useState<number | ''>('');
  const [showEditor, setShowEditor] = useState(false);
  const [showStats, setShowStats] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<JournalEntry | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['journal-entries', page, courseFilter],
    queryFn: () =>
      learningJournalApi.listEntries({
        page,
        limit: 20,
        course_id: courseFilter ? Number(courseFilter) : undefined,
      }),
  });

  // Fetch courses for the dropdown — re-use existing courses endpoint
  const { data: coursesData } = useQuery({
    queryKey: ['courses-light'],
    queryFn: () =>
      fetch('/api/courses', {
        headers: { Authorization: `Bearer ${localStorage.getItem('token') || ''}` },
      })
        .then((r) => r.json())
        .then((d: unknown) => {
          if (Array.isArray(d)) return d as Array<{ id: number; name: string }>;
          if (d && typeof d === 'object' && 'courses' in d) {
            const obj = d as { courses: Array<{ id: number; name: string }> };
            return obj.courses;
          }
          return [];
        }),
    staleTime: 60_000,
  });

  const courses = coursesData ?? [];

  const invalidate = useCallback(() => {
    qc.invalidateQueries({ queryKey: ['journal-entries'] });
    qc.invalidateQueries({ queryKey: ['journal-stats'] });
  }, [qc]);

  const deleteMutation = useMutation({
    mutationFn: (id: number) => learningJournalApi.deleteEntry(id),
    onSuccess: invalidate,
  });

  const entries = data?.entries ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / 20);

  return (
    <DashboardLayout welcomeSubtitle="Your personal learning journal">
      <div className="jj-page">
        {/* Page header */}
        <div className="jj-page__header">
          <div>
            <h1 className="jj-page__title">Learning Journal</h1>
            <p className="jj-page__subtitle">
              Reflect on your learning journey, track your mood, and share insights with your teacher.
            </p>
          </div>
          <div className="jj-page__actions">
            <button
              className="jj-btn jj-btn--outline"
              onClick={() => setShowStats(!showStats)}
            >
              {showStats ? 'Hide Stats' : 'My Stats'}
            </button>
            <button
              className="jj-btn jj-btn--primary"
              onClick={() => setShowEditor(true)}
            >
              + New Entry
            </button>
          </div>
        </div>

        {/* Layout: stats + list */}
        <div className={`jj-layout${showStats ? ' jj-layout--with-sidebar' : ''}`}>
          {showStats && <StatsSidebar onClose={() => setShowStats(false)} />}

          <div className="jj-content">
            {/* Filters */}
            <div className="jj-filters">
              <select
                className="jj-filter-select"
                value={courseFilter}
                onChange={(e) => {
                  setCourseFilter(e.target.value ? Number(e.target.value) : '');
                  setPage(1);
                }}
              >
                <option value="">All Courses</option>
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              {total > 0 && (
                <span className="jj-entry-count">
                  {total} {total === 1 ? 'entry' : 'entries'}
                </span>
              )}
            </div>

            {/* Entry grid */}
            {isLoading ? (
              <div className="jj-loading">Loading entries…</div>
            ) : entries.length === 0 ? (
              <div className="jj-empty">
                <p>No journal entries yet.</p>
                <button
                  className="jj-btn jj-btn--primary"
                  onClick={() => setShowEditor(true)}
                >
                  Write your first entry
                </button>
              </div>
            ) : (
              <div className="jj-masonry">
                {entries.map((entry) => (
                  <EntryCard
                    key={entry.id}
                    entry={entry}
                    onOpen={setSelectedEntry}
                  />
                ))}
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="jj-pagination">
                <button
                  className="jj-btn jj-btn--ghost"
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                >
                  Previous
                </button>
                <span>
                  {page} / {totalPages}
                </span>
                <button
                  className="jj-btn jj-btn--ghost"
                  disabled={page === totalPages}
                  onClick={() => setPage(page + 1)}
                >
                  Next
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Modals */}
      {showEditor && (
        <EntryEditor
          onClose={() => setShowEditor(false)}
          onSaved={() => {
            setShowEditor(false);
            invalidate();
          }}
          courses={courses}
        />
      )}

      {selectedEntry && (
        <DetailModal
          entry={selectedEntry}
          onClose={() => setSelectedEntry(null)}
          onDelete={(id) => {
            deleteMutation.mutate(id);
            setSelectedEntry(null);
          }}
        />
      )}
    </DashboardLayout>
  );
}

export default LearningJournalPage;
