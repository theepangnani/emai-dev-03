import type { DciSubjectBullet } from '../../api/dciSummary';
import './EveningSummaryHero.css';

interface Props {
  kidName: string;
  date: string;
  bullets: DciSubjectBullet[];
}

/**
 * CB-DCI-001 M0-10 — 30-second-read evening hero card.
 *
 * Spec § 8: navy ink card, three subject bullets in plain text. No icons,
 * no badges, no cleverness — Priya needs to read this in the time it takes
 * to walk from the front door to the kitchen.
 */
export function EveningSummaryHero({ kidName, date, bullets }: Props) {
  const dateLabel = formatDate(date);
  return (
    <section
      className="dci-evening-hero"
      aria-labelledby="dci-evening-hero-title"
    >
      <header className="dci-evening-hero__header">
        <p className="dci-evening-hero__eyebrow">Tonight&rsquo;s 30-second read</p>
        <h2 className="dci-evening-hero__title" id="dci-evening-hero-title">
          {kidName} &middot; {dateLabel}
        </h2>
      </header>
      {bullets.length === 0 ? (
        <p className="dci-evening-hero__empty">
          No bullets in tonight&rsquo;s summary yet.
        </p>
      ) : (
        <ul className="dci-evening-hero__bullets">
          {bullets.map((bullet, idx) => (
            <li key={idx} className="dci-evening-hero__bullet">
              <span className="dci-evening-hero__subject">{bullet.subject}</span>
              <span className="dci-evening-hero__text">{bullet.text}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function formatDate(iso: string): string {
  // ISO 'yyyy-mm-dd' parsed without timezone surprises
  const [y, m, d] = iso.split('-').map(Number);
  if (!y || !m || !d) return iso;
  const dt = new Date(y, m - 1, d);
  return dt.toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });
}
