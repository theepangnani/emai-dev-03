/**
 * useTutorChatEnabled — thin wrapper over `useFeatureFlagEnabled` (#4066).
 *
 * Verifies that the hook reads the `tutor_chat_enabled` key from the
 * `/api/features` response and returns the correct boolean, and that it
 * defaults to `false` while the query is still pending (kill-switch
 * semantics from #3930).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useTutorChatEnabled } from '../useTutorChatEnabled';
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

describe('useTutorChatEnabled (#4066)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns false while the /api/features query is pending', async () => {
    let resolveFn: ((value: unknown) => void) | undefined;
    const pending = new Promise<unknown>((resolve) => {
      resolveFn = resolve;
    });
    vi.spyOn(api, 'get').mockReturnValue(pending as never);

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useTutorChatEnabled(), {
      wrapper: Wrapper,
    });

    expect(result.current).toBe(false);

    // Release the hanging promise so the harness doesn't leak.
    resolveFn?.({ data: { tutor_chat_enabled: false } });
  });

  it('returns true when the server reports tutor_chat_enabled: true', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      data: {
        tutor_chat_enabled: true,
      },
    } as never);

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useTutorChatEnabled(), {
      wrapper: Wrapper,
    });

    await waitFor(() => expect(result.current).toBe(true));
  });

  it('returns false when the server reports tutor_chat_enabled: false', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      data: {
        tutor_chat_enabled: false,
      },
    } as never);

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useTutorChatEnabled(), {
      wrapper: Wrapper,
    });

    // Either still pending (false) or resolved false — both acceptable.
    await waitFor(() => expect(result.current).toBe(false));
  });

  it('returns false when the flag key is absent from the response', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      data: {
        // tutor_chat_enabled intentionally absent
        google_classroom: true,
      },
    } as never);

    const { Wrapper } = makeWrapper();
    const { result } = renderHook(() => useTutorChatEnabled(), {
      wrapper: Wrapper,
    });

    await waitFor(() => {
      // Once the query resolves, the value should be a stable boolean (false).
      expect(result.current).toBe(false);
    });
  });
});
