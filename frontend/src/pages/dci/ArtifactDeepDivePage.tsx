import { Link, useParams } from 'react-router-dom';
import { DashboardLayout } from '../../components/DashboardLayout';
import './ArtifactDeepDivePage.css';

/**
 * CB-DCI-001 M0-10 — Artifact deep-dive stub.
 *
 * Spec § 8 calls for a richer view (waveform + transcript side-by-side,
 * curriculum-strand annotation, engagement heuristic, edit/regenerate).
 * Those land in fast-follows. For M0 we ship a minimal stub that displays
 * the raw artifact id + transcript placeholder so deep-link navigation
 * works end-to-end.
 */
export function ArtifactDeepDivePage() {
  const { id } = useParams<{ id: string }>();
  return (
    <DashboardLayout welcomeSubtitle="Artifact details">
      <div className="dci-deep-dive">
        <Link to="/parent/today" className="dci-deep-dive__back">
          &larr; Back to tonight&rsquo;s summary
        </Link>
        <h2 className="dci-deep-dive__title">Artifact #{id}</h2>
        <p className="dci-deep-dive__hint">
          The full deep-dive view (transcript, curriculum strand, engagement
          rating, edit + regenerate) ships in a fast-follow. For now this is a
          placeholder so deep links from the evening summary resolve.
        </p>
        <section className="dci-deep-dive__placeholder" aria-label="Raw artifact preview">
          <p className="dci-deep-dive__placeholder-row">
            <strong>Artifact ID</strong>
            <span>{id ?? '—'}</span>
          </p>
          <p className="dci-deep-dive__placeholder-row">
            <strong>Transcript</strong>
            <span>Pending fast-follow.</span>
          </p>
        </section>
      </div>
    </DashboardLayout>
  );
}
