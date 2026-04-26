import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

// #4257: Targeted unhandled-rejection filter for jsdom 28 + undici v7
// incompatibility. jsdom's resource dispatcher omits the `onError` handler
// that undici v7 now validates, so any external resource fetch (e.g. the
// `fonts.googleapis.com` stylesheet injected by `useLandingFonts` or
// imported from `index.css`) produces an `UND_ERR_INVALID_ARG` rejection
// during teardown. We log + swallow only that exact error code so genuine
// app-level rejections still surface in test output.
//
// `dangerouslyIgnoreUnhandledErrors` is also set in `vitest.config.ts` to
// guarantee a clean process exit even if a future Node version starts firing
// `unhandledRejection` after vitest's own listener has already collected.
process.on('unhandledRejection', (reason: unknown) => {
  const code = (reason as { code?: string } | null | undefined)?.code
  if (code === 'UND_ERR_INVALID_ARG') {
    return // jsdom-internal noise; safe to ignore.
  }
  // Re-surface anything we didn't expect so it shows up in test logs.
  console.error('[setup] unexpected unhandledRejection:', reason)
})

// Mock ResizeObserver (not available in jsdom)
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value },
    removeItem: (key: string) => { delete store[key] },
    clear: () => { store = {} },
    get length() { return Object.keys(store).length },
    key: (i: number) => Object.keys(store)[i] ?? null,
  }
})()

Object.defineProperty(window, 'localStorage', { value: localStorageMock })

// Mock matchMedia (not available in jsdom)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })),
})
