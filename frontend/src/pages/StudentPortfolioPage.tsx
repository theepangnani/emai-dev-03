import { useState, useRef, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import { useAuth } from '../context/AuthContext';
import {
  getMyPortfolio,
  getChildPortfolio,
  updatePortfolio,
  addItem,
  updateItem,
  removeItem,
  reorderItems,
  getPortfolioSummary,
  exportPortfolio,
} from '../api/portfolio';
import type {
  Portfolio,
  PortfolioItem,
  PortfolioItemType,
  PortfolioItemCreate,
} from '../api/portfolio';
import './StudentPortfolioPage.css';

// ---------------------------------------------------------------------------
// Type badge colours per item type
// ---------------------------------------------------------------------------

const TYPE_LABELS: Record<PortfolioItemType, string> = {
  study_guide: 'Study Guide',
  quiz_result: 'Quiz Result',
  assignment: 'Assignment',
  document: 'Document',
  note: 'Note',
  achievement: 'Achievement',
};

const ALL_ITEM_TYPES: PortfolioItemType[] = [
  'study_guide',
  'quiz_result',
  'assignment',
  'document',
  'note',
  'achievement',
];

// ---------------------------------------------------------------------------
// Add Item Modal
// ---------------------------------------------------------------------------

interface AddItemModalProps {
  portfolioId: number;
  onClose: () => void;
  onAdded: () => void;
}

function AddItemModal({ portfolioId, onClose, onAdded }: AddItemModalProps) {
  const qc = useQueryClient();
  const [form, setForm] = useState<{
    item_type: PortfolioItemType;
    title: string;
    description: string;
    tags: string;
  }>({
    item_type: 'study_guide',
    title: '',
    description: '',
    tags: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) {
      setError('Title is required.');
      return;
    }
    setSaving(true);
    setError('');
    const tagsArr = form.tags
      .split(',')
      .map(t => t.trim())
      .filter(Boolean);
    const payload: PortfolioItemCreate = {
      item_type: form.item_type,
      title: form.title.trim(),
      description: form.description.trim() || undefined,
      tags: tagsArr,
    };
    try {
      await addItem(portfolioId, payload);
      qc.invalidateQueries({ queryKey: ['portfolio'] });
      onAdded();
      onClose();
    } catch {
      setError('Failed to add item. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="pf-modal-overlay" onClick={onClose}>
      <div className="pf-modal" onClick={e => e.stopPropagation()}>
        <h2 className="pf-modal-title">Add to Portfolio</h2>
        <form onSubmit={handleSubmit} className="pf-modal-form">
          <label className="pf-label">
            Type
            <select
              className="pf-input"
              value={form.item_type}
              onChange={e => setForm(f => ({ ...f, item_type: e.target.value as PortfolioItemType }))}
            >
              {ALL_ITEM_TYPES.map(t => (
                <option key={t} value={t}>{TYPE_LABELS[t]}</option>
              ))}
            </select>
          </label>

          <label className="pf-label">
            Title *
            <input
              className="pf-input"
              type="text"
              placeholder="e.g. Biology Chapter 4 Study Guide"
              value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
            />
          </label>

          <label className="pf-label">
            My Reflection
            <textarea
              className="pf-textarea"
              placeholder="What did you learn? Why is this work meaningful to you?"
              value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              rows={4}
            />
          </label>

          <label className="pf-label">
            Tags (comma-separated)
            <input
              className="pf-input"
              type="text"
              placeholder="e.g. biology, chapter4, exam"
              value={form.tags}
              onChange={e => setForm(f => ({ ...f, tags: e.target.value }))}
            />
          </label>

          {error && <p className="pf-error">{error}</p>}

          <div className="pf-modal-actions">
            <button type="button" className="pf-btn pf-btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="pf-btn pf-btn-primary" disabled={saving}>
              {saving ? 'Adding…' : 'Add Item'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Portfolio Item Card
// ---------------------------------------------------------------------------

interface ItemCardProps {
  item: PortfolioItem;
  portfolioId: number;
  dragging: boolean;
  onDragStart: (e: React.DragEvent, id: number) => void;
  onDragOver: (e: React.DragEvent, id: number) => void;
  onDrop: (e: React.DragEvent) => void;
  onDragEnd: () => void;
  onRemove: (id: number) => void;
}

function ItemCard({
  item,
  portfolioId,
  dragging,
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
  onRemove,
}: ItemCardProps) {
  return (
    <div
      className={`pf-item-card${dragging ? ' pf-item-dragging' : ''}`}
      draggable
      onDragStart={e => onDragStart(e, item.id)}
      onDragOver={e => onDragOver(e, item.id)}
      onDrop={onDrop}
      onDragEnd={onDragEnd}
    >
      <div className="pf-item-header">
        <span className={`pf-type-badge pf-type-${item.item_type}`}>
          {TYPE_LABELS[item.item_type]}
        </span>
        <button
          className="pf-item-remove"
          onClick={() => onRemove(item.id)}
          aria-label="Remove item"
          title="Remove from portfolio"
        >
          &times;
        </button>
      </div>
      <h3 className="pf-item-title">{item.title}</h3>
      {item.description && (
        <p className="pf-item-reflection">{item.description}</p>
      )}
      {item.tags.length > 0 && (
        <div className="pf-item-tags">
          {item.tags.map(tag => (
            <span key={tag} className="pf-tag">{tag}</span>
          ))}
        </div>
      )}
      <div className="pf-item-drag-hint">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="3" y1="9" x2="21" y2="9"/>
          <line x1="3" y1="15" x2="21" y2="15"/>
        </svg>
        Drag to reorder
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function StudentPortfolioPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const isParent = user?.role === 'parent';

  // For parents viewing child's portfolio — could be extended with a selector;
  // for now parents see their own linked student via a query param.
  const params = new URLSearchParams(window.location.search);
  const childStudentId = params.get('student_id') ? Number(params.get('student_id')) : null;

  const {
    data: portfolio,
    isLoading,
    isError,
  } = useQuery<Portfolio>({
    queryKey: ['portfolio', isParent && childStudentId ? `child-${childStudentId}` : 'me'],
    queryFn: () =>
      isParent && childStudentId ? getChildPortfolio(childStudentId) : getMyPortfolio(),
    enabled: true,
  });

  // ---------------------------------------------------------------------------
  // Local UI state
  // ---------------------------------------------------------------------------

  const [showAddModal, setShowAddModal] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState('');
  const [descDraft, setDescDraft] = useState('');

  const [summary, setSummary] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState('');

  const [exportLoading, setExportLoading] = useState(false);

  // Drag-and-drop state
  const dragItemId = useRef<number | null>(null);
  const dragOverItemId = useRef<number | null>(null);

  // ---------------------------------------------------------------------------
  // Mutations
  // ---------------------------------------------------------------------------

  const removeMutation = useMutation({
    mutationFn: ({ portfolioId, itemId }: { portfolioId: number; itemId: number }) =>
      removeItem(portfolioId, itemId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portfolio'] }),
  });

  const updatePortfolioMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof updatePortfolio>[1] }) =>
      updatePortfolio(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portfolio'] }),
  });

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const handleSaveHeader = useCallback(() => {
    if (!portfolio) return;
    updatePortfolioMutation.mutate({
      id: portfolio.id,
      data: { title: titleDraft, description: descDraft },
    });
    setEditingTitle(false);
  }, [portfolio, titleDraft, descDraft, updatePortfolioMutation]);

  const handleTogglePublic = useCallback(() => {
    if (!portfolio || isParent) return;
    updatePortfolioMutation.mutate({
      id: portfolio.id,
      data: { is_public: !portfolio.is_public },
    });
  }, [portfolio, isParent, updatePortfolioMutation]);

  const handleRemoveItem = useCallback(
    (itemId: number) => {
      if (!portfolio) return;
      if (!window.confirm('Remove this item from your portfolio?')) return;
      removeMutation.mutate({ portfolioId: portfolio.id, itemId });
    },
    [portfolio, removeMutation],
  );

  // Drag and drop
  const handleDragStart = useCallback((_e: React.DragEvent, id: number) => {
    dragItemId.current = id;
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent, id: number) => {
    e.preventDefault();
    dragOverItemId.current = id;
  }, []);

  const handleDrop = useCallback(
    async (_e: React.DragEvent) => {
      if (!portfolio || dragItemId.current === null || dragOverItemId.current === null) return;
      if (dragItemId.current === dragOverItemId.current) return;

      const ids = portfolio.items.map(i => i.id);
      const fromIdx = ids.indexOf(dragItemId.current);
      const toIdx = ids.indexOf(dragOverItemId.current);
      if (fromIdx === -1 || toIdx === -1) return;

      const newIds = [...ids];
      newIds.splice(fromIdx, 1);
      newIds.splice(toIdx, 0, dragItemId.current);

      try {
        await reorderItems(portfolio.id, newIds);
        qc.invalidateQueries({ queryKey: ['portfolio'] });
      } catch {
        // Silently ignore reorder errors
      }
    },
    [portfolio, qc],
  );

  const handleDragEnd = useCallback(() => {
    dragItemId.current = null;
    dragOverItemId.current = null;
  }, []);

  const handleGenerateSummary = useCallback(async () => {
    if (!portfolio) return;
    setSummaryLoading(true);
    setSummaryError('');
    try {
      const text = await getPortfolioSummary(portfolio.id);
      setSummary(text);
    } catch {
      setSummaryError('Failed to generate summary. Please try again.');
    } finally {
      setSummaryLoading(false);
    }
  }, [portfolio]);

  const handleExport = useCallback(async () => {
    if (!portfolio) return;
    setExportLoading(true);
    try {
      const data = await exportPortfolio(portfolio.id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `portfolio-${portfolio.title.replace(/\s+/g, '_')}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // Silently fail
    } finally {
      setExportLoading(false);
    }
  }, [portfolio]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (isLoading) {
    return (
      <DashboardLayout welcomeSubtitle="Loading portfolio…">
        <div className="pf-loading">Loading your portfolio…</div>
      </DashboardLayout>
    );
  }

  if (isError || !portfolio) {
    return (
      <DashboardLayout welcomeSubtitle="Portfolio">
        <div className="pf-error-state">
          Failed to load portfolio. Please refresh the page.
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout welcomeSubtitle="Portfolio">
      <div className="pf-container">
        {/* Header */}
        <div className="pf-header-card">
          {editingTitle && !isParent ? (
            <div className="pf-header-edit">
              <input
                className="pf-input pf-title-input"
                value={titleDraft}
                onChange={e => setTitleDraft(e.target.value)}
                placeholder="Portfolio title"
              />
              <textarea
                className="pf-textarea"
                value={descDraft}
                onChange={e => setDescDraft(e.target.value)}
                placeholder="Add a description…"
                rows={2}
              />
              <div className="pf-header-actions">
                <button className="pf-btn pf-btn-primary" onClick={handleSaveHeader}>
                  Save
                </button>
                <button className="pf-btn pf-btn-secondary" onClick={() => setEditingTitle(false)}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="pf-header-display">
              <div className="pf-header-text">
                <h1 className="pf-title">{portfolio.title}</h1>
                {portfolio.description && (
                  <p className="pf-description">{portfolio.description}</p>
                )}
                <p className="pf-meta">
                  {portfolio.items.length} item{portfolio.items.length !== 1 ? 's' : ''}
                  {' '}·{' '}
                  <span className={`pf-visibility ${portfolio.is_public ? 'public' : 'private'}`}>
                    {portfolio.is_public ? 'Public' : 'Private'}
                  </span>
                </p>
              </div>
              {!isParent && (
                <div className="pf-header-controls">
                  <button
                    className="pf-btn pf-btn-secondary"
                    onClick={() => {
                      setTitleDraft(portfolio.title);
                      setDescDraft(portfolio.description ?? '');
                      setEditingTitle(true);
                    }}
                  >
                    Edit
                  </button>
                  <button
                    className={`pf-btn ${portfolio.is_public ? 'pf-btn-secondary' : 'pf-btn-outline'}`}
                    onClick={handleTogglePublic}
                    title={portfolio.is_public ? 'Make private' : 'Make public'}
                  >
                    {portfolio.is_public ? 'Make Private' : 'Make Public'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Toolbar */}
        <div className="pf-toolbar">
          {!isParent && (
            <button
              className="pf-btn pf-btn-primary"
              onClick={() => setShowAddModal(true)}
            >
              + Add to Portfolio
            </button>
          )}
          <button
            className="pf-btn pf-btn-secondary"
            onClick={handleGenerateSummary}
            disabled={summaryLoading}
          >
            {summaryLoading ? 'Generating…' : 'Generate AI Summary'}
          </button>
          <button
            className="pf-btn pf-btn-secondary"
            onClick={handleExport}
            disabled={exportLoading}
          >
            {exportLoading ? 'Exporting…' : 'Export Portfolio'}
          </button>
        </div>

        {/* AI Summary Panel */}
        {(summary || summaryError) && (
          <div className={`pf-summary-panel${summaryError ? ' pf-summary-error' : ''}`}>
            {summaryError ? (
              <p>{summaryError}</p>
            ) : (
              <>
                <div className="pf-summary-label">AI-Generated Summary</div>
                <p className="pf-summary-text">{summary}</p>
                <button
                  className="pf-summary-close"
                  onClick={() => { setSummary(null); setSummaryError(''); }}
                  aria-label="Close summary"
                >
                  &times;
                </button>
              </>
            )}
          </div>
        )}

        {/* Items Grid */}
        {portfolio.items.length === 0 ? (
          <div className="pf-empty-state">
            <div className="pf-empty-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M3 7V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v16l-7-3-7 3V7"/>
                <path d="M8 10h8M8 14h5"/>
              </svg>
            </div>
            <p className="pf-empty-text">Your portfolio is empty.</p>
            {!isParent && (
              <p className="pf-empty-hint">
                Click "Add to Portfolio" to start curating your best work.
              </p>
            )}
          </div>
        ) : (
          <div className="pf-items-grid">
            {portfolio.items.map(item => (
              <ItemCard
                key={item.id}
                item={item}
                portfolioId={portfolio.id}
                dragging={dragItemId.current === item.id}
                onDragStart={handleDragStart}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                onDragEnd={handleDragEnd}
                onRemove={handleRemoveItem}
              />
            ))}
          </div>
        )}

        {/* Add Item Modal */}
        {showAddModal && (
          <AddItemModal
            portfolioId={portfolio.id}
            onClose={() => setShowAddModal(false)}
            onAdded={() => qc.invalidateQueries({ queryKey: ['portfolio'] })}
          />
        )}
      </div>
    </DashboardLayout>
  );
}

export default StudentPortfolioPage;
