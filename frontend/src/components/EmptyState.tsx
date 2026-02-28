import React from 'react';
import './EmptyState.css';

interface EmptyStateAction {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary';
}

interface EmptyStateProps {
  icon?: string | React.ReactNode;
  title: string;
  description?: string;
  action?: EmptyStateAction;
  actions?: EmptyStateAction[];
  variant?: 'default' | 'compact';
  className?: string;
}

export default function EmptyState({
  icon,
  title,
  description,
  action,
  actions,
  variant = 'default',
  className = '',
}: EmptyStateProps) {
  const allActions = actions || (action ? [action] : []);

  return (
    <div className={`empty-state ${variant === 'compact' ? 'empty-state--compact' : ''} ${className}`}>
      {icon && (
        <div className="empty-state-icon" aria-hidden="true">
          {typeof icon === 'string' ? <span role="img" aria-hidden="true">{icon}</span> : icon}
        </div>
      )}
      <h3 className="empty-state-title">{title}</h3>
      {description && <p className="empty-state-text">{description}</p>}
      {allActions.length > 0 && (
        <div className="empty-state-actions">
          {allActions.map((a, i) => (
            <button
              key={i}
              className={`empty-state-cta ${a.variant === 'secondary' ? 'empty-state-cta--secondary' : ''}`}
              onClick={a.onClick}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
