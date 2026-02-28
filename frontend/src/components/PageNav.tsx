import { Link } from 'react-router-dom';
import './PageNav.css';

interface PageNavItem {
  label: string;
  to?: string; // omitted = current page (plain text)
}

interface PageNavProps {
  items: PageNavItem[];
}

/**
 * Unified page navigation strip — replaces both the header back button and Breadcrumb.
 * Provides a prominent, deterministic back button alongside a breadcrumb trail.
 *
 * Desktop: shows back button + full breadcrumb trail
 * Mobile: shows a large, easy-to-tap back bar
 *
 * Usage:
 *   <PageNav items={[
 *     { label: 'Home', to: '/dashboard' },
 *     { label: 'Materials', to: '/course-materials' },
 *     { label: 'My Document' },   // current page, no link
 *   ]} />
 */
export function PageNav({ items }: PageNavProps) {
  // The "back" destination is always the second-to-last item
  const backItem = items.length >= 2 ? items[items.length - 2] : null;

  // Mobile: show last 2 levels with ellipsis for earlier levels
  const mobileItems = items.length > 2
    ? [{ label: '...', to: items[0].to }, ...items.slice(-2)]
    : items;

  return (
    <nav className="page-nav" aria-label="Page navigation">
      {/* Back button — always visible when there's a parent */}
      {backItem?.to && (
        <Link to={backItem.to} className="page-nav-back">
          <svg
            className="page-nav-back-icon"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M15 18l-6-6 6-6" />
          </svg>
          <span className="page-nav-back-label">{backItem.label}</span>
        </Link>
      )}

      {/* Desktop breadcrumb trail (full) */}
      <div className="page-nav-trail page-nav-trail-desktop">
        {items.map((item, i) => (
          <span key={i} className="page-nav-trail-item">
            {i > 0 && <span className="page-nav-trail-sep">/</span>}
            {item.to ? (
              <Link to={item.to} className="page-nav-trail-link">{item.label}</Link>
            ) : (
              <span className="page-nav-trail-current">{item.label}</span>
            )}
          </span>
        ))}
      </div>

      {/* Mobile breadcrumb trail (truncated: ... / Parent / Current) */}
      <div className="page-nav-trail page-nav-trail-mobile">
        {mobileItems.map((item, i) => (
          <span key={i} className="page-nav-trail-item">
            {i > 0 && <span className="page-nav-trail-sep">/</span>}
            {item.to ? (
              <Link to={item.to} className="page-nav-trail-link">{item.label}</Link>
            ) : (
              <span className="page-nav-trail-current">{item.label}</span>
            )}
          </span>
        ))}
      </div>
    </nav>
  );
}
