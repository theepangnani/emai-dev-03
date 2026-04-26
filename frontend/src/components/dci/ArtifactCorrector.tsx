/**
 * ArtifactCorrector — list view of every artifact-classification pair the
 * kid has captured this session. One AIDetectedChip per row, plus a
 * thumbnail/transcript-snippet so the kid can match chip → thing they
 * just sent.
 */
import type { DciClassification, DciArtifactType } from '../../api/dci';
import { AIDetectedChip } from './AIDetectedChip';
import './ArtifactCorrector.css';

export interface CapturedArtifact {
  artifact_type: DciArtifactType;
  /** Object URL for the photo blob (artifact_type === 'photo'). */
  previewUrl?: string;
  /** Snippet of the typed text (artifact_type === 'text'). */
  textSnippet?: string;
}

export interface ArtifactCorrectorProps {
  artifacts: CapturedArtifact[];
  classifications: DciClassification[];
  classifying: boolean;
  onCorrect: (next: {
    artifact_type: DciArtifactType;
    subject?: string;
    topic?: string;
    deadline_iso?: string | null;
  }) => Promise<void> | void;
}

export function ArtifactCorrector({
  artifacts,
  classifications,
  classifying,
  onCorrect,
}: ArtifactCorrectorProps) {
  if (artifacts.length === 0) return null;

  return (
    <ul className="dci-artifact-corrector" aria-label="Items you sent">
      {artifacts.map((art) => {
        const classification =
          classifications.find((c) => c.artifact_type === art.artifact_type) ?? null;
        return (
          <li className="dci-artifact-corrector__row" key={art.artifact_type}>
            <div className="dci-artifact-corrector__thumb">
              {art.artifact_type === 'photo' && art.previewUrl && (
                <img
                  src={art.previewUrl}
                  alt="Captured handout"
                  className="dci-artifact-corrector__thumb-img"
                />
              )}
              {art.artifact_type === 'voice' && (
                <span className="dci-artifact-corrector__chip-icon">🎙️</span>
              )}
              {art.artifact_type === 'text' && (
                <span className="dci-artifact-corrector__text">
                  {art.textSnippet?.slice(0, 80) ?? ''}
                </span>
              )}
            </div>
            <AIDetectedChip
              classification={classification}
              loading={classifying && !classification}
              onCorrect={onCorrect}
            />
          </li>
        );
      })}
    </ul>
  );
}

export default ArtifactCorrector;
