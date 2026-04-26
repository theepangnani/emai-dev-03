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
    onSubmitSettled,
  } = useDciCheckin();
  const submittedRef = useRef(false);
  const [preparing, setPreparing] = useState(false);

  // Tie `preparing` release to the mutation's onSettled (issue #4195) so the
  // CTA stays "Sending…" through the entire submit cycle without flickering
  // back to enabled between our local resize-finished and isPending=true.
  useEffect(() => {
    onSubmitSettled(() => setPreparing(false));
    return () => onSubmitSettled(null);
  }, [onSubmitSettled]);
  // Track every preview URL we allocate so the unmount cleanup can revoke
  // them all even if the latest `drafts` value isn't captured by the
  // mount-only effect closure.
  const previewUrlsRef = useRef<Set<string>>(new Set());

  // Telemetry: classify_ms is reported once per submit, when polling settles.
  useEffect(() => {
    if (classifyMs !== null) {
      emitDciKidEvent('dci.kid.classify_ms', { ms: classifyMs });
    }
  }, [classifyMs]);

  // Revoke every preview URL we ever allocated when the page unmounts.
  // Uses a ref-tracked set so we don't race the stale-`drafts` closure
  // problem of a `[]`-dep cleanup effect.
  useEffect(() => {
    const urls = previewUrlsRef.current;
    return () => {
      urls.forEach((u) => URL.revokeObjectURL(u));
      urls.clear();
    };
  }, []);

  const onCapture = (
    capturedMode: CaptureMode,
    data: { blob?: Blob; text?: string },
  ) => {
    const nextUrl = data.blob ? URL.createObjectURL(data.blob) : undefined;
    if (nextUrl) previewUrlsRef.current.add(nextUrl);
    setDrafts((prev) => {
      // Revoke the previous preview URL for this slot before allocating a new one.
      const previous = prev[capturedMode];
      if (previous?.previewUrl) {
        URL.revokeObjectURL(previous.previewUrl);
        previewUrlsRef.current.delete(previous.previewUrl);
      }
      return {
        ...prev,
        [capturedMode]: {
          artifact_type: capturedMode,
          blob: data.blob,
          text: data.text,
          previewUrl: nextUrl,
          textSnippet: data.text,
        },
      };
    });
  };

  const sendToClassBridge = async () => {
    if (preparing || submittedRef.current) return;
    const photo = drafts.photo;
    const voice = drafts.voice;
    const text = drafts.text;
    if (!photo && !voice && !text) return;
    setPreparing(true);
    submittedRef.current = true;

    try {
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
      // NOTE: `setPreparing(false)` is intentionally NOT called here. It now
      // fires in the mutation's onSettled (wired via `onSubmitSettled`
      // above) so the CTA stays disabled across the full submit lifecycle.
    } catch (err) {
      // Resize/encode threw before we ever called submit() — release the
      // preparing latch ourselves since onSettled won't fire.
      setPreparing(false);
      submittedRef.current = false;
      throw err;
    }
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
    // NOTE: this measures "send-to-done click" timing (kid pressed the finish
    // button), not "Done screen seen" timing — the Done screen is reached on
    // the next render after navigate().
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
              disabled={!hasAnything || isSubmitting || preparing}
              onClick={sendToClassBridge}
            >
              {isSubmitting || preparing ? 'Sending…' : 'Send to ClassBridge'}
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
