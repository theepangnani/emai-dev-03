import { useState, useRef, useEffect } from 'react';
import './MaterialContextMenu.css';

interface MenuItem {
  label: string;
  icon?: React.ReactNode;
  onClick: () => void;
}

interface MaterialContextMenuProps {
  items: MenuItem[];
}

export function MaterialContextMenu({ items }: MaterialContextMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  return (
    <div className="material-ctx" ref={ref}>
      <button
        className={`material-ctx-trigger${open ? ' open' : ''}`}
        onClick={() => setOpen(prev => !prev)}
        aria-label="Actions menu"
        title="Actions"
      >
        +
      </button>
      {open && (
        <div className="material-ctx-menu">
          {items.map((item) => (
            <button
              key={item.label}
              className="material-ctx-item"
              onClick={() => { item.onClick(); setOpen(false); }}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
