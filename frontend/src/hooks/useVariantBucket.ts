/**
 * useVariantBucket — sticky A/B bucketing for feature flag variants (#3601, #3802).
 *
 * Resolves a flag's declared variant into a concrete "on" | "off" value for
 * the current visitor:
 *   - variant === 'off'          → 'off'
 *   - variant === 'on_for_all'   → 'on'          (CB-DEMO-001 legacy)
 *   - variant === 'on_50'        → 'on' for ~50% of bucket ids, else 'off'
 *   - variant === 'on_5'         → 'on' for ~5%  of bucket ids (CB-LAND-001 #3802)
 *   - variant === 'on_25'        → 'on' for ~25%
 *   - variant === 'on_100'       → 'on'           (full rollout; synonym of on_for_all)
 *
 * The bucket id is a UUID persisted to localStorage under
 * `classbridge_ab_bucket`, so the same visitor gets a stable assignment
 * across reloads and flag evaluations.
 */
import { useMemo } from 'react';
import { useFeatureVariant, type FeatureVariant } from './useFeatureToggle';

export const BUCKET_STORAGE_KEY = 'classbridge_ab_bucket';

export type BucketResolution = 'on' | 'off';

/** Generate a random UUID, falling back to Math.random when crypto is unavailable. */
function generateBucketId(): string {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
  } catch {
    // fall through to fallback
  }
  // Non-secure fallback — still fine for A/B bucketing
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/** Read or create the sticky localStorage bucket id. Safe in SSR / no-storage environments. */
export function getOrCreateBucketId(): string {
  try {
    if (typeof window === 'undefined' || !window.localStorage) {
      return generateBucketId();
    }
    const existing = window.localStorage.getItem(BUCKET_STORAGE_KEY);
    if (existing && existing.length > 0) {
      return existing;
    }
    const created = generateBucketId();
    window.localStorage.setItem(BUCKET_STORAGE_KEY, created);
    return created;
  } catch {
    // localStorage disabled (e.g. private mode quota) — return ephemeral id
    return generateBucketId();
  }
}

/**
 * Deterministic hash of a string to an integer in [0, 99].
 * Uses a simple FNV-1a style mix — cheap, stable, and good enough for
 * uniform 0..99 bucketing. (NOT a cryptographic hash.)
 */
export function hashBucketId(bucketId: string): number {
  let h = 0x811c9dc5; // FNV offset basis (32-bit)
  for (let i = 0; i < bucketId.length; i++) {
    h ^= bucketId.charCodeAt(i);
    // Avoid Math.imul for IE/older-browser safety — JS bitwise ops stay 32-bit.
    h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) | 0;
  }
  // >>> 0 converts to unsigned 32-bit before modulo
  return (h >>> 0) % 100;
}

/**
 * Threshold percentage for each `on_N` variant.
 * `on_for_all` and `on_100` short-circuit to 'on' above.
 */
const VARIANT_THRESHOLD: Record<FeatureVariant, number> = {
  off: 0,
  on_5: 5,
  on_25: 25,
  on_50: 50,
  on_100: 100,
  on_for_all: 100,
};

/** Pure resolver — exposed for tests. */
export function resolveVariant(variant: FeatureVariant, bucketId: string): BucketResolution {
  if (variant === 'off') return 'off';
  if (variant === 'on_for_all' || variant === 'on_100') return 'on';
  const threshold = VARIANT_THRESHOLD[variant] ?? 0;
  if (threshold <= 0) return 'off';
  if (threshold >= 100) return 'on';
  return hashBucketId(bucketId) < threshold ? 'on' : 'off';
}

/**
 * React hook that returns `'on'` or `'off'` for the given flag key,
 * applying sticky percentage bucketing when the flag's variant is a
 * partial rollout (`on_5` / `on_25` / `on_50`).
 */
export function useVariantBucket(flagKey: string): BucketResolution {
  const variant = useFeatureVariant(flagKey);
  return useMemo(() => {
    if (variant === 'off') return 'off';
    if (variant === 'on_for_all' || variant === 'on_100') return 'on';
    const bucketId = getOrCreateBucketId();
    return resolveVariant(variant, bucketId);
  }, [variant]);
}
