import { useState, useEffect, useMemo } from 'react';
import './TableOfContents.css';

interface TocItem {
  id: string;
  text: string;
  level: 2 | 3;
}

interface TableOfContentsProps {
  content: string;
}

/** Parse H2/H3 headings from markdown content */
function parseHeadings(markdown: string): TocItem[] {
  const items: TocItem[] = [];
  const lines = markdown.split('\n');
  for (const line of lines) {
    const match = line.match(/^(#{2,3})\s+(.+)/);
    if (!match) continue;
    const level = match[1].length as 2 | 3;
    const text = match[2].replace(/[*_`~]/g, '').trim();
    if (!text) continue;
    const id = text
      .toLowerCase()
      .replace(/[^\w\s-]/g, '')
      .replace(/\s+/g, '-');
    items.push({ id, text, level });
  }
  return items;
}

export function TableOfContents({ content }: TableOfContentsProps) {
  const [collapsed, setCollapsed] = useState(() => window.innerWidth < 768);
  const items = useMemo(() => parseHeadings(content), [content]);

  // Update collapsed default on resize
  useEffect(() => {
    const mql = window.matchMedia('(max-width: 768px)');
    const handler = (e: MediaQueryListEvent) => {
      if (e.matches) setCollapsed(true);
    };
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, []);

  if (items.length < 2) return null;

  const handleClick = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <div className="sg-toc">
      <button
        className="sg-toc-toggle"
        onClick={() => setCollapsed(v => !v)}
        aria-expanded={!collapsed}
      >
        <svg className={`sg-toc-chevron ${collapsed ? '' : 'sg-toc-chevron--open'}`} width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M6 4l4 4-4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span className="sg-toc-title">Table of Contents</span>
        <span className="sg-toc-count">{items.length}</span>
      </button>
      {!collapsed && (
        <nav className="sg-toc-list" aria-label="Table of contents">
          {items.map((item, i) => (
            <button
              key={`${item.id}-${i}`}
              className={`sg-toc-item sg-toc-item--h${item.level}`}
              onClick={() => handleClick(item.id)}
            >
              {item.text}
            </button>
          ))}
        </nav>
      )}
    </div>
  );
}
