/**
 * Validate a post-login return path. Only same-origin paths starting with `/`
 * are allowed; protocol-relative or absolute URLs are rejected to prevent
 * open-redirect attacks via ?redirect=https://evil.com.
 */
export function sanitizeReturnPath(raw: string | null | undefined): string | null {
  if (!raw) return null;
  if (typeof raw !== 'string') return null;
  // Reject anything that isn't a clean same-origin path:
  // - Must start with `/`
  // - Must NOT start with `//` (protocol-relative)
  // - Must NOT contain `://` (absolute URL)
  if (!raw.startsWith('/')) return null;
  if (raw.startsWith('//')) return null;
  if (raw.includes('://')) return null;
  return raw;
}
