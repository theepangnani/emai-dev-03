import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import { projectsApi, type ProjectItem, type MilestoneItem } from '../api/projects';
import { api } from '../api/client';
import './ProjectsPage.css';

interface CourseOption {
  id: number;
  name: string;
}

const PROJECT_COLORS = ['blue', 'green', 'yellow', 'pink', 'purple', 'orange', 'red'] as const;
type ProjectColor = typeof PROJECT_COLORS[number];

const STATUS_LABELS: Record<string, string> = {
  active: 'Active',
  completed: 'Completed',
  archived: 'Archived',
};

// ============================================================
// New Project Modal
// ============================================================
function NewProjectModal({
  courses,
  onSave,
  onClose,
}: {
  courses: CourseOption[];
  onSave: (data: Parameters<typeof projectsApi.create>[0]) => void;
  onClose: () => void;
}) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [courseId, setCourseId] = useState<number | null>(null);
  const [dueDate, setDueDate] = useState('');
  const [color, setColor] = useState<ProjectColor>('blue');

  const handleSubmit = () => {
    if (!title.trim()) return;
    onSave({
      title: title.trim(),
      description: description || undefined,
      course_id: courseId,
      due_date: dueDate || undefined,
      color,
    });
  };

  return (
    <div className="project-modal-backdrop" onClick={onClose}>
      <div className="project-modal" onClick={(e) => e.stopPropagation()}>
        <div className="project-modal__header">
          <h2>New Project</h2>
          <button className="project-modal__close" onClick={onClose} aria-label="Close">&times;</button>
        </div>

        <div className="project-modal__body">
          <label className="project-field">
            <span>Title *</span>
            <input
              className="project-input"
              placeholder="Project title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              autoFocus
            />
          </label>

          <label className="project-field">
            <span>Description</span>
            <textarea
              className="project-textarea"
              placeholder="What is this project about?"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </label>

          <div className="project-field-row">
            <label className="project-field">
              <span>Course</span>
              <select
                className="project-input"
                value={courseId ?? ''}
                onChange={(e) => setCourseId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">None</option>
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </label>

            <label className="project-field">
              <span>Due Date</span>
              <input
                className="project-input"
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
            </label>
          </div>

          <div className="project-field">
            <span>Colour</span>
            <div className="project-color-row">
              {PROJECT_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  className={`project-color-dot project-color-dot--${c}${color === c ? ' selected' : ''}`}
                  onClick={() => setColor(c)}
                  aria-label={c}
                />
              ))}
            </div>
          </div>
        </div>

        <div className="project-modal__footer">
          <button className="proj-btn proj-btn--ghost" onClick={onClose}>Cancel</button>
          <button className="proj-btn proj-btn--primary" onClick={handleSubmit} disabled={!title.trim()}>
            Create Project
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// Project detail panel (milestones)
// ============================================================
function ProjectDetailPanel({
  project,
  onClose,
  onUpdateProject,
}: {
  project: ProjectItem;
  onClose: () => void;
  onUpdateProject: () => void;
}) {
  const queryClient = useQueryClient();
  const [newMilestone, setNewMilestone] = useState('');
  const [newMilestoneDate, setNewMilestoneDate] = useState('');

  const addMilestoneMutation = useMutation({
    mutationFn: ({ title, due_date }: { title: string; due_date?: string }) =>
      projectsApi.addMilestone(project.id, { title, due_date }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setNewMilestone('');
      setNewMilestoneDate('');
    },
  });

  const toggleMilestoneMutation = useMutation({
    mutationFn: ({ milestoneId, is_completed }: { milestoneId: number; is_completed: boolean }) =>
      projectsApi.updateMilestone(project.id, milestoneId, { is_completed }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects'] }),
  });

  const deleteMilestoneMutation = useMutation({
    mutationFn: (milestoneId: number) =>
      projectsApi.deleteMilestone(project.id, milestoneId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects'] }),
  });

  const markCompletedMutation = useMutation({
    mutationFn: () => projectsApi.update(project.id, { status: 'completed' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      onUpdateProject();
    },
  });

  const handleAddMilestone = () => {
    if (!newMilestone.trim()) return;
    addMilestoneMutation.mutate({ title: newMilestone.trim(), due_date: newMilestoneDate || undefined });
  };

  const total = project.milestones.length;
  const completed = project.milestones.filter((m) => m.is_completed).length;
  const progress = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div className="project-panel-backdrop" onClick={onClose}>
      <div className="project-panel" onClick={(e) => e.stopPropagation()}>
        <div className={`project-panel__accent project-panel__accent--${project.color || 'blue'}`} />
        <div className="project-panel__content">
          <div className="project-panel__header">
            <div>
              <h2 className="project-panel__title">{project.title}</h2>
              {project.course_name && (
                <span className="project-panel__course">{project.course_name}</span>
              )}
            </div>
            <button className="project-panel__close" onClick={onClose} aria-label="Close">&times;</button>
          </div>

          {project.description && (
            <p className="project-panel__desc">{project.description}</p>
          )}

          <div className="project-panel__meta">
            {project.due_date && (
              <span className="project-meta-item">
                Due: {new Date(project.due_date + 'T00:00:00').toLocaleDateString()}
              </span>
            )}
            <span className={`project-status-badge project-status-badge--${project.status}`}>
              {STATUS_LABELS[project.status] || project.status}
            </span>
          </div>

          {/* Progress */}
          <div className="project-panel__progress-section">
            <div className="project-panel__progress-label">
              Progress: {completed}/{total} milestones
            </div>
            <div className="project-progress-bar-track">
              <div className="project-progress-bar-fill" style={{ width: `${progress}%` }} />
            </div>
          </div>

          {/* Milestone list */}
          <div className="project-milestones">
            <h3 className="project-milestones__heading">Milestones</h3>
            {project.milestones.length === 0 && (
              <p className="project-milestones__empty">No milestones yet. Add one below.</p>
            )}
            {project.milestones.map((m) => (
              <div key={m.id} className={`milestone-item${m.is_completed ? ' milestone-item--done' : ''}`}>
                <input
                  type="checkbox"
                  checked={m.is_completed}
                  onChange={() => toggleMilestoneMutation.mutate({ milestoneId: m.id, is_completed: !m.is_completed })}
                  className="milestone-checkbox"
                />
                <span className="milestone-title">{m.title}</span>
                {m.due_date && (
                  <span className="milestone-date">
                    {new Date(m.due_date + 'T00:00:00').toLocaleDateString()}
                  </span>
                )}
                <button
                  className="milestone-delete"
                  onClick={() => deleteMilestoneMutation.mutate(m.id)}
                  aria-label="Delete milestone"
                  title="Delete"
                >
                  &times;
                </button>
              </div>
            ))}
          </div>

          {/* Add milestone */}
          <div className="project-add-milestone">
            <input
              className="project-input"
              placeholder="Milestone name..."
              value={newMilestone}
              onChange={(e) => setNewMilestone(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleAddMilestone(); }}
            />
            <input
              className="project-input project-input--date"
              type="date"
              value={newMilestoneDate}
              onChange={(e) => setNewMilestoneDate(e.target.value)}
              title="Optional due date"
            />
            <button
              className="proj-btn proj-btn--primary proj-btn--sm"
              onClick={handleAddMilestone}
              disabled={!newMilestone.trim() || addMilestoneMutation.isPending}
            >
              Add
            </button>
          </div>

          {project.status === 'active' && (
            <button
              className="proj-btn proj-btn--success proj-btn--full"
              onClick={() => markCompletedMutation.mutate()}
              disabled={markCompletedMutation.isPending}
            >
              Mark as Completed
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================
// Project card
// ============================================================
function ProjectCard({ project, onClick }: { project: ProjectItem; onClick: (p: ProjectItem) => void }) {
  const total = project.milestones.length;
  const completed = project.milestones.filter((m) => m.is_completed).length;
  const progress = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div className="project-card" onClick={() => onClick(project)}>
      <div className={`project-card__accent project-card__accent--${project.color || 'blue'}`} />
      <div className="project-card__body">
        <div className="project-card__top">
          <h3 className="project-card__title">{project.title}</h3>
          <span className={`project-status-badge project-status-badge--${project.status}`}>
            {STATUS_LABELS[project.status] || project.status}
          </span>
        </div>
        {project.course_name && (
          <p className="project-card__course">{project.course_name}</p>
        )}
        {project.due_date && (
          <p className="project-card__due">
            Due: {new Date(project.due_date + 'T00:00:00').toLocaleDateString()}
          </p>
        )}
        <div className="project-card__progress">
          <div className="project-card__progress-label">
            {completed}/{total} milestones
          </div>
          <div className="project-progress-bar-track">
            <div className="project-progress-bar-fill" style={{ width: `${progress}%` }} />
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// Page
// ============================================================
export function ProjectsPage() {
  const queryClient = useQueryClient();
  const [showNewModal, setShowNewModal] = useState(false);
  const [selectedProject, setSelectedProject] = useState<ProjectItem | null>(null);
  const [statusFilter, setStatusFilter] = useState('active');

  const { data: coursesData } = useQuery({
    queryKey: ['projects-courses'],
    queryFn: async () => {
      const res = await api.get('/api/courses/');
      return (res.data?.courses ?? res.data ?? []) as CourseOption[];
    },
    staleTime: 60_000,
  });
  const courses: CourseOption[] = coursesData ?? [];

  const { data: projects = [], isLoading } = useQuery({
    queryKey: ['projects', { status: statusFilter }],
    queryFn: () => projectsApi.list({ status: statusFilter }),
  });

  const createMutation = useMutation({
    mutationFn: projectsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setShowNewModal(false);
    },
  });

  const archiveMutation = useMutation({
    mutationFn: projectsApi.archive,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setSelectedProject(null);
    },
  });

  const handleCardClick = useCallback((p: ProjectItem) => {
    setSelectedProject(p);
  }, []);

  // Keep selectedProject in sync with fresh data
  const selectedFresh = selectedProject
    ? projects.find((p) => p.id === selectedProject.id) ?? selectedProject
    : null;

  return (
    <DashboardLayout welcomeSubtitle="Track your long-term projects">
      <div className="projects-page">
        <div className="projects-header">
          <h1 className="projects-title">Projects</h1>
          <button className="proj-btn proj-btn--primary" onClick={() => setShowNewModal(true)}>
            + New Project
          </button>
        </div>

        {/* Status filter */}
        <div className="projects-filter-bar">
          {['active', 'completed', 'archived'].map((s) => (
            <button
              key={s}
              className={`projects-filter-chip${statusFilter === s ? ' active' : ''}`}
              onClick={() => setStatusFilter(s)}
            >
              {STATUS_LABELS[s]}
            </button>
          ))}
        </div>

        {isLoading && <p className="projects-loading">Loading projects...</p>}
        {!isLoading && projects.length === 0 && (
          <p className="projects-empty">
            No {statusFilter} projects. Click "+ New Project" to get started.
          </p>
        )}

        <div className="projects-grid">
          {projects.map((p) => (
            <ProjectCard key={p.id} project={p} onClick={handleCardClick} />
          ))}
        </div>

        {showNewModal && (
          <NewProjectModal
            courses={courses}
            onSave={createMutation.mutate}
            onClose={() => setShowNewModal(false)}
          />
        )}

        {selectedFresh && (
          <ProjectDetailPanel
            project={selectedFresh}
            onClose={() => setSelectedProject(null)}
            onUpdateProject={() => queryClient.invalidateQueries({ queryKey: ['projects'] })}
          />
        )}
      </div>
    </DashboardLayout>
  );
}
