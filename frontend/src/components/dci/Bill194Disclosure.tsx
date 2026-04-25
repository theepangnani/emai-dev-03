// CB-DCI-001 M0-11 — Bill 194 inline disclosure (#4148)
//
// Spec: docs/design/CB-DCI-001-daily-checkin.md § 11
// "AI processing disclosed at each check-in inline:
//  'AI will read this to help your parents.'"
//
// Designed to be compact and unobtrusive. M0-9 imports this and places it
// inline above the "Send to ClassBridge" CTA on every kid capture screen.

import type { CSSProperties } from 'react';

export interface Bill194DisclosureProps {
  /** Optional override for the body copy. Defaults to the Bill 194 spec line. */
  message?: string;
  /** Optional CSS overrides. */
  style?: CSSProperties;
  /** Test id. Defaults to 'bill-194-disclosure'. */
  testId?: string;
}

const DEFAULT_MESSAGE = 'AI will read this to help your parents.';

const containerStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'flex-start',
  gap: 8,
  padding: '8px 12px',
  background: '#fff7ed', // amber-50
  border: '1px solid #fed7aa', // amber-200
  borderRadius: 8,
  fontSize: 12,
  lineHeight: 1.4,
  color: '#7c2d12', // amber-900
};

const iconStyle: CSSProperties = {
  flex: '0 0 auto',
  fontSize: 14,
  lineHeight: 1,
  marginTop: 1,
};

const textStyle: CSSProperties = {
  flex: 1,
  margin: 0,
};

const labelStyle: CSSProperties = {
  fontWeight: 600,
  marginRight: 4,
};

/**
 * Reusable inline AI disclosure required on every kid capture screen.
 *
 * The wrapper uses `role="note"` to mark it as advisory text — that's
 * the WCAG-correct affordance for static content. (We intentionally do
 * not use `aria-live` here: it's for dynamic regions that change after
 * mount, and the disclosure copy is static.)
 */
export function Bill194Disclosure({
  message = DEFAULT_MESSAGE,
  style,
  testId = 'bill-194-disclosure',
}: Bill194DisclosureProps) {
  return (
    <div
      role="note"
      data-testid={testId}
      style={{ ...containerStyle, ...style }}
    >
      <span aria-hidden="true" style={iconStyle}>
        ⓘ
      </span>
      <p style={textStyle}>
        <span style={labelStyle}>AI notice:</span>
        {message}
      </p>
    </div>
  );
}

export default Bill194Disclosure;
