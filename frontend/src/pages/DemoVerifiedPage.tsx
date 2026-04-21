import { Link, useSearchParams } from 'react-router-dom';
import { DemoMascot } from '../components/demo/DemoMascot';
import { IconCheck, IconArrowRight } from '../components/demo/icons';
import '../pages/LaunchLandingPage.css';
import './DemoVerifiedPage.css';

/**
 * Public "email verified" confirmation page reached via
 *   GET /api/v1/demo/verify?token=... → 302 /demo/verified?pos=347
 */
export function DemoVerifiedPage() {
  const [params] = useSearchParams();
  const posParam = params.get('pos');
  const position = posParam && /^\d+$/.test(posParam) ? parseInt(posParam, 10) : 0;

  return (
    <div className="launch-page">
      <nav className="launch-nav" aria-label="Primary">
        <Link to="/" aria-label="ClassBridge home">
          <img src="/classbridge-logo.png" alt="ClassBridge" className="launch-nav-logo" />
        </Link>
      </nav>

      <section className="demo-verified-hero" aria-labelledby="demo-verified-title">
        <div className="demo-verified-mascot">
          <DemoMascot size={96} mood="complete" />
        </div>

        <h1 id="demo-verified-title" className="demo-verified-title">
          Your spot is saved
        </h1>

        {position > 0 && (
          <div className="demo-verified-position-pill" aria-label={`Waitlist position ${position}`}>
            #{position.toLocaleString()}
          </div>
        )}

        <ul className="demo-verified-benefits">
          <li>
            <IconCheck size={20} />
            <span>Your email is confirmed and your waitlist spot is locked in.</span>
          </li>
          <li>
            <IconCheck size={20} />
            <span>We'll email you the moment your role's invite wave opens.</span>
          </li>
          <li>
            <IconCheck size={20} />
            <span>Want to jump the queue? Forward our email to a friend who'd benefit.</span>
          </li>
        </ul>

        <Link to="/" className="launch-btn-primary launch-btn-lg demo-verified-cta">
          <IconArrowRight size={18} />
          <span>Back to ClassBridge</span>
        </Link>
      </section>
    </div>
  );
}

export default DemoVerifiedPage;
