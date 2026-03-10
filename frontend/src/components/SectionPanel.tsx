import type { ReactNode } from 'react';
import './SectionPanel.css';

export interface SectionPanelProps {
  title: string;
  /** Emoji or icon element shown before the title */
  icon?: string;
  /** Count badge shown after the title */
  count?: number;
  /** Whether the panel is collapsed (undefined = not collapsible) */
  collapsed?: boolean;
  /** Toggle callback — if provided, the header becomes clickable */
  onToggle?: () => void;
  /** Extra element(s) rendered in the header-right area (e.g. "All tasks >" link) */
  headerRight?: ReactNode;
  /** Panel content */
  children: ReactNode;
  /** Extra className(s) on the outer wrapper */
  className?: string;
}

export function SectionPanel({
  title,
  icon,
  count,
  collapsed,
  onToggle,
  headerRight,
  children,
  className,
}: SectionPanelProps) {
  const isCollapsible = onToggle != null;
  const isExpanded = collapsed !== true;

  const headerClasses = [
    'section-panel__header',
    isCollapsible ? 'section-panel__header--collapsible' : 'section-panel__header--static',
    isCollapsible && isExpanded ? 'section-panel__header--expanded' : '',
  ]
    .filter(Boolean)
    .join(' ');

  const handleHeaderKeyDown = (e: React.KeyboardEvent) => {
    if (onToggle && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      onToggle();
    }
  };

  return (
    <section className={`section-panel${className ? ` ${className}` : ''}`}>
      <div
        className={headerClasses}
        onClick={onToggle}
        role={isCollapsible ? 'button' : undefined}
        tabIndex={isCollapsible ? 0 : undefined}
        aria-expanded={isCollapsible ? isExpanded : undefined}
        onKeyDown={isCollapsible ? handleHeaderKeyDown : undefined}
      >
        <h3 className="section-panel__title">
          {icon && (
            <span className="section-panel__title-icon" aria-hidden="true">
              {icon}
            </span>
          )}
          {title}
          {count != null && count > 0 && <span className="section-panel__count">{count}</span>}
        </h3>
        {(headerRight || isCollapsible) && (
          <div className="section-panel__header-right">
            {headerRight}
            {isCollapsible && (
              <svg
                className={`section-panel__chevron${!isExpanded ? ' section-panel__chevron--collapsed' : ''}`}
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            )}
          </div>
        )}
      </div>
      {isExpanded && <div className="section-panel__body">{children}</div>}
    </section>
  );
}
