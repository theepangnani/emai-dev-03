/**
 * ComparisonSplit — CB-LAND-001 S7 (§6.136.1 §6).
 *
 * Red/green split: "The old homework routine vs ClassBridge."
 * Two columns (stack on mobile). Coral-accented left (✗ "The Old Way"),
 * mint-accented right (✓ "The ClassBridge Way"). Five paired rows.
 * DemoMascot (mood="greeting") centered between columns as a visual divider.
 *
 * Scoped under [data-landing="v2"] so landing-v2 tokens resolve. Do not use
 * outside the landing-v2 tree. Reference: docs/design/landing-v2-reference/
 * 06-old-vs-new.png. Related: epic #3800, issue #3807.
 */

import { DemoMascot } from '../../demo/DemoMascot';
import { useSectionViewTracker } from '../useSectionViewTracker';
import './ComparisonSplit.css';

interface ComparisonRow {
  old: string;
  next: string;
}

const ROWS: ComparisonRow[] = [
  { old: 'Scattered Gmail threads', next: 'Daily AI digest' },
  { old: 'Endless re-reading', next: 'Flash Tutor' },
  { old: 'Parent out of loop', next: 'Parent digest' },
  { old: 'Paper scans lost', next: 'AI study guides' },
  { old: 'One-shot quizzes', next: 'Adaptive difficulty' },
];

export function ComparisonSplit() {
  const sectionRef = useSectionViewTracker<HTMLElement>('compare');
  return (
    <section ref={sectionRef} data-landing="v2" className="landing-compare">
      <div className="landing-compare__inner">
        <h2 className="landing-compare__title">
          The old homework routine <em>vs</em> ClassBridge.
        </h2>

        <div className="landing-compare__grid">
          <div
            className="landing-compare__col landing-compare__col--old"
            aria-labelledby="landing-compare-old"
          >
            <h3 id="landing-compare-old" className="landing-compare__col-title">
              The Old Way
            </h3>
            <ul className="landing-compare__list">
              {ROWS.map((row) => (
                <li key={`old-${row.old}`} className="landing-compare__pill landing-compare__pill--old">
                  <span className="landing-compare__glyph" aria-hidden="true">
                    ✗
                  </span>
                  <span className="landing-compare__label">{row.old}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="landing-compare__mascot" aria-hidden="true">
            <DemoMascot size={72} mood="greeting" />
          </div>

          <div
            className="landing-compare__col landing-compare__col--new"
            aria-labelledby="landing-compare-new"
          >
            <h3 id="landing-compare-new" className="landing-compare__col-title">
              The ClassBridge Way
            </h3>
            <ul className="landing-compare__list">
              {ROWS.map((row) => (
                <li key={`new-${row.next}`} className="landing-compare__pill landing-compare__pill--new">
                  <span className="landing-compare__glyph" aria-hidden="true">
                    ✓
                  </span>
                  <span className="landing-compare__label">{row.next}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

export const section = {
  id: 'compare',
  order: 50,
  component: ComparisonSplit,
};

export default ComparisonSplit;
