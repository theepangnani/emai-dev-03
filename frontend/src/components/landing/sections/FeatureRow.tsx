/**
 * CB-LAND-001 S5 — FeatureRow
 *
 * A single alternating pastel feature row: left text column (icon square +
 * serif-italic headline + 3-line body + "Learn more" link) + right product-
 * screenshot mockup.
 *
 * Layout direction is driven by `reversed` so the container can flip every
 * other row. Background comes from the `variant` prop → S1 token
 * `--color-row-{variant}`.
 *
 * Reference: docs/design/landing-v2-reference/04a-feature-rows-notes-summary.png
 */

import './FeatureRow.css';
import type { FeatureRowContent } from '../content/features';

export interface FeatureRowProps {
  content: FeatureRowContent;
  /** When true, text sits on the right and the mockup sits on the left. */
  reversed?: boolean;
  /**
   * CB-LAND-001 S13 — opt-in cyan scanline overlay on the product mockup.
   * Defaults to `false` so existing rows keep their calm pastel look;
   * flip on for rows that should feel "live" (e.g. AI-powered features).
   * Scanline loop is driven by `--motion-scanline-loop` and fully disabled
   * under `prefers-reduced-motion: reduce` per §6.136.5.
   */
  scanline?: boolean;
}

export function FeatureRow({ content, reversed = false, scanline = false }: FeatureRowProps) {
  const { id, kicker, headlineHtml, body, learnMoreLabel, screenshotLabel, variant } = content;

  return (
    <article
      className={`feature-row feature-row--${variant}${reversed ? ' feature-row--reversed' : ''}`}
      data-variant={variant}
      aria-labelledby={`feature-row-${id}-headline`}
    >
      <div className="feature-row__inner">
        <div className="feature-row__text">
          <div className="feature-row__icon" aria-hidden="true" />
          <p className="feature-row__kicker">{kicker}</p>
          <h3
            id={`feature-row-${id}-headline`}
            className="feature-row__headline"
            // Only <em> is expected in headlineHtml; content is author-controlled.
            dangerouslySetInnerHTML={{ __html: headlineHtml }}
          />
          <p className="feature-row__body">{body}</p>
          <a className="feature-row__learn-more" href={`#${id}`}>
            {learnMoreLabel} <span aria-hidden="true">&rarr;</span>
          </a>
        </div>
        <div
          className="feature-row__mockup"
          data-scanline={scanline ? 'true' : undefined}
          role="img"
          aria-label={screenshotLabel}
        >
          <span className="feature-row__mockup-label">[{screenshotLabel}]</span>
        </div>
      </div>
    </article>
  );
}

export default FeatureRow;
