import { useNavigate } from 'react-router-dom';
import type { DciArtifact } from '../../api/dciSummary';
import './ArtifactStrip.css';

interface Props {
  artifacts: DciArtifact[];
  /** Fired before navigation so the page can emit telemetry */
  onOpen?: (artifact: DciArtifact) => void;
}

/**
 * CB-DCI-001 M0-10 — horizontal strip of today's artifacts.
 *
 * Spec § 8: thumbnail row of photos / voice waveform pills / text snippets,
 * tap-to-deep-dive opens `/parent/today/artifact/{id}`.
 */
export function ArtifactStrip({ artifacts, onOpen }: Props) {
  const navigate = useNavigate();
  if (artifacts.length === 0) return null;

  const handleOpen = (artifact: DciArtifact) => {
    onOpen?.(artifact);
    navigate(`/parent/today/artifact/${artifact.id}`);
  };

  return (
    <section className="dci-artifact-strip" aria-label="Today's artifacts">
      <h3 className="dci-artifact-strip__title">Today&rsquo;s artifacts</h3>
      <ul className="dci-artifact-strip__list">
        {artifacts.map((a) => (
          <li key={a.id}>
            <button
              type="button"
              className={`dci-artifact-tile dci-artifact-tile--${a.artifact_type}`}
              onClick={() => handleOpen(a)}
              aria-label={`Open ${a.artifact_type} artifact: ${a.preview}`}
            >
              {a.artifact_type === 'photo' && a.thumbnail_url ? (
                <img
                  src={a.thumbnail_url}
                  alt=""
                  className="dci-artifact-tile__thumb"
                />
              ) : (
                <span
                  className="dci-artifact-tile__icon"
                  aria-hidden="true"
                >
                  {iconFor(a.artifact_type)}
                </span>
              )}
              <span className="dci-artifact-tile__preview">{a.preview}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function iconFor(type: DciArtifact['artifact_type']): string {
  switch (type) {
    case 'voice':
      return '\u{1F3A4}'; // microphone
    case 'text':
      return '\u{1F4DD}'; // memo
    case 'photo':
    default:
      return '\u{1F4F7}'; // camera
  }
}
