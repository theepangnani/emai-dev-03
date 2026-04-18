/**
 * Tests for useVariantBucket (#3601, CB-DEMO-001 F2).
 *
 * We test the pure helpers (resolveVariant, hashBucketId, getOrCreateBucketId)
 * — the hook itself is a thin useMemo wrapper around them.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import {
  BUCKET_STORAGE_KEY,
  getOrCreateBucketId,
  hashBucketId,
  resolveVariant,
} from './useVariantBucket';

describe('hashBucketId', () => {
  it('is deterministic for the same input', () => {
    const a = hashBucketId('test-bucket-id');
    const b = hashBucketId('test-bucket-id');
    expect(a).toBe(b);
  });

  it('returns a value in [0, 99]', () => {
    for (const id of ['a', 'aa', 'a-very-long-bucket-id-1234567890', '', 'xyz']) {
      const h = hashBucketId(id);
      expect(h).toBeGreaterThanOrEqual(0);
      expect(h).toBeLessThanOrEqual(99);
    }
  });

  it('produces a reasonably uniform distribution across many inputs', () => {
    let lowCount = 0;
    const N = 2000;
    for (let i = 0; i < N; i++) {
      const id = `user-${i}-${Math.sin(i).toString(36)}`;
      if (hashBucketId(id) < 50) lowCount++;
    }
    const ratio = lowCount / N;
    // Allow a generous tolerance — we just want rough uniformity, not a PRNG.
    expect(ratio).toBeGreaterThan(0.4);
    expect(ratio).toBeLessThan(0.6);
  });
});

describe('resolveVariant', () => {
  it("returns 'off' when variant is 'off'", () => {
    expect(resolveVariant('off', 'any-bucket')).toBe('off');
  });

  it("returns 'on' when variant is 'on_for_all'", () => {
    expect(resolveVariant('on_for_all', 'any-bucket')).toBe('on');
  });

  it("is deterministic for 'on_50' given a fixed bucket id", () => {
    const id = 'stable-bucket-id-12345';
    const first = resolveVariant('on_50', id);
    for (let i = 0; i < 20; i++) {
      expect(resolveVariant('on_50', id)).toBe(first);
    }
  });

  it("splits roughly 50/50 across many bucket ids when variant is 'on_50'", () => {
    let onCount = 0;
    const N = 2000;
    for (let i = 0; i < N; i++) {
      if (resolveVariant('on_50', `bucket-${i}`) === 'on') onCount++;
    }
    const ratio = onCount / N;
    expect(ratio).toBeGreaterThan(0.4);
    expect(ratio).toBeLessThan(0.6);
  });
});

describe('getOrCreateBucketId', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('creates and persists a bucket id on first call', () => {
    expect(window.localStorage.getItem(BUCKET_STORAGE_KEY)).toBeNull();
    const id = getOrCreateBucketId();
    expect(id).toBeTruthy();
    expect(id.length).toBeGreaterThan(8);
    expect(window.localStorage.getItem(BUCKET_STORAGE_KEY)).toBe(id);
  });

  it('returns the same bucket id on subsequent calls (sticky)', () => {
    const first = getOrCreateBucketId();
    const second = getOrCreateBucketId();
    const third = getOrCreateBucketId();
    expect(second).toBe(first);
    expect(third).toBe(first);
  });

  it('re-uses an existing bucket id written directly to localStorage', () => {
    window.localStorage.setItem(BUCKET_STORAGE_KEY, 'preexisting-bucket-id');
    const id = getOrCreateBucketId();
    expect(id).toBe('preexisting-bucket-id');
  });
});
