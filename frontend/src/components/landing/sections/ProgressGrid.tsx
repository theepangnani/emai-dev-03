/**
 * CB-LAND-001 S8 — Progress tracking grid (2×2)
 *
 * §6.136.1 §7 — Progress tracking section of the landing-v2 spine.
 * Reference: docs/design/landing-v2-reference/07-progress-tracking.png
 *
 * Scoped under [data-landing="v2"] — tokens live in index.css.
 */
import { Activity, Flame, User, PlayCircle } from 'lucide-react';
import type { ComponentType, SVGProps } from 'react';
import './ProgressGrid.css';

type IconComponent = ComponentType<SVGProps<SVGSVGElement>>;

type ProgressCard = {
  title: string;
  body: string;
  Icon: IconComponent;
  tint: 'lavender' | 'peach' | 'mint' | 'pink';
};

const CARDS: ProgressCard[] = [
  {
    title: 'Real-Time Activity Feed',
    body: 'See every upload, quiz, and message as it happens.',
    Icon: Activity,
    tint: 'lavender',
  },
  {
    title: 'Streak / XP',
    body: 'Celebrate consistency with Flash Tutor streaks and badges.',
    Icon: Flame,
    tint: 'peach',
  },
  {
    title: 'Per-Child Focus Panel',
    body: 'Each child has their own week-at-a-glance — overdue, due today, coming up.',
    Icon: User,
    tint: 'mint',
  },
  {
    title: 'Resume Where You Left Off',
    body: 'Pick up Flash Tutor, quizzes, and study guides from anywhere.',
    Icon: PlayCircle,
    tint: 'pink',
  },
];

export function ProgressGrid() {
  return (
    <section data-landing="v2" className="landing-progress">
      <div className="landing-progress__inner">
        <h2 className="landing-progress__headline">
          Progress for <em>every child, every week.</em>
        </h2>
        <ul className="landing-progress__grid" role="list">
          {CARDS.map(({ title, body, Icon, tint }) => (
            <li key={title} className="landing-progress__card">
              <span
                className={`landing-progress__icon landing-progress__icon--${tint}`}
                aria-hidden="true"
              >
                <Icon width={24} height={24} strokeWidth={2} />
              </span>
              <div className="landing-progress__card-body">
                <h3 className="landing-progress__card-title">{title}</h3>
                <p className="landing-progress__card-text">{body}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export const section = {
  id: 'progress',
  order: 60,
  component: ProgressGrid,
};

export default ProgressGrid;
