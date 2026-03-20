import { useState } from 'react'
import { useAuth } from '../context/AuthContext'

interface ParentSummaryCardProps {
  summary: string | null | undefined
  studentName?: string
  collapsed?: boolean
}

export default function ParentSummaryCard({
  summary,
  studentName,
  collapsed: initialCollapsed = false,
}: ParentSummaryCardProps) {
  const { user } = useAuth()
  const [isCollapsed, setIsCollapsed] = useState(initialCollapsed)

  const isParent =
    user?.role === 'PARENT' || (user?.roles && user.roles.includes('PARENT'))

  if (!isParent || !summary) {
    return null
  }

  const title = studentName ? `Parent Summary — ${studentName}` : 'Parent Summary'

  return (
    <div className="parent-summary-card">
      <div
        className="parent-summary-header"
        onClick={() => setIsCollapsed(!isCollapsed)}
        role="button"
        tabIndex={0}
      >
        <h4>{title}</h4>
        <span className="collapse-icon">{isCollapsed ? '▶' : '▼'}</span>
      </div>
      {!isCollapsed && (
        <div className="parent-summary-body">
          <p>{summary}</p>
        </div>
      )}
    </div>
  )
}
