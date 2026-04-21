import { Link } from 'react-router-dom';
import { useSectionViewTracker } from '../useSectionViewTracker';
import './LandingNav.css';

/**
 * LandingNav — CB-LAND-001 #3885.
 *
 * Persistent top nav restoring the ClassBridge brand on LandingPageV2. The
 * legacy `LaunchLandingPage` rendered `/classbridge-logo.png` in its top nav
 * and hero; the v2 scaffold shipped without either, which would leave the
 * page brand-less once the `landing_v2` flag is flipped on.
 *
 * Contract:
 * - Left: logo `<img>` wrapped in a router `<Link to="/">` so clicking the
 *   brand mark returns to root (and is discoverable by keyboard / AT).
 * - Right: "Log In" text link → `/login`, "Join Waitlist" button → `/waitlist`.
 *   Mobile (≤640px) collapses to logo + "Log In" only — the waitlist CTA is
 *   kept below the fold in the hero to avoid double-CTA clutter on narrow
 *   viewports.
 * - Root `<nav data-landing="v2">` so the S1 token set (§6.136.1) resolves.
 * - Registered with `order: 5` so it renders before `LandingHero` (order 10).
 *
 * Accessibility:
 * - Logo `alt="ClassBridge"` (not empty) — it's a primary brand landmark.
 * - Visible focus ring on both the logo link and the "Log In" / "Join Waitlist"
 *   controls (via `focus-visible` in LandingNav.css).
 * - Nav exposes `aria-label="Landing navigation"` so screen readers can
 *   distinguish it from the footer landmark.
 */
export function LandingNav() {
  const sectionRef = useSectionViewTracker<HTMLElement>('nav');
  return (
    <nav
      ref={sectionRef}
      data-landing="v2"
      className="landing-nav"
      aria-label="Landing navigation"
    >
      <div className="landing-nav__inner">
        <Link to="/" className="landing-nav__brand" aria-label="ClassBridge home">
          <img
            src="/classbridge-logo.png"
            alt="ClassBridge"
            className="landing-nav__logo"
          />
        </Link>
        <div className="landing-nav__actions">
          <Link to="/login" className="landing-nav__login">
            Log In
          </Link>
          <Link to="/waitlist" className="landing-nav__waitlist">
            Join Waitlist
          </Link>
        </div>
      </div>
    </nav>
  );
}

/**
 * Section-registry entry. `order: 5` renders this above LandingHero (order 10)
 * so the logo sits at the very top of the page, before all other sections.
 */
export const section = { id: 'nav', order: 5, component: LandingNav };

export default LandingNav;
