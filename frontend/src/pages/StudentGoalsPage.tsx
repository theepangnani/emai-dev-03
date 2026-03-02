import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import { useAuth } from '../context/AuthContext';
import studentGoalsApi, {
  type AIMilestoneSuggestion,
  type CreateGoalPayload,
  type GoalCategory,
  type GoalMilestone,
  type GoalStatus,
  type StudentGoal,
  type StudentGoalSummary,
} from '../api/studentGoals';
import './StudentGoalsPage.css';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CATEGORY_ICONS: Record<GoalCategory, string> = {
  academic: '📚',
  personal: '🌱',
  extracurricular: '⚽',
  skill: '🔧',
};

const CATEGORY_LABELS: Record<GoalCategory, string> = {
  academic: 'Academic',
  personal: 'Personal',
  extracurricular: 'Extracurricular',
  skill: 'Skill',
};

const STATUS_LABELS: Record<GoalStatus, string> = {
  active: 'Active',
  completed: 'Completed',
  paused: 'Paused',
  abandoned: 'Abandoned',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function daysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const target = new Date(dateStr);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  target.setHours(0, 0, 0, 0);
  return Math.ceil((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

// ---------------------------------------------------------------------------
// Add Goal Modal
// ---------------------------------------------------------------------------

interface AddGoalModalProps {
  onClose: () => void;
  onSave: (payload: CreateGoalPayload) => void;
  loading: boolean;
}

function AddGoalModal({ onClose, onSave, loading }: AddGoalModalProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState<GoalCategory>('academic');
  const [targetDate, setTargetDate] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    onSave({
      title: title.trim(),
      description: description.trim() || undefined,
      category,
      target_date: targetDate || null,
      progress_pct: 0,
    });
  };

  return (
    <div className="goal-modal-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label="Add Goal">
      <div className="goals-form-modal" onClick={(e) => e.stopPropagation()}>
        <h2 className="goals-form-modal__title">New Goal</h2>
        <form className="goals-form" onSubmit={handleSubmit}>
          <div className="goals-form-group">
            <label className="goals-form-label" htmlFor="goal-title">Title *</label>
            <input
              id="goal-title"
              className="goals-form-input"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Improve my math grade to 90%"
              required
              maxLength={300}
            />
          </div>

          <div className="goals-form-group">
            <label className="goals-form-label" htmlFor="goal-description">Description</label>
            <textarea
              id="goal-description"
              className="goals-form-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does success look like?"
              maxLength={1000}
            />
          </div>

          <div className="goals-form-group">
            <label className="goals-form-label" htmlFor="goal-category">Category</label>
            <select
              id="goal-category"
              className="goals-form-select"
              value={category}
              onChange={(e) => setCategory(e.target.value as GoalCategory)}
            >
              {(Object.keys(CATEGORY_LABELS) as GoalCategory[]).map((cat) => (
                <option key={cat} value={cat}>
                  {CATEGORY_ICONS[cat]} {CATEGORY_LABELS[cat]}
                </option>
              ))}
            </select>
          </div>

          <div className="goals-form-group">
            <label className="goals-form-label" htmlFor="goal-target-date">Target Date</label>
            <input
              id="goal-target-date"
              className="goals-form-input"
              type="date"
              value={targetDate}
              onChange={(e) => setTargetDate(e.target.value)}
              min={new Date().toISOString().split('T')[0]}
            />
          </div>

          <div className="goals-form-actions">
            <button type="button" className="goals-btn goals-btn--secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="goals-btn goals-btn--primary" disabled={loading || !title.trim()}>
              {loading ? 'Creating...' : 'Create Goal'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Goal Detail Modal
// ---------------------------------------------------------------------------

interface GoalDetailModalProps {
  goal: StudentGoal;
  onClose: () => void;
  onProgressChange: (pct: number) => void;
  onToggleMilestone: (milestoneId: number, completed: boolean) => void;
  onGenerateAI: () => void;
  onDeleteGoal: () => void;
  onStatusChange: (status: GoalStatus) => void;
  aiLoading: boolean;
  aiSuggestions: AIMilestoneSuggestion[] | null;
  onSaveAISuggestions: () => void;
  savingAI: boolean;
  progressLoading: boolean;
  milestoneLoading: Set<number>;
}

function GoalDetailModal({
  goal,
  onClose,
  onProgressChange,
  onToggleMilestone,
  onGenerateAI,
  onDeleteGoal,
  onStatusChange,
  aiLoading,
  aiSuggestions,
  onSaveAISuggestions,
  savingAI,
  progressLoading,
  milestoneLoading,
}: GoalDetailModalProps) {
  const [localProgress, setLocalProgress] = useState(goal.progress_pct);
  const days = daysUntil(goal.target_date);

  return (
    <div className="goal-modal-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label={goal.title}>
      <div className="goal-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="goal-modal__header">
          <div>
            <h2 className="goal-modal__title">
              {CATEGORY_ICONS[goal.category as GoalCategory]} {goal.title}
            </h2>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.375rem' }}>
              <span className={`goal-status-badge goal-status-badge--${goal.status}`}>
                {STATUS_LABELS[goal.status as GoalStatus]}
              </span>
              <span className="goal-category-badge">
                {CATEGORY_LABELS[goal.category as GoalCategory]}
              </span>
              {goal.target_date && (
                <span
                  className={`goal-card__meta-item${days !== null && days < 0 ? ' goal-card__meta-item--overdue' : ''}`}
                  style={{ fontSize: '0.8rem', color: days !== null && days < 0 ? '#ef4444' : '#6b7280' }}
                >
                  {days !== null && days < 0
                    ? `${Math.abs(days)}d overdue`
                    : days === 0
                    ? 'Due today'
                    : `${days}d left — ${formatDate(goal.target_date)}`}
                </span>
              )}
            </div>
          </div>
          <button className="goal-modal__close-btn" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>

        {/* Description */}
        {goal.description && (
          <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-secondary, #6b7280)', lineHeight: 1.6 }}>
            {goal.description}
          </p>
        )}

        {/* Progress Slider */}
        <div className="goal-modal__progress-section">
          <div className="goal-modal__progress-label">
            <span>Progress</span>
            <span>{localProgress}%</span>
          </div>
          <div className="goal-progress__bar-track">
            <div
              className={`goal-progress__bar-fill goal-card--${goal.category}`}
              style={{ width: `${localProgress}%` }}
            />
          </div>
          <input
            type="range"
            className="goal-progress-slider"
            min={0}
            max={100}
            step={5}
            value={localProgress}
            onChange={(e) => setLocalProgress(Number(e.target.value))}
            onMouseUp={() => onProgressChange(localProgress)}
            onTouchEnd={() => onProgressChange(localProgress)}
            disabled={progressLoading}
            aria-label="Progress percentage"
          />
        </div>

        {/* Status Controls */}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary, #6b7280)' }}>
            Status:
          </span>
          {(['active', 'paused', 'completed', 'abandoned'] as GoalStatus[]).map((s) => (
            <button
              key={s}
              className={`goals-filters__btn${goal.status === s ? ' active' : ''}`}
              onClick={() => onStatusChange(s)}
              style={{ fontSize: '0.75rem' }}
            >
              {STATUS_LABELS[s]}
            </button>
          ))}
        </div>

        {/* Milestones */}
        <div>
          <div className="goal-milestones__header">
            <h3 className="goal-milestones__title">
              Milestones ({goal.milestones.filter((m) => m.completed).length}/{goal.milestones.length})
            </h3>
            <div className="goal-milestones__actions">
              <button
                className="goals-btn goals-btn--ai goals-btn--sm"
                onClick={onGenerateAI}
                disabled={aiLoading}
              >
                {aiLoading ? (
                  <>
                    <span className="ai-milestones-spinner" />
                    Generating...
                  </>
                ) : (
                  'AI Milestones'
                )}
              </button>
            </div>
          </div>

          {goal.milestones.length === 0 && !aiSuggestions && (
            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary, #6b7280)', margin: 0 }}>
              No milestones yet. Click "AI Milestones" to generate suggestions.
            </p>
          )}

          <div className="goal-milestones__list">
            {goal.milestones.map((m) => (
              <MilestoneItem
                key={m.id}
                milestone={m}
                onToggle={(completed) => onToggleMilestone(m.id, completed)}
                loading={milestoneLoading.has(m.id)}
              />
            ))}
          </div>

          {/* AI Suggestions */}
          {aiLoading && (
            <div className="ai-milestones-loading">
              <span className="ai-milestones-spinner" />
              Generating AI milestones...
            </div>
          )}

          {aiSuggestions && aiSuggestions.length > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#764ba2' }}>
                  AI Suggestions
                </span>
                <button
                  className="goals-btn goals-btn--primary goals-btn--sm"
                  onClick={onSaveAISuggestions}
                  disabled={savingAI}
                >
                  {savingAI ? 'Saving...' : 'Save All'}
                </button>
              </div>
              <div className="ai-suggestions-list">
                {aiSuggestions.map((s, i) => (
                  <div key={i} className="ai-suggestion-item">
                    <p className="ai-suggestion-item__title">{s.title}</p>
                    <p className="ai-suggestion-item__desc">{s.description}</p>
                    {s.suggested_target_date && (
                      <p className="ai-suggestion-item__date">
                        Suggested: {formatDate(s.suggested_target_date)}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Danger Zone */}
        <div style={{ borderTop: '1px solid var(--border-color, #e5e7eb)', paddingTop: '1rem' }}>
          <button className="goals-btn goals-btn--danger goals-btn--sm" onClick={onDeleteGoal}>
            Delete Goal
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Milestone Item
// ---------------------------------------------------------------------------

interface MilestoneItemProps {
  milestone: GoalMilestone;
  onToggle: (completed: boolean) => void;
  loading: boolean;
}

function MilestoneItem({ milestone, onToggle, loading }: MilestoneItemProps) {
  const days = daysUntil(milestone.target_date);

  return (
    <div className={`milestone-item${milestone.completed ? ' milestone-item--completed' : ''}`}>
      <input
        type="checkbox"
        className="milestone-item__checkbox"
        checked={milestone.completed}
        onChange={(e) => onToggle(e.target.checked)}
        disabled={loading}
        aria-label={`Mark "${milestone.title}" as ${milestone.completed ? 'incomplete' : 'complete'}`}
      />
      <div className="milestone-item__content">
        <p className="milestone-item__title">{milestone.title}</p>
        {milestone.description && (
          <p className="milestone-item__description">{milestone.description}</p>
        )}
        {milestone.target_date && (
          <p
            className={`milestone-item__date${!milestone.completed && days !== null && days < 0 ? ' milestone-item__date--overdue' : ''}`}
          >
            {milestone.completed
              ? `Completed ${formatDate(milestone.completed_at)}`
              : days !== null && days < 0
              ? `Overdue by ${Math.abs(days)}d — ${formatDate(milestone.target_date)}`
              : `Due ${formatDate(milestone.target_date)}`}
          </p>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Goal Card
// ---------------------------------------------------------------------------

interface GoalCardProps {
  goal: StudentGoalSummary;
  onClick: () => void;
}

function GoalCard({ goal, onClick }: GoalCardProps) {
  const days = daysUntil(goal.target_date);

  return (
    <div
      className={`goal-card goal-card--${goal.category}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
      aria-label={`Goal: ${goal.title}`}
    >
      <div className="goal-card__header">
        <div className="goal-card__title-row">
          <span className="goal-card__icon">{CATEGORY_ICONS[goal.category as GoalCategory]}</span>
          <h3 className="goal-card__title">{goal.title}</h3>
        </div>
        <span className={`goal-status-badge goal-status-badge--${goal.status}`}>
          {STATUS_LABELS[goal.status as GoalStatus]}
        </span>
      </div>

      {goal.description && (
        <p className="goal-card__description">{goal.description}</p>
      )}

      {/* Progress */}
      <div className="goal-progress">
        <div className="goal-progress__label">
          <span>Progress</span>
          <span>{goal.progress_pct}%</span>
        </div>
        <div className="goal-progress__bar-track">
          <div
            className="goal-progress__bar-fill"
            style={{ width: `${goal.progress_pct}%` }}
          />
        </div>
      </div>

      {/* Meta */}
      <div className="goal-card__meta">
        {goal.target_date && (
          <span
            className={`goal-card__meta-item${days !== null && days < 0 ? ' goal-card__meta-item--overdue' : ''}`}
          >
            {days !== null && days < 0
              ? `${Math.abs(days)}d overdue`
              : days === 0
              ? 'Due today'
              : `${days}d left`}
          </span>
        )}
        {goal.milestone_count > 0 && (
          <span className="goal-milestone-count">
            {goal.completed_milestone_count}/{goal.milestone_count} milestones
          </span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Parent Child Selector
// ---------------------------------------------------------------------------

interface ChildInfo {
  id: number;
  name: string;
}

interface ChildSelectorProps {
  children: ChildInfo[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
}

function ChildSelector({ children: kids, selectedId, onSelect }: ChildSelectorProps) {
  if (!kids.length) return null;
  return (
    <div className="goals-child-selector">
      <span className="goals-child-selector__label">Viewing:</span>
      <button
        className={`goals-child-btn${selectedId === null ? ' active' : ''}`}
        onClick={() => onSelect(null)}
      >
        My Goals
      </button>
      {kids.map((k) => (
        <button
          key={k.id}
          className={`goals-child-btn${selectedId === k.id ? ' active' : ''}`}
          onClick={() => onSelect(k.id)}
        >
          {k.name}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function StudentGoalsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const isParent = user?.role === 'parent';

  // State
  const [statusFilter, setStatusFilter] = useState<GoalStatus | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<GoalCategory | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedGoalId, setSelectedGoalId] = useState<number | null>(null);
  const [selectedChildId, setSelectedChildId] = useState<number | null>(null);
  const [aiSuggestions, setAiSuggestions] = useState<AIMilestoneSuggestion[] | null>(null);
  const [milestoneLoading, setMilestoneLoading] = useState<Set<number>>(new Set());

  // Queries
  const goalsQueryKey = isParent && selectedChildId != null
    ? ['childGoals', selectedChildId, statusFilter]
    : ['goals', statusFilter, categoryFilter];

  const { data: goals = [], isLoading } = useQuery({
    queryKey: goalsQueryKey,
    queryFn: () => {
      if (isParent && selectedChildId != null) {
        return studentGoalsApi.getChildGoals(selectedChildId, {
          status: statusFilter ?? undefined,
        });
      }
      return studentGoalsApi.listGoals({
        status: statusFilter ?? undefined,
        category: categoryFilter ?? undefined,
      });
    },
    enabled: !isParent || selectedChildId != null || true,
  });

  const { data: selectedGoal, isLoading: goalDetailLoading } = useQuery({
    queryKey: ['goal', selectedGoalId],
    queryFn: () => studentGoalsApi.getGoal(selectedGoalId!),
    enabled: selectedGoalId != null,
  });

  // Mutations
  const createGoalMutation = useMutation({
    mutationFn: studentGoalsApi.createGoal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goals'] });
      setShowAddModal(false);
    },
  });

  const updateGoalMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Parameters<typeof studentGoalsApi.updateGoal>[1] }) =>
      studentGoalsApi.updateGoal(id, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(['goal', updated.id], updated);
      queryClient.invalidateQueries({ queryKey: ['goals'] });
    },
  });

  const deleteGoalMutation = useMutation({
    mutationFn: studentGoalsApi.deleteGoal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goals'] });
      setSelectedGoalId(null);
    },
  });

  const updateProgressMutation = useMutation({
    mutationFn: ({ id, pct }: { id: number; pct: number }) =>
      studentGoalsApi.updateProgress(id, { progress_pct: pct }),
    onSuccess: (updated) => {
      queryClient.setQueryData(['goal', updated.id], updated);
      queryClient.invalidateQueries({ queryKey: ['goals'] });
    },
  });

  const toggleMilestoneMutation = useMutation({
    mutationFn: ({
      goalId,
      milestoneId,
      completed,
    }: {
      goalId: number;
      milestoneId: number;
      completed: boolean;
    }) => studentGoalsApi.toggleMilestone(goalId, milestoneId, completed),
    onMutate: ({ milestoneId }) => {
      setMilestoneLoading((prev) => new Set(prev).add(milestoneId));
    },
    onSettled: ({ id }: GoalMilestone) => {
      setMilestoneLoading((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      queryClient.invalidateQueries({ queryKey: ['goal', selectedGoalId] });
      queryClient.invalidateQueries({ queryKey: ['goals'] });
    },
  });

  const generateAIMutation = useMutation({
    mutationFn: (goalId: number) => studentGoalsApi.generateAIMilestones(goalId, false),
    onSuccess: (data) => {
      setAiSuggestions(data.suggestions);
    },
  });

  const saveAISuggestionsMutation = useMutation({
    mutationFn: (goalId: number) => studentGoalsApi.generateAIMilestones(goalId, true),
    onSuccess: () => {
      setAiSuggestions(null);
      queryClient.invalidateQueries({ queryKey: ['goal', selectedGoalId] });
      queryClient.invalidateQueries({ queryKey: ['goals'] });
    },
  });

  // Handlers
  const handleOpenGoal = useCallback((goalId: number) => {
    setSelectedGoalId(goalId);
    setAiSuggestions(null);
  }, []);

  const handleCloseGoal = useCallback(() => {
    setSelectedGoalId(null);
    setAiSuggestions(null);
  }, []);

  const handleProgressChange = useCallback(
    (pct: number) => {
      if (selectedGoalId != null) {
        updateProgressMutation.mutate({ id: selectedGoalId, pct });
      }
    },
    [selectedGoalId, updateProgressMutation],
  );

  const handleToggleMilestone = useCallback(
    (milestoneId: number, completed: boolean) => {
      if (selectedGoalId != null) {
        toggleMilestoneMutation.mutate({ goalId: selectedGoalId, milestoneId, completed });
      }
    },
    [selectedGoalId, toggleMilestoneMutation],
  );

  const handleGenerateAI = useCallback(() => {
    if (selectedGoalId != null) {
      setAiSuggestions(null);
      generateAIMutation.mutate(selectedGoalId);
    }
  }, [selectedGoalId, generateAIMutation]);

  const handleSaveAISuggestions = useCallback(() => {
    if (selectedGoalId != null) {
      saveAISuggestionsMutation.mutate(selectedGoalId);
    }
  }, [selectedGoalId, saveAISuggestionsMutation]);

  const handleDeleteGoal = useCallback(() => {
    if (selectedGoalId != null && window.confirm('Delete this goal and all its milestones? This cannot be undone.')) {
      deleteGoalMutation.mutate(selectedGoalId);
    }
  }, [selectedGoalId, deleteGoalMutation]);

  const handleStatusChange = useCallback(
    (newStatus: GoalStatus) => {
      if (selectedGoalId != null) {
        updateGoalMutation.mutate({ id: selectedGoalId, payload: { status: newStatus } });
      }
    },
    [selectedGoalId, updateGoalMutation],
  );

  // Render
  return (
    <DashboardLayout welcomeSubtitle="Track your goals and milestones">
      <div className="goals-page">
        {/* Header */}
        <div className="goals-page__header">
          <div>
            <h1 className="goals-page__title">Goals & Milestones</h1>
            <p className="goals-page__subtitle">
              {isParent
                ? 'Monitor your children\'s goals and progress'
                : 'Set goals and track your milestones'}
            </p>
          </div>
          {!isParent && (
            <button
              className="goals-btn goals-btn--primary"
              onClick={() => setShowAddModal(true)}
            >
              + Add Goal
            </button>
          )}
        </div>

        {/* Filters */}
        <div className="goals-filters">
          <span className="goals-filters__label">Status:</span>
          {([null, 'active', 'completed', 'paused', 'abandoned'] as (GoalStatus | null)[]).map((s) => (
            <button
              key={String(s)}
              className={`goals-filters__btn${statusFilter === s ? ' active' : ''}`}
              onClick={() => setStatusFilter(s)}
            >
              {s === null ? 'All' : STATUS_LABELS[s]}
            </button>
          ))}
        </div>

        {!isParent && (
          <div className="goals-filters">
            <span className="goals-filters__label">Category:</span>
            {([null, 'academic', 'personal', 'extracurricular', 'skill'] as (GoalCategory | null)[]).map((c) => (
              <button
                key={String(c)}
                className={`goals-filters__btn${categoryFilter === c ? ' active' : ''}`}
                onClick={() => setCategoryFilter(c)}
              >
                {c === null ? 'All' : `${CATEGORY_ICONS[c]} ${CATEGORY_LABELS[c]}`}
              </button>
            ))}
          </div>
        )}

        {/* Goals Grid */}
        {isLoading ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary, #6b7280)' }}>
            Loading goals...
          </div>
        ) : goals.length === 0 ? (
          <div className="goals-empty">
            <span className="goals-empty__icon">🎯</span>
            <h3 className="goals-empty__title">No goals yet</h3>
            <p className="goals-empty__desc">
              {isParent
                ? 'Your child has not set any goals yet.'
                : 'Start by creating your first goal to track your progress.'}
            </p>
            {!isParent && (
              <button className="goals-btn goals-btn--primary" onClick={() => setShowAddModal(true)}>
                + Create First Goal
              </button>
            )}
          </div>
        ) : (
          <div className="goals-grid">
            {goals.map((goal) => (
              <GoalCard key={goal.id} goal={goal} onClick={() => handleOpenGoal(goal.id)} />
            ))}
          </div>
        )}

        {/* Add Goal Modal */}
        {showAddModal && (
          <AddGoalModal
            onClose={() => setShowAddModal(false)}
            onSave={(payload) => createGoalMutation.mutate(payload)}
            loading={createGoalMutation.isPending}
          />
        )}

        {/* Goal Detail Modal */}
        {selectedGoalId != null && selectedGoal && !goalDetailLoading && (
          <GoalDetailModal
            goal={selectedGoal}
            onClose={handleCloseGoal}
            onProgressChange={handleProgressChange}
            onToggleMilestone={handleToggleMilestone}
            onGenerateAI={handleGenerateAI}
            onDeleteGoal={handleDeleteGoal}
            onStatusChange={handleStatusChange}
            aiLoading={generateAIMutation.isPending}
            aiSuggestions={aiSuggestions}
            onSaveAISuggestions={handleSaveAISuggestions}
            savingAI={saveAISuggestionsMutation.isPending}
            progressLoading={updateProgressMutation.isPending}
            milestoneLoading={milestoneLoading}
          />
        )}
      </div>
    </DashboardLayout>
  );
}

export default StudentGoalsPage;
