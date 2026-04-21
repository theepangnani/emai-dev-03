import { useEffect, useRef, useState } from 'react';
import { getWaitlistStats, type WaitlistStats } from '../../api/public';
import { IconPeople, IconQuote, IconShield, IconCheck } from './icons';
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
const COUNT_UP_RE_ANIMATE_THRESHOLD = 0.2;

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () =>
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  return reduced;
}

function badgeIcon(id: string) {
  if (id === 'canadian-stack') {
    return <IconCheck size={16} className="proof-wall__badge-icon" />;
  }
  return <IconShield size={16} className="proof-wall__badge-icon" />;
}

function CountUp({ target }: { target: number }) {
  const reduced = usePrefersReducedMotion();
  const rafRef = useRef<number | null>(null);
  const prevTargetRef = useRef<number>(0);

  // For reduced motion, render target directly without animation state.
  // For normal motion, animate via rAF into local state.
  const [animatedValue, setAnimatedValue] = useState(0);

  useEffect(() => {
    if (reduced) return;

    const prev = prevTargetRef.current;
    const delta = prev === 0 ? 1 : Math.abs(target - prev) / prev;
    const shouldAnimate = prev === 0 || delta > COUNT_UP_RE_ANIMATE_THRESHOLD;

    if (!shouldAnimate) {
      // Snap to new value without re-animating from 0. Defer via rAF to
      // avoid sync setState inside effect.
      rafRef.current = requestAnimationFrame(() => setAnimatedValue(target));
      prevTargetRef.current = target;
      return () => {
        if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      };
    }

    const from = prev === 0 ? 0 : prev;
    const start = performance.now();
    const step = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / COUNT_UP_DURATION_MS, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setAnimatedValue(Math.round(from + (target - from) * eased));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(step);
      }
    };
    rafRef.current = requestAnimationFrame(step);
    prevTargetRef.current = target;
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, [target, reduced]);

  return <>{reduced ? target : animatedValue}</>;
}

export function ProofWall() {
  const [stats, setStats] = useState<WaitlistStats | null>(null);
  const [testimonials, setTestimonials] = useState<Testimonial[]>([]);
  const [badges, setBadges] = useState<ComplianceBadge[]>([]);

  useEffect(() => {
    let cancelled = false;

    getWaitlistStats()
      .then((s) => { if (!cancelled) setStats(s); })
      .catch((e) => {
        console.error('ProofWall fetch failed:', e);
        if (!cancelled) setStats(null);
      });

    fetch('/content/proof-wall/testimonials.json')
      .then((r) => (r.ok ? r.json() : { testimonials: [] }))
      .then((data) => { if (!cancelled) setTestimonials(data.testimonials ?? []); })
      .catch((e) => {
        console.error('ProofWall fetch failed:', e);
        if (!cancelled) setTestimonials([]);
      });

    fetch('/content/proof-wall/compliance-badges.json')
      .then((r) => (r.ok ? r.json() : { badges: [] }))
      .then((data) => { if (!cancelled) setBadges(data.badges ?? []); })
      .catch((e) => {
        console.error('ProofWall fetch failed:', e);
        if (!cancelled) setBadges([]);
      });

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
          <div className="proof-wall__counter-row">
            <IconPeople size={24} className="proof-wall__counter-icon" />
            <span className="proof-wall__counter-total">
              <CountUp target={stats.total} />
            </span>
            <span className="proof-wall__counter-label">
              Ontario families on the waitlist
            </span>
          </div>
          {showMunicipality && topMunicipality && (
            <div className="proof-wall__counter-municipality">
              <span className="proof-wall__municipality-dot" aria-hidden="true" />
              {topMunicipality.count} from {topMunicipality.name}
            </div>
          )}
        </div>
      )}

      {consentedTestimonials.length > 0 && (
        <div className="proof-wall__testimonials" data-testid="proof-wall-testimonials">
          {consentedTestimonials.map((t) => (
            <figure key={t.id} className="proof-wall__testimonial">
              <IconQuote size={20} className="proof-wall__testimonial-icon" />
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
        <ul
          className="proof-wall__badges"
          aria-label="Compliance commitments"
          data-testid="proof-wall-badges"
        >
          {badges.map((b) => (
            <li key={b.id} className="proof-wall__badge-item">
              <a
                href={b.href}
                className="proof-wall__badge"
                aria-label={b.label}
              >
                {badgeIcon(b.id)}
                <span>{b.label}</span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default ProofWall;
