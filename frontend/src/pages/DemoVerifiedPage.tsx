import { Link, useSearchParams } from 'react-router-dom';
import '../pages/LaunchLandingPage.css';

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

      <section className="launch-hero" aria-labelledby="demo-verified-title">
        <h1 id="demo-verified-title">You're verified</h1>
        {position > 0 ? (
          <p className="launch-hero-sub">
            You're <strong>#{position.toLocaleString()}</strong> on the ClassBridge waitlist. We'll
            email you as soon as your spot opens.
          </p>
        ) : (
          <p className="launch-hero-sub">
            Your email is confirmed and your waitlist spot is secured. We'll
            email you as soon as your spot opens.
          </p>
        )}

        <div className="launch-hero-actions">
          <Link to="/" className="launch-btn-primary launch-btn-lg">
            Back to homepage
          </Link>
          <Link to="/login" className="launch-btn-secondary launch-btn-lg">
            Sign in
          </Link>
        </div>

        <div style={{ marginTop: 40, maxWidth: 520, textAlign: 'left' }}>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.25rem', margin: '0 0 12px' }}>
            What happens next
          </h2>
          <ul style={{ color: 'var(--color-ink-muted)', lineHeight: 1.7, paddingLeft: 20 }}>
            <li>We'll email you when your role's invite wave opens.</li>
            <li>Keep an eye on your inbox for onboarding tips and early-access previews.</li>
            <li>Want to jump the queue? Forward our email to a friend who would benefit.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}

export default DemoVerifiedPage;
