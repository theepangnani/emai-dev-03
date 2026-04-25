/**
 * CheckInCapturePage — Screen 2 of the kid /checkin flow.
 *
 * Owns:
 *   - mode switching via ?mode=photo|voice|text + "+ Add more" chip for
 *     multi-artifact days
 *   - on-device JPEG resize ≤ 500KB before upload (lazy-loaded import)
 *   - submit → AIDetectedChip via useDciCheckin (which also polls /status)
 *   - kid corrections via PATCH /correct
 *   - Bill 194 disclosure inline above the "Send to ClassBridge" CTA
 *
 * Spec: docs/design/CB-DCI-001-daily-checkin.md § 7.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  CapturePicker,
  type CaptureMode,
} from '../../components/dci/CapturePicker';
import {
  ArtifactCorrector,
  type CapturedArtifact,
} from '../../components/dci/ArtifactCorrector';
import { useDciCheckin } from '../../hooks/useDciCheckin';
import { emitDciKidEvent } from '../../components/dci/telemetry';
import './CheckIn.css';

interface CapturedDraft extends CapturedArtifact {
  blob?: Blob;
  text?: string;
}

const VALID_MODES: CaptureMode[] = ['photo', 'voice', 'text'];

export function CheckInCapturePage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const startedAtRef = useRef<number>(performance.now());
  const requestedMode = (params.get('mode') ?? 'photo') as CaptureMode;
  const mode: CaptureMode = VALID_MODES.includes(requestedMode)
    ? requestedMode
    : 'photo';

  const [drafts, setDrafts] = useState<Record<CaptureMode, CapturedDraft | null>>({
    photo: null,
    voice: null,
    text: null,
  });

  const {
    submit,
    isSubmitting,
    submitError,
    classifications,
    classifyMs,
    applyCorrection,
    checkinId,
  } = useDciCheckin();
  const submittedRef = useRef(false);

  // Telemetry: classify_ms is reported once per submit, when polling settles.
  useEffect(() => {
    if (classifyMs !== null) {
      emitDciKidEvent('dci.kid.classify_ms', { ms: classifyMs });
    }
  }, [classifyMs]);

  const onCapture = (
    capturedMode: CaptureMode,
    data: { blob?: Blob; text?: string },
  ) => {
    setDrafts((prev) => ({
      ...prev,
      [capturedMode]: {
        artifact_type: capturedMode,
        blob: data.blob,
        text: data.text,
        previewUrl: data.blob ? URL.createObjectURL(data.blob) : undefined,
        textSnippet: data.text,
      },
    }));
  };

  const sendToClassBridge = async () => {
    if (submittedRef.current) return;
    const photo = drafts.photo;
    const voice = drafts.voice;
    const text = drafts.text;
    if (!photo && !voice && !text) return;
    submittedRef.current = true;

    const form = new FormData();
    // Lazy-import the resizer so the canvas/Image cost stays off the
    // intro page's bundle. Voice/text users never pay for it.
    if (photo?.blob) {
      const { resizeJpegBlob } = await import('../../components/dci/imageResize');
      const resized = await resizeJpegBlob(photo.blob);
      form.append('photo', resized, 'photo.jpg');
    }
    if (voice?.blob) {
      form.append('voice', voice.blob, 'voice.webm');
    }
    if (text?.text) {
      form.append('text', text.text);
    }
    submit(form);
  };

  const onCorrect = async (next: {
    artifact_type: CaptureMode;
    subject?: string;
    topic?: string;
    deadline_iso?: string | null;
  }) => {
    const previous =
      classifications.find((c) => c.artifact_type === next.artifact_type) ?? null;
    await applyCorrection(next);
    emitDciKidEvent('dci.kid.corrected', {
      from: previous?.subject ?? null,
      to: next.subject ?? null,
    });
  };

  const goDone = () => {
    const completed = Math.round(
      (performance.now() - startedAtRef.current) / 1000,
    );
    emitDciKidEvent('dci.kid.completed_seconds', { seconds: completed });
    navigate('/checkin/done', {
      state: {
        classifications,
        completed_seconds: completed,
      },
    });
  };

  const switchMode = (next: CaptureMode) => {
    setParams({ mode: next });
  };

  const captured = useMemo(
    () =>
      Object.values(drafts).filter(Boolean) as CapturedDraft[],
    [drafts],
  );

  const hasAnything = captured.length > 0;
  const allModesUsed = VALID_MODES.every((m) => drafts[m] !== null);
  const sent = checkinId !== null;

  return (
    <main className="dci-checkin">
      <div className="dci-checkin__shell">
        <div className="dci-checkin__nav">
          <button
            type="button"
            className="dci-checkin__back"
            onClick={() => navigate('/checkin')}
          >
            ← Back
          </button>
          <span aria-hidden="true">{captured.length}/3</span>
        </div>

        {!sent && (
          <CapturePicker
            mode={mode}
            onCapture={(d) => onCapture(mode, d)}
          />
        )}

        {hasAnything && (
          <ArtifactCorrector
            artifacts={captured}
            classifications={classifications}
            classifying={sent && classifyMs === null}
            onCorrect={onCorrect}
          />
        )}

        {!sent && (
          <div className="dci-checkin__add-more">
            {VALID_MODES.filter((m) => m !== mode && drafts[m] === null).map(
              (m) => (
                <button
                  key={m}
                  type="button"
                  className="dci-checkin__add-more-chip"
                  onClick={() => switchMode(m)}
                  disabled={allModesUsed}
                >
                  + Add {m}
                </button>
              ),
            )}
          </div>
        )}

        {!sent && (
          <>
            <p className="dci-checkin__bill194">
              AI will read this to help your parents.
            </p>
            <button
              type="button"
              className="dci-checkin__send"
              disabled={!hasAnything || isSubmitting}
              onClick={sendToClassBridge}
            >
              {isSubmitting ? 'Sending…' : 'Send to ClassBridge'}
            </button>
            {submitError && (
              <div className="dci-checkin__error" role="alert">
                {submitError.message ?? 'Could not send. Try again?'}
              </div>
            )}
          </>
        )}

        {sent && (
          <button
            type="button"
            className="dci-checkin__send"
            onClick={goDone}
          >
            All good — finish
          </button>
        )}
      </div>
    </main>
  );
}

export default CheckInCapturePage;
