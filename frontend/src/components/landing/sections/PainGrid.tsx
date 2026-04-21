import { useState, type ComponentType } from 'react';
import {
  IconParent,
  IconStudent,
  IconTeacher,
  IconShield,
  IconArrowRight,
} from '../../demo/icons';
import type { IconProps } from '../../demo/icons';
import { InstantTrialModal } from '../../demo/InstantTrialModal';
import './PainGrid.css';

/**
 * CB-LAND-001 S4 — Pain section (§6.136.1 §2).
 *
 * Mindgrasp-inspired pain-empathy block, adapted to ClassBridge's 4 roles.
 * Renders a kicker + italic-accented headline, 4 role-quote cards, and a
 * trailing "better way" strip with a demo CTA that opens the InstantTrialModal.
 *
 * Tokens are scoped under `[data-landing="v2"]`; see
 * `frontend/src/components/landing/README.md`.
 */

interface PainCard {
  id: 'parent' | 'student' | 'teacher' | 'admin';
  role: string;
  quote: string;
  Icon: ComponentType<IconProps>;
  tintClass: string;
}

const CARDS: PainCard[] = [
  {
    id: 'parent',
    role: 'Parent',
    quote: "I miss half my kid's emails",
    Icon: IconParent,
    tintClass: 'landing-pain__tint--peach',
  },
  {
    id: 'student',
    role: 'Student',
    quote: 'I re-read chapters and still forget',
    Icon: IconStudent,
    tintClass: 'landing-pain__tint--mint',
  },
  {
    id: 'teacher',
    role: 'Teacher',
    quote: 'Parents never see my announcements',
    Icon: IconTeacher,
    tintClass: 'landing-pain__tint--lavender',
  },
  {
    id: 'admin',
    role: 'Admin',
    quote: 'No visibility across homes',
    Icon: IconShield,
    tintClass: 'landing-pain__tint--pink',
  },
];

export function PainGrid() {
  const [demoOpen, setDemoOpen] = useState(false);

  return (
    <section data-landing="v2" className="landing-pain" aria-labelledby="landing-pain-heading">
      <div className="landing-pain__inner">
        <p className="landing-pain__kicker">Sound familiar?</p>
        <h2 id="landing-pain-heading" className="landing-pain__heading">
          School communication is <em>broken.</em>
        </h2>

        <ul className="landing-pain__grid" role="list">
          {CARDS.map(({ id, role, quote, Icon, tintClass }) => (
            <li key={id} className="landing-pain__card">
              <span className={`landing-pain__icon ${tintClass}`} aria-hidden="true">
                <Icon size={24} />
              </span>
              <span className="landing-pain__badge">{role}</span>
              <blockquote className="landing-pain__quote">&ldquo;{quote}&rdquo;</blockquote>
            </li>
          ))}
        </ul>

        <div className="landing-pain__strip">
          <p className="landing-pain__strip-text">
            <strong>There&rsquo;s a better way.</strong> See how ClassBridge turns chaos into one
            calm stream for every family.
          </p>
          <button
            type="button"
            className="landing-pain__cta"
            onClick={() => setDemoOpen(true)}
          >
            Try the 30-second demo
            <IconArrowRight size={18} className="landing-pain__cta-arrow" />
          </button>
        </div>
      </div>

      {demoOpen && <InstantTrialModal onClose={() => setDemoOpen(false)} />}
    </section>
  );
}

// Glob-registry contract for landing-v2 sections.
export const section = { id: 'pain', order: 20, component: PainGrid };
