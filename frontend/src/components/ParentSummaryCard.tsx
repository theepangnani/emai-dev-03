import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import './ParentSummaryCard.css';

interface ParentSummaryCardProps {
  summary: string | null | undefined;
  studentName?: string;
  collapsed?: boolean;
}

export default function ParentSummaryCard({
  summary,
  studentName,
  collapsed: initialCollapsed = false,
}: ParentSummaryCardProps) {
  const { user } = useAuth();
  const [collapsed, setCollapsed] = useState(initialCollapsed);

  // Only show to parents
  const isParent = user?.role === 'PARENT' ||
    (Array.isArray(user?.roles) && user.roles.includes('PARENT'));

  if (!isParent || !summary) {
    return null;
  }

  return (
    <div className="parent-summary-card">
      <button
        className="parent-summary-card__header"
        onClick={() => setCollapsed(!collapsed)}
        aria-expanded={!collapsed}
      >
        <div className="parent-summary-card__title-row">
          <span className="parent-summary-card__icon" aria-hidden="true">&#x1F468;&#x200D;&#x1F469;&#x200D;&#x1F467;</span>
          <span className="parent-summary-card__title">
            Parent Summary{studentName ? ` \u2014 ${studentName}` : ''}
          </span>
        </div>
        <span className={`parent-summary-card__chevron ${collapsed ? '' : 'parent-summary-card__chevron--open'}`}>
          &#x25B8;
        </span>
      </button>
      {!collapsed && (
        <div className="parent-summary-card__body">
          <p className="parent-summary-card__text">{summary}</p>
        </div>
      )}
    </div>
  );
}

export type { ParentSummaryCardProps };
