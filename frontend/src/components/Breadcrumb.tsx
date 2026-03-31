import { Link } from 'react-router-dom';
import './Breadcrumb.css';

interface BreadcrumbItem {
  label: string;
  to?: string; // if omitted, renders as plain text (current page)
}

interface BreadcrumbProps {
  items: BreadcrumbItem[];
}

export function Breadcrumb({ items }: BreadcrumbProps) {
  const backItem = items.length >= 2 ? items[items.length - 2] : null;

  return (
    <nav className="breadcrumb" aria-label="Breadcrumb">
      {/* Desktop: full trail */}
      <div className="breadcrumb-full">
        {items.map((item, i) => (
          <span key={i}>
            {i > 0 && <span className="breadcrumb-separator">›</span>}
            {item.to ? (
              <Link to={item.to} className="breadcrumb-link">{item.label}</Link>
            ) : (
              <span className="breadcrumb-current" aria-current="page">{item.label}</span>
            )}
          </span>
        ))}
      </div>

      {/* Mobile: back link only */}
      {backItem?.to && (
        <Link to={backItem.to} className="breadcrumb-back">
          ‹ Back to {backItem.label}
        </Link>
      )}
    </nav>
  );
}
