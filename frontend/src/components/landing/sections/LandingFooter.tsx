import { Link } from 'react-router-dom';
import { useSectionViewTracker } from '../useSectionViewTracker';
import { LANDING_SECTION_ID } from '../sectionIds';
import './LandingFooter.css';

/**
 * CB-LAND-001 S12B — Landing v2 footer.
 *
 * Rendered last on the LandingPageV2 scaffold (via the S2 registry). Four
 * desktop columns collapse to a single mobile column. The bottom strip shows
 * the copyright line and a small "Made in Canada" chip.
 *
 * All links inside placeholder columns use "#" until real destinations ship
 * (Company/Legal pages tracked under separate CB-LAND-001 follow-ups).
 */
export function LandingFooter() {
  const sectionRef = useSectionViewTracker<HTMLElement>('footer');
  return (
    <footer
      ref={sectionRef}
      data-landing="v2"
      className="landing-footer"
      aria-labelledby="landing-footer-heading"
    >
      <h2 id="landing-footer-heading" className="sr-only">
        ClassBridge footer
      </h2>
      <div className="landing-footer__inner">
        {/* Brand mark above the column grid. alt="" because the section is
            already announced by the "ClassBridge footer" sr-only <h2> above —
            an additional label would double up for screen-reader users
            (#3885). */}
        <img
          src="/classbridge-logo-dark.png"
          alt=""
          aria-hidden="true"
          width={60}
          height={40}
          className="landing-footer__logo"
        />
        <div className="landing-footer__columns">
          <section
            className="landing-footer__col"
            aria-labelledby="landing-footer-product"
          >
            <h3
              id="landing-footer-product"
              className="landing-footer__col-title"
            >
              Product
            </h3>
            <ul className="landing-footer__links">
              <li>
                <a href="#features">Features</a>
              </li>
              <li>
                <a href="#how-it-works">How It Works</a>
              </li>
              <li>
                <a href="#pricing">Pricing</a>
              </li>
              <li>
                <a href="#integrations">Integrations</a>
              </li>
            </ul>
          </section>

          <section
            className="landing-footer__col"
            aria-labelledby="landing-footer-company"
          >
            <h3
              id="landing-footer-company"
              className="landing-footer__col-title"
            >
              Company
            </h3>
            <ul className="landing-footer__links">
              <li>
                <a href="#">About</a>
              </li>
              <li>
                <a href="#">Careers</a>
              </li>
              <li>
                <a href="#">Partners</a>
              </li>
              <li>
                <a href="#">Contact</a>
              </li>
            </ul>
          </section>

          <section
            className="landing-footer__col"
            aria-labelledby="landing-footer-legal"
          >
            <h3
              id="landing-footer-legal"
              className="landing-footer__col-title"
            >
              Legal
            </h3>
            <ul className="landing-footer__links">
              <li>
                <Link to="/privacy">Privacy</Link>
              </li>
              <li>
                <Link to="/terms">Terms</Link>
              </li>
              <li>
                <a href="#">Accessibility</a>
              </li>
            </ul>
          </section>

          <section
            className="landing-footer__col"
            aria-labelledby="landing-footer-connect"
          >
            <h3
              id="landing-footer-connect"
              className="landing-footer__col-title"
            >
              Connect
            </h3>
            <ul className="landing-footer__links landing-footer__links--icons">
              <li>
                <a href="#" aria-label="Email ClassBridge">
                  <span aria-hidden="true" className="landing-footer__icon">
                    @
                  </span>
                  <span>Email</span>
                </a>
              </li>
              <li>
                <a href="#" aria-label="ClassBridge on LinkedIn">
                  <span aria-hidden="true" className="landing-footer__icon">
                    in
                  </span>
                  <span>LinkedIn</span>
                </a>
              </li>
              <li>
                <a href="#" aria-label="ClassBridge on Twitter">
                  <span aria-hidden="true" className="landing-footer__icon">
                    x
                  </span>
                  <span>Twitter</span>
                </a>
              </li>
            </ul>
          </section>
        </div>

        <div className="landing-footer__bottom">
          <p className="landing-footer__copyright">
            &copy; 2026 ClassBridge &middot; classbridge.ca
          </p>
          <span className="landing-footer__chip" aria-label="Made in Canada">
            Made in Canada
          </span>
        </div>
      </div>
    </footer>
  );
}

export const section = {
  id: LANDING_SECTION_ID.footer,
  order: 9999,
  component: LandingFooter,
};

export default LandingFooter;
