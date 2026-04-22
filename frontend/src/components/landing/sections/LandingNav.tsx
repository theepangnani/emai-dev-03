import { Link } from 'react-router-dom';
import { useLandingCtas } from '../useLandingCtas';
import { LANDING_SECTION_ID } from '../sectionIds';
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
  // NOTE: intentionally does NOT call useSectionViewTracker. The nav is
  // sticky at the top of the page and is guaranteed >50% visible on first
  // paint — firing `landing_v2.section_view` for it on every render would
  // duplicate page-view signal and pollute the §6.136.7 funnel dashboards
  // that group by section_id. Scroll-engagement tracking is reserved for
  // content sections below the fold.
  //
  // The trailing CTA branches on `waitlist_enabled` (#3889 regression guard
  // of #1219): pre-launch it routes to `/waitlist` and says "Join Waitlist"
  // (short form chosen to keep the top-nav compact vs. the hero's longer
  // "Join the waitlist" label); at launch it routes to `/register` and says
  // "Get Started". The short/long label split lives in `useLandingCtas`
  // (#3898) so copy stays in one place.
  const { secondaryHref, secondaryLabelShort } = useLandingCtas();
  return (
    <nav
      data-landing="v2"
      className="landing-nav"
      aria-label="Landing navigation"
    >
      <div className="landing-nav__inner">
        <Link to="/" className="landing-nav__brand" aria-label="ClassBridge home">
          {/* width/height match the intrinsic 400×187 (~2.139:1) ratio of
              the tight-cropped v6 asset (#3908) so the browser reserves
              space before decode, eliminating above-the-fold CLS. CSS
              (`height: 64px; width: auto`) still controls the rendered
              size. */}
          <img
            src="/classbridge-logo-v6.png"
            alt="ClassBridge"
            width={137}
            height={64}
            className="landing-nav__logo"
          />
        </Link>
        <div className="landing-nav__actions">
          <Link to="/login" className="landing-nav__login">
            Log In
          </Link>
          <Link to={secondaryHref} className="landing-nav__waitlist">
            {secondaryLabelShort}
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
export const section = { id: LANDING_SECTION_ID.nav, order: 5, component: LandingNav };

export default LandingNav;
