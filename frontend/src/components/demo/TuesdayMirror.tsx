import { useEffect, useMemo, useState } from 'react';
import { useTuesdayMirrorAnimation } from '../../hooks/useTuesdayMirrorAnimation';
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
  } catch {
    /* ignore */
  }
  return 'yrdsb';
}

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
  const [error, setError] = useState<string | null>(null);
  const [mobileTab, setMobileTab] = useState<'without' | 'with'>('without');
  const reducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, board);
    } catch {
      /* ignore */
    }
  }, [board]);

  useEffect(() => {
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- resetting on board change
    setContent(null);
    setError(null);
    fetch(`/content/tuesday-mirror/${board}.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<TuesdayMirrorContent>;
      })
      .then((data) => {
        if (!cancelled) setContent(data);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [board]);

  const beats = useMemo(() => content?.beats ?? [], [content]);
  const visible = useTuesdayMirrorAnimation(beats.length, reducedMotion);

  const handleCtaClick = () => {
    const el = document.getElementById('instant-trial');
    if (el) el.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth' });
  };

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

      {error && <p className="tm-error" role="alert">Could not load storyboard ({error}).</p>}

      <div className="tm-mobile-tabs" role="tablist" aria-label="Compare Tuesdays">
        <button
          type="button"
          role="tab"
          aria-selected={mobileTab === 'without'}
          className={`tm-tab ${mobileTab === 'without' ? 'tm-tab-active' : ''}`}
          onClick={() => setMobileTab('without')}
        >
          Without ClassBridge
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mobileTab === 'with'}
          className={`tm-tab ${mobileTab === 'with' ? 'tm-tab-active' : ''}`}
          onClick={() => setMobileTab('with')}
        >
          With ClassBridge
        </button>
      </div>

      <div className={`tm-grid tm-mobile-${mobileTab}`}>
        <div className="tm-column tm-column-without" aria-label="A Tuesday without ClassBridge">
          <h3 className="tm-column-title">A Tuesday without ClassBridge</h3>
          <ol className="tm-beats" aria-live="polite">
            {beats.map((beat, i) => (
              <li
                key={`without-${beat.index}`}
                className={`tm-beat tm-beat-without ${visible.includes(i) ? 'tm-beat-visible' : ''}`}
                data-testid={`beat-without-${beat.index}`}
                aria-hidden={!visible.includes(i)}
              >
                <span className="tm-beat-time">{beat.timestamp}</span>
                <span className="tm-beat-text">{beat.without}</span>
              </li>
            ))}
          </ol>
        </div>

        <div className="tm-column tm-column-with" aria-label="A Tuesday with ClassBridge">
          <h3 className="tm-column-title">A Tuesday with ClassBridge</h3>
          <ol className="tm-beats" aria-live="polite">
            {beats.map((beat, i) => (
              <li
                key={`with-${beat.index}`}
                className={`tm-beat tm-beat-with ${visible.includes(i) ? 'tm-beat-visible' : ''}`}
                data-testid={`beat-with-${beat.index}`}
                aria-hidden={!visible.includes(i)}
              >
                <span className="tm-beat-icon" aria-hidden="true">&#10003;</span>
                <span className="tm-beat-time">{beat.timestamp}</span>
                <span className="tm-beat-text">{beat.with}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <div className="tm-cta-wrap">
        <button type="button" className="tm-cta" onClick={handleCtaClick}>
          Sounds familiar?
        </button>
      </div>
    </section>
  );
}
