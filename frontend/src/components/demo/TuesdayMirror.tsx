import { useEffect, useMemo, useState } from 'react';
import { useTuesdayMirrorAnimation } from '../../hooks/useTuesdayMirrorAnimation';
import { IconCheck, IconClock } from './icons';
import './TuesdayMirror.css';

export type TuesdayMirrorBoard = 'yrdsb' | 'tdsb' | 'ddsb' | 'pdsb' | 'ocdsb';

interface Beat {
  index: number;
  timestamp: string;
  without: string;
  with: string;
}

interface TuesdayMirrorContent {
  board: string;
  display_name: string;
  tools_named: string[];
  beats: Beat[];
}

const BOARDS: { value: TuesdayMirrorBoard; label: string }[] = [
  { value: 'yrdsb', label: 'YRDSB' },
  { value: 'tdsb', label: 'TDSB' },
  { value: 'ddsb', label: 'DDSB' },
  { value: 'pdsb', label: 'PDSB' },
  { value: 'ocdsb', label: 'OCDSB' },
];

const STORAGE_KEY = 'classbridge_demo_board';

function readStoredBoard(): TuesdayMirrorBoard {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && BOARDS.some((b) => b.value === stored)) {
      return stored as TuesdayMirrorBoard;
    }
  } catch { /* ignore */ }
  return 'yrdsb';
}

const IconWarn = ({ size = 16 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v5M12 16h.01" />
  </svg>
);

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState<boolean>(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });
  useEffect(() => {
    if (!window.matchMedia) return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener?.('change', handler);
    return () => mq.removeEventListener?.('change', handler);
  }, []);
  return reduced;
}

export function TuesdayMirror() {
  const [board, setBoard] = useState<TuesdayMirrorBoard>(readStoredBoard);
  const [content, setContent] = useState<TuesdayMirrorContent | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [mobileTab, setMobileTab] = useState<'without' | 'with'>('without');
  const reducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    try { window.localStorage.setItem(STORAGE_KEY, board); } catch { /* ignore */ }
  }, [board]);

  useEffect(() => {
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- resetting on board change
    setLoading(true);
    setError(null);
    fetch(`/content/tuesday-mirror/${board}.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<TuesdayMirrorContent>;
      })
      .then((data) => { if (!cancelled) { setContent(data); setLoading(false); } })
      .catch((e: Error) => { if (!cancelled) { setError(e.message); setLoading(false); } });
    return () => { cancelled = true; };
  }, [board]);

  const beats = useMemo(() => content?.beats ?? [], [content]);
  const toolsNamed = content?.tools_named ?? [];
  const visible = useTuesdayMirrorAnimation(beats.length, reducedMotion);

  const handleCtaClick = () => {
    const el = document.getElementById('instant-trial');
    if (el) el.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth' });
  };

  const renderBeat = (beat: Beat, i: number, variant: 'without' | 'with') => (
    <li
      key={`${variant}-${beat.index}`}
      className={`tm-beat tm-beat-${variant} ${visible.includes(i) ? 'tm-beat-visible' : ''}`}
      data-testid={`beat-${variant}-${beat.index}`}
      aria-hidden={!visible.includes(i)}
    >
      <span className="tm-time-chip">
        <IconClock size={14} />
        <span className="tm-beat-time">{beat.timestamp}</span>
      </span>
      <span className="tm-beat-text">{variant === 'without' ? beat.without : beat.with}</span>
    </li>
  );

  return (
    <section className="tuesday-mirror" aria-labelledby="tuesday-mirror-heading">
      <div className="tm-header">
        <h2 id="tuesday-mirror-heading" className="tm-title">A Tuesday in a parent's life</h2>
        <label className="tm-board-selector">
          <span className="tm-board-label">School board</span>
          <select
            className="tm-board-select"
            value={board}
            onChange={(e) => setBoard(e.target.value as TuesdayMirrorBoard)}
            aria-label="Select school board"
          >
            {BOARDS.map((b) => (
              <option key={b.value} value={b.value}>{b.label}</option>
            ))}
          </select>
        </label>
      </div>

      {error ? (
        <p className="tm-error" role="alert">Could not load storyboard ({error}).</p>
      ) : (
        <>
          {toolsNamed.length > 0 && (
            <p className="tm-tools-named">Featuring: {toolsNamed.join(', ')}</p>
          )}

          <div className="tm-mobile-tabs" role="tablist" aria-label="Compare Tuesdays">
            <button
              type="button" role="tab" id="tm-tab-without"
              aria-selected={mobileTab === 'without'} aria-controls="tm-panel-without"
              tabIndex={mobileTab === 'without' ? 0 : -1}
              className={`tm-tab ${mobileTab === 'without' ? 'tm-tab-active' : ''}`}
              onClick={() => setMobileTab('without')}
              onKeyDown={(e) => {
                if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                  e.preventDefault();
                  setMobileTab('with');
                  document.getElementById('tm-tab-with')?.focus();
                }
              }}
            >Without ClassBridge</button>
            <button
              type="button" role="tab" id="tm-tab-with"
              aria-selected={mobileTab === 'with'} aria-controls="tm-panel-with"
              tabIndex={mobileTab === 'with' ? 0 : -1}
              className={`tm-tab ${mobileTab === 'with' ? 'tm-tab-active' : ''}`}
              onClick={() => setMobileTab('with')}
              onKeyDown={(e) => {
                if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
                  e.preventDefault();
                  setMobileTab('without');
                  document.getElementById('tm-tab-without')?.focus();
                }
              }}
            >With ClassBridge</button>
          </div>

          <div className={`tm-grid tm-mobile-${mobileTab} ${loading ? 'tm-grid--loading' : ''}`}>
            <div id="tm-panel-without" className="tm-column tm-column-without"
              role="tabpanel" aria-labelledby="tm-tab-without" tabIndex={0}>
              <h3 className="tm-column-title">
                <span className="tm-column-icon tm-column-icon--warn"><IconWarn size={16} /></span>
                A Tuesday without ClassBridge
              </h3>
              <ol className="tm-beats" aria-live="polite">
                {beats.map((b, i) => renderBeat(b, i, 'without'))}
              </ol>
            </div>

            <div id="tm-panel-with" className="tm-column tm-column-with"
              role="tabpanel" aria-labelledby="tm-tab-with" tabIndex={0}>
              <h3 className="tm-column-title">
                <span className="tm-column-icon tm-column-icon--check"><IconCheck size={16} /></span>
                A Tuesday with ClassBridge
              </h3>
              <ol className="tm-beats" aria-live="polite">
                {beats.map((b, i) => renderBeat(b, i, 'with'))}
              </ol>
            </div>
          </div>

          <div className="tm-cta-wrap">
            <button type="button" className="tm-cta" onClick={handleCtaClick}>
              Sounds familiar?
            </button>
          </div>
        </>
      )}
    </section>
  );
}
