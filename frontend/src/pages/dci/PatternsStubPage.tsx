import { Link } from 'react-router-dom';
import { DashboardLayout } from '../../components/DashboardLayout';
import './PatternsStubPage.css';

/**
 * CB-DCI-001 M0-10 — Patterns view stub.
 *
 * Spec § 8: real pattern view ships V2. M0 just shows the single line.
 */
export function PatternsStubPage() {
  return (
    <DashboardLayout welcomeSubtitle="Patterns">
      <div className="dci-patterns-stub">
        <Link to="/parent/today" className="dci-patterns-stub__back">
          &larr; Back to tonight&rsquo;s summary
        </Link>
        <p className="dci-patterns-stub__line">
          We&rsquo;re learning about your kid. Check back in 30 days for your
          first insight.
        </p>
      </div>
    </DashboardLayout>
  );
}
