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
  onDeleteSub?: (subId: number) => void;
}

export function LinkedMaterialsPanel({ materials, currentMaterialId, isCurrentMaster, loading, onDeleteSub }: LinkedMaterialsPanelProps) {
  const [expanded, setExpanded] = useState(false);

  if (loading) return null;
  if (!materials || materials.length === 0) return null;

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
          Linked Materials ({materials.length})
        </span>
        <span className={`linked-materials-chevron ${expanded ? 'expanded' : ''}`}>
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </span>
      </button>

      {expanded && (
        <div className="linked-materials-list">
          {materials.map(m => (
            <div key={m.id} className={`linked-material-item ${m.id === currentMaterialId ? 'current' : ''}`}>
              <Link
                to={`/course-materials/${m.id}`}
                className="linked-material-link"
              >
                <span className="linked-material-title">
                  {m.title}
                </span>
                {m.is_master === 'true' && (
                  <span className="linked-material-badge master">Master</span>
                )}
                {m.is_master !== 'true' && (
                  <span className="linked-material-badge sub">Sub</span>
                )}
              </Link>
              {isCurrentMaster && m.is_master !== 'true' && m.id !== currentMaterialId && onDeleteSub && (
                <button
                  className="linked-material-delete-btn"
                  title="Delete sub-material"
                  aria-label={`Delete ${m.title}`}
                  onClick={() => {
                    if (window.confirm('Delete this sub-material? This will permanently remove the file and any linked study guides.')) {
                      onDeleteSub(m.id);
                    }
                  }}
                >
                  &times;
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
