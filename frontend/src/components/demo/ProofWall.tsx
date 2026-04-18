import { useEffect, useRef, useState } from 'react';
import { getWaitlistStats, type WaitlistStats } from '../../api/public';
import './ProofWall.css';

interface Testimonial {
  id: string;
  quote: string;
  role: string;
  city: string;
  status?: string;
}

interface ComplianceBadge {
  id: string;
  label: string;
  href: string;
}

const COUNT_UP_DURATION_MS = 1200;
const MUNICIPALITY_MIN_COUNT = 3;

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function CountUp({ target }: { target: number }) {
  const reduced = prefersReducedMotion();
  const [value, setValue] = useState(() => (reduced ? target : 0));
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (reduced) return;
    const start = performance.now();
    const step = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / COUNT_UP_DURATION_MS, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(target * eased));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(step);
      }
    };
    rafRef.current = requestAnimationFrame(step);
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, [target, reduced]);

  return <>{value}</>;
}

export function ProofWall() {
  const [stats, setStats] = useState<WaitlistStats | null>(null);
  const [testimonials, setTestimonials] = useState<Testimonial[]>([]);
  const [badges, setBadges] = useState<ComplianceBadge[]>([]);

  useEffect(() => {
    let cancelled = false;

    getWaitlistStats()
      .then((s) => { if (!cancelled) setStats(s); })
      .catch(() => { if (!cancelled) setStats(null); });

    fetch('/content/proof-wall/testimonials.json')
      .then((r) => (r.ok ? r.json() : { testimonials: [] }))
      .then((data) => { if (!cancelled) setTestimonials(data.testimonials ?? []); })
      .catch(() => { if (!cancelled) setTestimonials([]); });

    fetch('/content/proof-wall/compliance-badges.json')
      .then((r) => (r.ok ? r.json() : { badges: [] }))
      .then((data) => { if (!cancelled) setBadges(data.badges ?? []); })
      .catch(() => { if (!cancelled) setBadges([]); });

    return () => { cancelled = true; };
  }, []);

  const consentedTestimonials = testimonials.filter((t) => t.status !== 'pending_consent');
  const topMunicipality = stats?.by_municipality?.[0];
  const showMunicipality =
    topMunicipality != null && topMunicipality.count >= MUNICIPALITY_MIN_COUNT;

  return (
    <section className="proof-wall" aria-label="Proof wall">
      {stats?.total != null && (
        <div className="proof-wall__counter" data-testid="proof-wall-counter">
          <div className="proof-wall__counter-total">
            <CountUp target={stats.total} />
          </div>
          <div className="proof-wall__counter-label">
            Ontario families on the waitlist
          </div>
          {showMunicipality && topMunicipality && (
            <div className="proof-wall__counter-municipality">
              {topMunicipality.count} from {topMunicipality.name}
            </div>
          )}
        </div>
      )}

      {consentedTestimonials.length > 0 && (
        <div className="proof-wall__testimonials" data-testid="proof-wall-testimonials">
          {consentedTestimonials.map((t) => (
            <figure key={t.id} className="proof-wall__testimonial">
              <blockquote className="proof-wall__testimonial-quote">
                {t.quote}
              </blockquote>
              <figcaption className="proof-wall__testimonial-attribution">
                {`\u2014 ${t.role}, ${t.city}`}
              </figcaption>
            </figure>
          ))}
        </div>
      )}

      {badges.length > 0 && (
        <div
          className="proof-wall__badges"
          role="list"
          aria-label="Compliance certifications"
          data-testid="proof-wall-badges"
        >
          {badges.map((b) => (
            <a
              key={b.id}
              role="listitem"
              href={b.href}
              className="proof-wall__badge"
              aria-label={b.label}
            >
              {b.label}
            </a>
          ))}
        </div>
      )}
    </section>
  );
}

export default ProofWall;
