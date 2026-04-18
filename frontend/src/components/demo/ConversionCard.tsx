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
  const positionText =
    position > 0
      ? `You're #${position.toLocaleString()}${totalText} on the waitlist`
      : 'You\u2019re on the waitlist';

  return (
    <aside className="demo-conversion-card" aria-label="Verify your email to secure your spot">
      <p className="demo-conversion-position">{positionText}</p>
      <ul className="demo-conversion-benefits">
        <li>Early access when we open invites for your role</li>
        <li>Personalized study guides, flashcards, and Flash Tutor practice</li>
        <li>We never share your email or send spam</li>
      </ul>
      <button type="button" className="demo-conversion-cta" onClick={onVerify}>
        Verify my email to secure my spot
      </button>
    </aside>
  );
}

export default ConversionCard;
