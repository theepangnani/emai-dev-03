/**
 * useFeatureToggle — #3895 hydration-default regression guard.
 *
 * Verifies that `useFeature('waitlist_enabled')` returns `true` while the
 * `/api/features` query is still pending (pre-launch posture), and that
 * other boolean flags default to `false`. Once the query resolves, the
 * server-supplied value takes precedence.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useFeature } from '../useFeatureToggle';
import { api } from '../../api/client';

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  }
  return { Wrapper, queryClient };
}

describe('useFeature (hydration defaults, #3895)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns true for waitlist_enabled while the query is pending', async () => {
    // Promise that never resolves during this assertion — simulates the
    // initial cold-load window before /api/features responds.
    let resolveFn: ((value: unknown) => void) | undefined;
    const pending = new Promise<unknown>((resolve) => {
      resolveFn = resolve;
    });
    const spy = vi.spyOn(api, 'get').mockReturnValue(pending as never);

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useFeature('waitlist_enabled'), {
      wrapper: Wrapper,
    });

    expect(result.current).toBe(true);
    expect(spy).toHaveBeenCalledWith('/api/features');

    // Clean up the hanging promise so the test harness doesn't leak.
    resolveFn?.({ data: { waitlist_enabled: false } });
  });

  it('returns false for non-waitlist flags while the query is pending', async () => {
    let resolveFn: ((value: unknown) => void) | undefined;
    const pending = new Promise<unknown>((resolve) => {
      resolveFn = resolve;
    });
    vi.spyOn(api, 'get').mockReturnValue(pending as never);

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useFeature('google_classroom'), {
      wrapper: Wrapper,
    });

    expect(result.current).toBe(false);

    resolveFn?.({ data: { google_classroom: true } });
  });

  it('returns the resolved server value once the query settles', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      data: {
        google_classroom: false,
        waitlist_enabled: false,
        school_board_connectivity: false,
        report_cards: false,
        analytics: false,
      },
    } as never);

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useFeature('waitlist_enabled'), {
      wrapper: Wrapper,
    });

    // During pending state, default kicks in.
    expect(result.current).toBe(true);

    // After the query resolves with `false`, the server value wins.
    await waitFor(() => expect(result.current).toBe(false));
  });
});
