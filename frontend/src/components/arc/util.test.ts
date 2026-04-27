import { describe, it, expect } from 'vitest';
import { getArcVariant, ARC_VARIANTS } from './util';

describe('getArcVariant', () => {
  it('returns "rose" for null/undefined user id', () => {
    expect(getArcVariant(null)).toBe('rose');
    expect(getArcVariant(undefined)).toBe('rose');
  });

  it('is deterministic for the same id', () => {
    const id = 12345;
    expect(getArcVariant(id)).toBe(getArcVariant(id));
  });

  it('produces all 6 variants across a representative range of ids', () => {
    const seen = new Set<string>();
    for (let i = 0; i < 60; i++) seen.add(getArcVariant(i));
    expect(seen.size).toBe(ARC_VARIANTS.length);
  });

  it('handles negative ids without crashing', () => {
    expect(ARC_VARIANTS).toContain(getArcVariant(-99));
  });
});
