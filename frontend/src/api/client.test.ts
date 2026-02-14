import { describe, it, expect, beforeEach } from 'vitest'
import { api } from './client'

describe('API client', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('injects Authorization header when token is in localStorage', () => {
    localStorage.setItem('token', 'test-jwt-token')
    // Trigger the request interceptor manually
    const config = { headers: {} as Record<string, string> }
    const interceptor = api.interceptors.request.handlers[0]
    const result = interceptor.fulfilled(config as any)
    expect(result.headers.Authorization).toBe('Bearer test-jwt-token')
  })

  it('does not inject Authorization header without token', () => {
    const config = { headers: {} as Record<string, string> }
    const interceptor = api.interceptors.request.handlers[0]
    const result = interceptor.fulfilled(config as any)
    expect(result.headers.Authorization).toBeUndefined()
  })
})
