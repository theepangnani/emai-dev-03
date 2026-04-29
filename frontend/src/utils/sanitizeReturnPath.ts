/**
 * Validate a post-login return path. Only same-origin paths starting with `/`
 * are allowed; protocol-relative or absolute URLs are rejected to prevent
 * open-redirect attacks via ?redirect=https://evil.com.
 *
 * Auth-page paths (`/login`, `/register`, etc.) are also rejected — navigating
 * back to them post-login produces an infinite redirect loop on the password
 * flow because the `?redirect=` param survives in the URL and the user-loaded
 * effect re-fires every render. (#4538)
 */
const FORBIDDEN_PATHS = new Set([
  '/login',
  '/register',
  '/forgot-password',
  '/waitlist',
]);

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
  // Reject auth-page paths to prevent post-login redirect loops (#4538).
  // Strip query/hash before comparing so `/login?next=foo` is also rejected.
  const pathname = raw.split('?')[0].split('#')[0];
  if (FORBIDDEN_PATHS.has(pathname)) return null;
  return raw;
}
