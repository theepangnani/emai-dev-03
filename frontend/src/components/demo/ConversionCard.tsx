import { IconArrowRight, IconCheck, IconMail } from './icons';

interface ConversionCardProps {
  /** Tentative waitlist position (e.g., 347). */
  position: number;
  /** Total waitlist size used for the "of N" phrase (e.g., 1204). */
  totalPreview?: number;
  /** Fires when the CTA is clicked. Parent handles verify flow. */
  onVerify: () => void;
}

/**
 * Post-generation conversion card that shows the tentative waitlist
 * position, 3 benefit bullets, and a primary "verify email" CTA.
 */
export function ConversionCard({ position, totalPreview, onVerify }: ConversionCardProps) {
  const totalText = totalPreview && totalPreview > position ? ` of ${totalPreview.toLocaleString()}` : '';
  const hasPosition = position > 0;

  const benefits = [
    'Early access when we open invites for your role',
    'Personalized study guides, flashcards, and Flash Tutor practice',
    'We never share your email or send spam',
  ];

  return (
    <aside className="demo-conversion-card" aria-label="Verify your email to secure your spot">
      <div className="demo-conversion-card__header">
        <span className="demo-conversion-card__icon" aria-hidden="true">
          <IconCheck size={22} aria-hidden />
        </span>
        {hasPosition ? (
          <p className="demo-conversion-position">
            You&rsquo;re{' '}
            <span className="demo-conversion-position-pill">#{position.toLocaleString()}</span>
            {totalText ? <span className="demo-conversion-position-total">{totalText}</span> : null}
            {' '}on the waitlist
          </p>
        ) : (
          <p className="demo-conversion-position">You&rsquo;re on the waitlist</p>
        )}
      </div>
      <ul className="demo-conversion-benefits">
        {benefits.map((text) => (
          <li key={text}>
            <IconCheck size={16} aria-hidden />
            <span>{text}</span>
          </li>
        ))}
      </ul>
      <button type="button" className="demo-conversion-cta" onClick={onVerify}>
        <IconMail size={18} aria-hidden />
        <span>Verify my email to secure my spot</span>
        <IconArrowRight size={18} aria-hidden />
      </button>
    </aside>
  );
}

export default ConversionCard;
