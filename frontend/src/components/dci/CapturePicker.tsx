/**
 * CapturePicker — wraps the three input modes on Screen 2:
 *   - photo:  getUserMedia + A4 guide overlay + capture
 *   - voice:  MediaRecorder (16 kHz mono opus) + level meter + ≤60s cap
 *   - text:   <textarea maxlength=280>
 *
 * The component owns the device-side capture state and yields a Blob (or a
 * string for text) up to the page via `onCapture`. Resize/encoding is the
 * page's job — keeps this file under one responsibility.
 *
 * NOTE on browser compat: getUserMedia + MediaRecorder are both gated. If
 * either is missing (Safari ≤ 14, older mobile browsers), we render a
 * graceful fallback message instead of crashing the page.
 */
import { useEffect, useRef, useState } from 'react';
import './CapturePicker.css';

export type CaptureMode = 'photo' | 'voice' | 'text';

export interface CapturePickerProps {
  mode: CaptureMode;
  onCapture: (data: { blob?: Blob; text?: string }) => void;
  /** Bytes — used for voice cap (default 60s × ~24kbps ≈ 180KB). */
  maxVoiceSeconds?: number;
}

const TEXT_MAX = 280;

export function CapturePicker({
  mode,
  onCapture,
  maxVoiceSeconds = 60,
}: CapturePickerProps) {
  if (mode === 'photo') {
    return <PhotoCapture onCapture={onCapture} />;
  }
  if (mode === 'voice') {
    return <VoiceCapture onCapture={onCapture} maxSeconds={maxVoiceSeconds} />;
  }
  return <TextCapture onCapture={onCapture} />;
}

// --- Photo --------------------------------------------------------------

function PhotoCapture({
  onCapture,
}: {
  onCapture: (d: { blob?: Blob }) => void;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const snapshotRef = useRef<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<string | null>(null);

  useEffect(() => {
    const supported =
      typeof navigator !== 'undefined' &&
      navigator.mediaDevices &&
      typeof navigator.mediaDevices.getUserMedia === 'function';
    if (!supported) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: surface unsupported-browser fallback synchronously
      setError('This browser does not support webcam capture.');
      return;
    }
    let cancelled = false;
    navigator.mediaDevices
      // facingMode is "ideal" rather than required so desktops without a rear
      // camera still get a working stream (otherwise getUserMedia rejects).
      .getUserMedia({
        video: { facingMode: { ideal: 'environment' } },
        audio: false,
      })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      })
      .catch((err) => {
        setError(err?.message ?? 'Could not start camera.');
      });
    return () => {
      cancelled = true;
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
    };
  }, []);

  const snap = () => {
    const video = videoRef.current;
    if (!video) return;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 1024;
    canvas.height = video.videoHeight || 1448; // ≈ A4 4:3-ish
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        // Revoke any prior snapshot URL before allocating a new one so we
        // don't leak object URLs across re-snaps.
        if (snapshotRef.current) {
          URL.revokeObjectURL(snapshotRef.current);
        }
        const next = URL.createObjectURL(blob);
        snapshotRef.current = next;
        setSnapshot(next);
        onCapture({ blob });
      },
      'image/jpeg',
      0.92,
    );
  };

  // Final cleanup: revoke whatever snapshot URL is still around when the
  // PhotoCapture unmounts (mode switch, page nav, etc.).
  useEffect(() => {
    return () => {
      if (snapshotRef.current) {
        URL.revokeObjectURL(snapshotRef.current);
        snapshotRef.current = null;
      }
    };
  }, []);

  if (error) {
    return (
      <div className="dci-capture dci-capture--error" role="alert">
        {error}
      </div>
    );
  }

  return (
    <div className="dci-capture dci-capture--photo">
      <div className="dci-capture__viewport">
        {snapshot ? (
          <img src={snapshot} alt="Captured" className="dci-capture__preview" />
        ) : (
          <>
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className="dci-capture__video"
              data-testid="dci-photo-video"
            />
            {/* A4 guide overlay (~1:1.414 aspect) */}
            <div className="dci-capture__guide" aria-hidden="true" />
          </>
        )}
      </div>
      <button
        type="button"
        className="dci-capture__primary"
        onClick={snap}
        disabled={!!snapshot}
      >
        {snapshot ? 'Captured' : 'Snap photo'}
      </button>
    </div>
  );
}

// --- Voice --------------------------------------------------------------

function VoiceCapture({
  onCapture,
  maxSeconds,
}: {
  onCapture: (d: { blob?: Blob }) => void;
  maxSeconds: number;
}) {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number | null>(null);
  const [recording, setRecording] = useState(false);
  const [level, setLevel] = useState(0);
  const [seconds, setSeconds] = useState(0);
  const [recordedUrl, setRecordedUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    return () => stopAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stopAll = () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      try {
        recorderRef.current.stop();
      } catch {
        /* ignore */
      }
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
      audioCtxRef.current.close().catch(() => {});
    }
    audioCtxRef.current = null;
    analyserRef.current = null;
  };

  const start = async () => {
    setError(null);
    const supported =
      typeof navigator !== 'undefined' &&
      navigator.mediaDevices &&
      typeof navigator.mediaDevices.getUserMedia === 'function' &&
      typeof window.MediaRecorder !== 'undefined';
    if (!supported) {
      setError('This browser does not support voice recording.');
      return;
    }
    try {
      // NOTE: sampleRate: 16_000 is best-effort — most browsers ignore the
      // hint and capture at the device's native rate (typically 48 kHz). The
      // backend (M0-5) downsamples to 16 kHz before STT, so we don't enforce.
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16_000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;
      // Pick a mime that browsers actually honor — opus first, fall back.
      const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']
        .find((m) => MediaRecorder.isTypeSupported(m));
      const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      recorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: mime ?? 'audio/webm',
        });
        setRecordedUrl(URL.createObjectURL(blob));
        onCapture({ blob });
      };
      recorder.start(250);
      startedAtRef.current = performance.now();
      setRecording(true);
      setSeconds(0);

      // Level meter via WebAudio analyser.
      const AudioCtor =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext?: typeof AudioContext })
          .webkitAudioContext;
      if (AudioCtor) {
        const ctx = new AudioCtor();
        audioCtxRef.current = ctx;
        const src = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        src.connect(analyser);
        analyserRef.current = analyser;
        const buf = new Uint8Array(analyser.frequencyBinCount);
        const tick = () => {
          if (!analyserRef.current) return;
          analyserRef.current.getByteFrequencyData(buf);
          let sum = 0;
          for (let i = 0; i < buf.length; i++) sum += buf[i];
          setLevel(Math.min(1, sum / buf.length / 128));
          if (startedAtRef.current !== null) {
            const elapsed = (performance.now() - startedAtRef.current) / 1000;
            setSeconds(elapsed);
            if (elapsed >= maxSeconds) {
              stop();
              return;
            }
          }
          rafRef.current = requestAnimationFrame(tick);
        };
        rafRef.current = requestAnimationFrame(tick);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Could not start microphone.',
      );
      stopAll();
      setRecording(false);
    }
  };

  const stop = () => {
    setRecording(false);
    stopAll();
  };

  if (error) {
    return (
      <div className="dci-capture dci-capture--error" role="alert">
        {error}
      </div>
    );
  }

  return (
    <div className="dci-capture dci-capture--voice">
      <div className="dci-capture__meter" aria-hidden="true">
        <div
          className="dci-capture__meter-bar"
          style={{ width: `${Math.round(level * 100)}%` }}
        />
      </div>
      <div className="dci-capture__seconds">
        {Math.floor(seconds)} / {maxSeconds}s
      </div>
      {recordedUrl && (
        <audio
          src={recordedUrl}
          controls
          className="dci-capture__playback"
          data-testid="dci-voice-playback"
        />
      )}
      {!recording ? (
        <button
          type="button"
          className="dci-capture__primary"
          onClick={start}
        >
          {recordedUrl ? 'Record again' : 'Record voice'}
        </button>
      ) : (
        <button
          type="button"
          className="dci-capture__stop"
          onClick={stop}
        >
          Stop
        </button>
      )}
    </div>
  );
}

// --- Text ---------------------------------------------------------------

function TextCapture({
  onCapture,
}: {
  onCapture: (d: { text?: string }) => void;
}) {
  const [value, setValue] = useState('');
  const remaining = TEXT_MAX - value.length;
  return (
    <div className="dci-capture dci-capture--text">
      <textarea
        maxLength={TEXT_MAX}
        value={value}
        placeholder="Today we learned…"
        aria-label="Tell ClassBridge about your day"
        className="dci-capture__textarea"
        onChange={(e) => {
          setValue(e.target.value);
          onCapture({ text: e.target.value });
        }}
      />
      <div
        className={`dci-capture__counter${
          remaining < 20 ? ' dci-capture__counter--low' : ''
        }`}
        aria-live="polite"
      >
        {remaining} characters left
      </div>
    </div>
  );
}

export default CapturePicker;
