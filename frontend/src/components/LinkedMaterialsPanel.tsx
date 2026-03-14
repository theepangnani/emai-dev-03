import { useState } from 'react'
import { Link } from 'react-router-dom'

export interface LinkedMaterialDisplay {
  id: number
  title: string
  is_master: string
  content_type: string
  has_file: boolean
  original_filename: string | null
  created_at: string
}

interface LinkedMaterialsPanelProps {
  materials: LinkedMaterialDisplay[]
  currentMaterialId: number
  isCurrentMaster: boolean
  loading?: boolean
}

export function LinkedMaterialsPanel({
  materials,
  currentMaterialId,
  loading,
}: LinkedMaterialsPanelProps) {
  const [expanded, setExpanded] = useState(false)

  if (!materials.length || loading) return null

  return (
    <div className="linked-materials-panel">
      <button
        className="linked-materials-toggle"
        onClick={() => setExpanded(!expanded)}
      >
        Linked Materials ({materials.length})
      </button>
      {expanded && (
        <div className="linked-materials-list">
          {materials.map((m) => (
            <Link
              key={m.id}
              to={`/course-materials/${m.id}`}
              className={`linked-material-item${m.id === currentMaterialId ? ' current' : ''}`}
            >
              <span className="linked-material-title">{m.title}</span>
              <span className={`linked-material-badge ${m.is_master === 'true' ? 'master' : 'sub'}`}>
                {m.is_master === 'true' ? 'Master' : 'Sub'}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
