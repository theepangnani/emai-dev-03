import { useRef, useEffect, useState } from 'react';
import './CollapsibleSection.css';

interface CollapsibleSectionProps {
  title: string;
  badge?: number | null;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

export function CollapsibleSection({ title, badge, expanded, onToggle, children }: CollapsibleSectionProps) {
  const contentRef = useRef<HTMLDivElement>(null);
  const [maxHeight, setMaxHeight] = useState<string>(expanded ? 'none' : '0px');

  useEffect(() => {
    const el = contentRef.current;
    if (!el) return;

    if (expanded) {
      // Measure the full scroll height, then set it as max-height for animation
      const fullHeight = el.scrollHeight;
      setMaxHeight(`${fullHeight}px`);
      // After the transition, set to 'none' so content can grow dynamically
      const timer = setTimeout(() => setMaxHeight('none'), 350);
      return () => clearTimeout(timer);
    } else {
      // First set the current height explicitly (from 'none' we can't animate)
      const currentHeight = el.scrollHeight;
      setMaxHeight(`${currentHeight}px`);
      // Force reflow, then collapse
      // eslint-disable-next-line @typescript-eslint/no-unused-expressions
      el.offsetHeight;
      requestAnimationFrame(() => {
        setMaxHeight('0px');
      });
    }
  }, [expanded]);

  return (
    <div className={`pd-collapsible${expanded ? ' expanded' : ''}`}>
      <button
        className="pd-collapsible-header"
        onClick={onToggle}
        type="button"
        aria-expanded={expanded}
        aria-label={title}
      >
        <span className={`pd-collapsible-chevron${expanded ? ' open' : ''}`} aria-hidden="true">
          {'\u25B6'}
        </span>
        <span className="pd-collapsible-title">{title}</span>
        {badge != null && badge > 0 && <span className="pd-collapsible-badge">{badge}</span>}
      </button>
      <div
        ref={contentRef}
        className="pd-collapsible-content"
        style={{ maxHeight }}
        aria-hidden={!expanded}
      >
        {children}
      </div>
    </div>
  );
}
