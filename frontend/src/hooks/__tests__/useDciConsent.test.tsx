/**
 * useDciConsent (#4267) — verifies the hook does NOT retry on 4xx errors.
 *
 * The global QueryClient default is `retry: 1`. A first-visit parent will
 * hit a 404 (no consent row yet) and that 404 should immediately surface
 * as `isError=true` so the page can redirect — not be retried. Without
 * this gate the parent saw a 1-2s blank state on every cold load.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

import { useDciConsent } from '../useDciConsent';
import { dciConsentApi } from '../../api/dciConsent';

function makeWrapper() {
  // Simulates the production QueryClient default of `retry: 1` so the
  // hook-level override is the only thing preventing retries.
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: 1, retryDelay: 0 },
      mutations: { retry: false },
    },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  }
  return { Wrapper, queryClient };
}

describe('useDciConsent (#4267 — no retry on 4xx)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('does not retry a 404 — surfaces isError after a single call', async () => {
    const err = Object.assign(new Error('not found'), {
      response: { status: 404 },
    });
    const spy = vi.spyOn(dciConsentApi, 'get').mockRejectedValue(err);

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useDciConsent(42), {
      wrapper: Wrapper,
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
    // The single failed call should not be retried.
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('does not retry a 403 either', async () => {
    const err = Object.assign(new Error('forbidden'), {
      response: { status: 403 },
    });
    const spy = vi.spyOn(dciConsentApi, 'get').mockRejectedValue(err);

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useDciConsent(7), {
      wrapper: Wrapper,
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('still retries 5xx server errors once', async () => {
    const err = Object.assign(new Error('server error'), {
      response: { status: 500 },
    });
    const spy = vi.spyOn(dciConsentApi, 'get').mockRejectedValue(err);

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useDciConsent(99), {
      wrapper: Wrapper,
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
    // Initial call + 1 retry = 2 total.
    expect(spy).toHaveBeenCalledTimes(2);
  });
});
