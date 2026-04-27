import { renderHook, act } from '@testing-library/react'
import type { ReactNode } from 'react'

import { ThemeProvider, useTheme, BRIDGE_DEFAULT_CACHE_KEY } from './ThemeContext'

const STORAGE_KEY = 'classbridge-theme'

function wrapper({ children }: { children: ReactNode }) {
  return <ThemeProvider>{children}</ThemeProvider>
}

describe('ThemeContext — applyBridgeDefaultIfUnset', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
  })

  it('applies bridge when no theme is stored', () => {
    const { result } = renderHook(() => useTheme(), { wrapper })
    act(() => result.current.applyBridgeDefaultIfUnset())
    expect(result.current.theme).toBe('bridge')
    expect(document.documentElement.getAttribute('data-theme')).toBe('bridge')
  })

  it('respects an explicit stored theme', () => {
    localStorage.setItem(STORAGE_KEY, 'dark')
    const { result } = renderHook(() => useTheme(), { wrapper })
    act(() => result.current.applyBridgeDefaultIfUnset())
    expect(result.current.theme).toBe('dark')
  })

  it('is a no-op on the second call (forcedRef guard preserves manual toggle)', () => {
    const { result } = renderHook(() => useTheme(), { wrapper })
    act(() => result.current.applyBridgeDefaultIfUnset())
    expect(result.current.theme).toBe('bridge')
    // Simulate user manually flipping after force-apply
    act(() => result.current.setTheme('focus'))
    expect(result.current.theme).toBe('focus')
    // A second call (e.g., flag flips again mid-session) must NOT overwrite the manual pick
    act(() => result.current.applyBridgeDefaultIfUnset())
    expect(result.current.theme).toBe('focus')
  })
})

describe('ThemeContext — getInitialTheme cached bridge flag (#4213 FOWT)', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
  })

  it('paints bridge synchronously on mount when the cached flag is true and no theme is stored', () => {
    localStorage.setItem(BRIDGE_DEFAULT_CACHE_KEY, 'true')
    const { result } = renderHook(() => useTheme(), { wrapper })
    // Initial state is derived synchronously by getInitialTheme — no
    // applyBridgeDefaultIfUnset() call needed here.
    expect(result.current.theme).toBe('bridge')
    expect(document.documentElement.getAttribute('data-theme')).toBe('bridge')
  })

  it('respects an explicit stored theme even when the cached flag is true', () => {
    localStorage.setItem(BRIDGE_DEFAULT_CACHE_KEY, 'true')
    localStorage.setItem(STORAGE_KEY, 'dark')
    const { result } = renderHook(() => useTheme(), { wrapper })
    expect(result.current.theme).toBe('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })

  it('falls back to light when the cached flag is absent or not "true"', () => {
    localStorage.setItem(BRIDGE_DEFAULT_CACHE_KEY, 'false')
    const { result } = renderHook(() => useTheme(), { wrapper })
    expect(result.current.theme).toBe('light')
  })
})
