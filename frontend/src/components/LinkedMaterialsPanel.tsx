import { useState } from 'react';
import { Link } from 'react-router-dom';
import './LinkedMaterialsPanel.css';

export interface LinkedMaterialDisplay {
  id: number;
  title: string;
  is_master: string;
  content_type: string;
  has_file: boolean;
  original_filename: string | null;
  created_at: string;
}

interface LinkedMaterialsPanelProps {
  materials: LinkedMaterialDisplay[];
  currentMaterialId: number;
  isCurrentMaster?: boolean;
  loading?: boolean;
  onReorder?: (reorderedIds: number[]) => void;
  masterId?: number;
}

export function LinkedMaterialsPanel({ materials, currentMaterialId, isCurrentMaster, loading, onReorder, masterId }: LinkedMaterialsPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [localMaterials, setLocalMaterials] = useState<LinkedMaterialDisplay[] | null>(null);

  if (loading) return null;
  if (!materials || materials.length === 0) return null;

  // Use local order if we've reordered, otherwise use props
  const displayMaterials = localMaterials ?? materials;

  // Reset local state when props change (e.g., after refetch)
  if (localMaterials && materials.length > 0 && localMaterials.length === materials.length) {
    const propsIds = materials.map(m => m.id).join(',');
    const localIds = localMaterials.map(m => m.id).join(',');
    if (propsIds === localIds) {
      // Props caught up to our local state, clear local override
    }
  }

  const masterItem = displayMaterials.find(m => m.is_master === 'true');
  const subItems = displayMaterials.filter(m => m.is_master !== 'true');

  const canReorder = isCurrentMaster && !!onReorder && !!masterId && subItems.length > 1;

  const handleMove = (index: number, direction: 'up' | 'down') => {
    const newSubs = [...subItems];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= newSubs.length) return;
    [newSubs[index], newSubs[targetIndex]] = [newSubs[targetIndex], newSubs[index]];

    // Rebuild full list: master first, then reordered subs
    const newList = masterItem ? [masterItem, ...newSubs] : [...newSubs];
    setLocalMaterials(newList);

    // Call onReorder with just the sub IDs in new order
    const newSubIds = newSubs.map(s => s.id);
    onReorder?.(newSubIds);
  };

  return (
    <div className="linked-materials-panel">
      <button
        className="linked-materials-toggle"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        <span className="linked-materials-icon">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M6 3h7a2 2 0 012 2v6a2 2 0 01-2 2H6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
            <path d="M10 3H3a2 2 0 00-2 2v6a2 2 0 002 2h7" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
          </svg>
        </span>
        <span className="linked-materials-label">
          Linked Materials ({displayMaterials.length})
        </span>
        <span className={`linked-materials-chevron ${expanded ? 'expanded' : ''}`}>
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </span>
      </button>

      {expanded && (
        <div className="linked-materials-list">
          {/* Render master item first */}
          {masterItem && (
            <Link
              key={masterItem.id}
              to={`/course-materials/${masterItem.id}`}
              className={`linked-material-item ${masterItem.id === currentMaterialId ? 'current' : ''}`}
            >
              <span className="linked-material-title">
                {masterItem.title}
              </span>
              <span className="linked-material-badge master">Master</span>
            </Link>
          )}
          {/* Render sub items with optional reorder buttons */}
          {subItems.map((m, index) => (
            <div key={m.id} className="linked-material-row">
              <Link
                to={`/course-materials/${m.id}`}
                className={`linked-material-item ${m.id === currentMaterialId ? 'current' : ''}`}
              >
                <span className="linked-material-title">
                  {m.title}
                </span>
                {canReorder && (
                  <span className="linked-material-reorder-controls">
                    <button
                      className="linked-material-reorder-btn"
                      disabled={index === 0}
                      onClick={(e) => { e.preventDefault(); e.stopPropagation(); handleMove(index, 'up'); }}
                      aria-label={`Move ${m.title} up`}
                      title="Move up"
                    >
                      {'\u25B2'}
                    </button>
                    <button
                      className="linked-material-reorder-btn"
                      disabled={index === subItems.length - 1}
                      onClick={(e) => { e.preventDefault(); e.stopPropagation(); handleMove(index, 'down'); }}
                      aria-label={`Move ${m.title} down`}
                      title="Move down"
                    >
                      {'\u25BC'}
                    </button>
                  </span>
                )}
                <span className="linked-material-badge sub">Sub</span>
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
