/**
 * sanitizeReturnPath (#4486 D6) — same-origin path validator for the
 * post-login redirect target. Guards against open-redirect attacks where a
 * malicious deep-link could send the user to https://evil.com after auth.
 */
import { describe, it, expect } from 'vitest';
import { sanitizeReturnPath } from './sanitizeReturnPath';

describe('sanitizeReturnPath', () => {
  it('returns null for null input', () => {
    expect(sanitizeReturnPath(null)).toBeNull();
  });

  it('returns null for undefined input', () => {
    expect(sanitizeReturnPath(undefined)).toBeNull();
  });

  it('returns null for empty string', () => {
    expect(sanitizeReturnPath('')).toBeNull();
  });

  it('returns null for non-string input', () => {
    // Forced non-string at runtime — TS would reject this without the cast.
    expect(sanitizeReturnPath(42 as unknown as string)).toBeNull();
  });

  it('accepts a clean same-origin path', () => {
    expect(sanitizeReturnPath('/email-digest')).toBe('/email-digest');
  });

  it('accepts a same-origin path with a query string', () => {
    expect(sanitizeReturnPath('/tasks?id=42')).toBe('/tasks?id=42');
  });

  it('accepts the root path', () => {
    expect(sanitizeReturnPath('/')).toBe('/');
  });

  it('rejects a path that does not start with /', () => {
    expect(sanitizeReturnPath('dashboard')).toBeNull();
  });

  it('rejects an absolute http URL', () => {
    expect(sanitizeReturnPath('http://evil.com')).toBeNull();
  });

  it('rejects an absolute https URL', () => {
    expect(sanitizeReturnPath('https://evil.com')).toBeNull();
  });

  it('rejects a protocol-relative URL', () => {
    expect(sanitizeReturnPath('//evil.com')).toBeNull();
  });

  it('rejects a path with ://, even if it starts with /', () => {
    // e.g. /redirect?to=https://evil.com — the inner `://` is the giveaway.
    expect(sanitizeReturnPath('/redirect?to=https://evil.com')).toBeNull();
  });

  it('rejects javascript: URLs (no leading slash)', () => {
    expect(sanitizeReturnPath('javascript:alert(1)')).toBeNull();
  });
});
