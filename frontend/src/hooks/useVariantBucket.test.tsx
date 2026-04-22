/**
 * Hook-level tests for useVariantBucket's kill-switch semantics (#3930, #3931).
 *
 * Focus: `enabled=false` MUST force `'off'` regardless of `variant`. The
 * pure helpers (resolveVariant, hashBucketId, getOrCreateBucketId) are
 * covered in useVariantBucket.test.ts; this file exercises the React hook
 * with `useFeatureFlagEnabled` + `useFeatureVariant` mocked so we can
 * deterministically assert the kill-switch boundary.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import type { FeatureVariant } from './useFeatureToggle';

const enabledMock = vi.fn<(key: string) => boolean>(() => true);
const variantMock = vi.fn<(key: string) => FeatureVariant>(() => 'off');

vi.mock('./useFeatureToggle', async () => {
  const actual = await vi.importActual<typeof import('./useFeatureToggle')>(
    './useFeatureToggle',
  );
  return {
    ...actual,
    useFeatureFlagEnabled: (key: string) => enabledMock(key),
    useFeatureVariant: (key: string) => variantMock(key),
  };
});

// Import AFTER the mock so the hook picks up mocked dependencies.
import { useVariantBucket, BUCKET_STORAGE_KEY } from './useVariantBucket';

describe('useVariantBucket — kill-switch boundary (#3930)', () => {
  beforeEach(() => {
    enabledMock.mockReset();
    variantMock.mockReset();
    window.localStorage.clear();
    // Pin a stable bucket id so on_50 is deterministic within a single run.
    window.localStorage.setItem(BUCKET_STORAGE_KEY, 'stable-test-bucket-id');
  });

  it("enabled=true, variant='off' → 'off'", () => {
    enabledMock.mockReturnValue(true);
    variantMock.mockReturnValue('off');
    const { result } = renderHook(() => useVariantBucket('landing_v2'));
    expect(result.current).toBe('off');
  });

  it("enabled=true, variant='on_for_all' → 'on'", () => {
    enabledMock.mockReturnValue(true);
    variantMock.mockReturnValue('on_for_all');
    const { result } = renderHook(() => useVariantBucket('demo_landing_v1_1'));
    expect(result.current).toBe('on');
  });

  it("enabled=true, variant='on_100' → 'on'", () => {
    enabledMock.mockReturnValue(true);
    variantMock.mockReturnValue('on_100');
    const { result } = renderHook(() => useVariantBucket('landing_v2'));
    expect(result.current).toBe('on');
  });

  it("enabled=true, variant='on_50' → 'on' or 'off' (bucketed)", () => {
    enabledMock.mockReturnValue(true);
    variantMock.mockReturnValue('on_50');
    const { result } = renderHook(() => useVariantBucket('landing_v2'));
    expect(['on', 'off']).toContain(result.current);
  });

  // ---- The bug being fixed (#3930) ----

  it("kill-switch: enabled=false overrides variant='on_for_all' → 'off'", () => {
    enabledMock.mockReturnValue(false);
    variantMock.mockReturnValue('on_for_all');
    const { result } = renderHook(() => useVariantBucket('demo_landing_v1_1'));
    expect(result.current).toBe('off');
  });

  it("kill-switch: enabled=false overrides variant='on_100' → 'off'", () => {
    enabledMock.mockReturnValue(false);
    variantMock.mockReturnValue('on_100');
    const { result } = renderHook(() => useVariantBucket('landing_v2'));
    expect(result.current).toBe('off');
  });

  it("kill-switch: enabled=false overrides variant='on_50' → 'off'", () => {
    enabledMock.mockReturnValue(false);
    variantMock.mockReturnValue('on_50');
    const { result } = renderHook(() => useVariantBucket('landing_v2'));
    expect(result.current).toBe('off');
  });

  it("enabled=false, variant='off' → 'off'", () => {
    enabledMock.mockReturnValue(false);
    variantMock.mockReturnValue('off');
    const { result } = renderHook(() => useVariantBucket('landing_v2'));
    expect(result.current).toBe('off');
  });
});
