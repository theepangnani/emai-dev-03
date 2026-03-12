import { renderHook, act, waitFor } from '@testing-library/react'
import { useHelpChat } from '../useHelpChat'
import { api } from '../../../api/client'

vi.mock('../../../api/client', () => ({
  api: {
    post: vi.fn(),
  },
}))

const mockedApi = vi.mocked(api)

describe('useHelpChat', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
  })

  it('sends correct field names and reads response correctly', async () => {
    // Backend returns "reply", not "answer"
    mockedApi.post.mockResolvedValueOnce({
      data: {
        reply: 'ClassBridge helps parents and students manage education.',
        sources: ['features'],
        videos: [],
      },
    })

    const { result } = renderHook(() => useHelpChat())

    act(() => {
      result.current.sendMessage('What can ClassBridge do?')
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    // Verify request uses "conversation" (not "conversation_history")
    expect(mockedApi.post).toHaveBeenCalledWith('/api/help/chat', {
      message: 'What can ClassBridge do?',
      conversation: expect.any(Array),
    })

    // Verify assistant message content comes from "reply" field
    const assistantMsg = result.current.messages.find(m => m.role === 'assistant')
    expect(assistantMsg).toBeDefined()
    expect(assistantMsg!.content).toBe('ClassBridge helps parents and students manage education.')
    expect(assistantMsg!.sources).toEqual(['features'])
  })

  it('fails if backend response uses "answer" instead of "reply"', async () => {
    // Simulate old mismatched response shape
    mockedApi.post.mockResolvedValueOnce({
      data: {
        answer: 'This should not work',
        reply: undefined,
        sources: [],
        videos: [],
      },
    })

    const { result } = renderHook(() => useHelpChat())

    act(() => {
      result.current.sendMessage('test')
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    // With the fix, content reads from "reply" which is undefined here
    // This proves the old "answer" field is NOT used
    const assistantMsg = result.current.messages.find(m => m.role === 'assistant')
    expect(assistantMsg?.content).toBeUndefined()
  })

  it('includes conversation history from previous messages', async () => {
    mockedApi.post.mockResolvedValue({
      data: { reply: 'Response', sources: [], videos: [] },
    })

    const { result } = renderHook(() => useHelpChat())

    // Send first message
    act(() => {
      result.current.sendMessage('Hello')
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    // Send second message
    act(() => {
      result.current.sendMessage('Follow up')
    })

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(4)
    })

    // Second call should include conversation history with "conversation" key
    const secondCall = mockedApi.post.mock.calls[1]
    expect(secondCall[1]).toHaveProperty('conversation')
    expect(secondCall[1]).not.toHaveProperty('conversation_history')
  })

  it('shows rate limit error for 429 responses', async () => {
    mockedApi.post.mockRejectedValueOnce({ response: { status: 429 } })

    const { result } = renderHook(() => useHelpChat())

    act(() => {
      result.current.sendMessage('test')
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.error).toMatch(/request limit/i)
  })

  it('shows auth error for 401 responses', async () => {
    mockedApi.post.mockRejectedValueOnce({ response: { status: 401 } })

    const { result } = renderHook(() => useHelpChat())

    act(() => {
      result.current.sendMessage('test')
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.error).toMatch(/session expired/i)
  })

  it('shows help page link for generic network errors', async () => {
    mockedApi.post.mockRejectedValueOnce(new Error('Network Error'))

    const { result } = renderHook(() => useHelpChat())

    act(() => {
      result.current.sendMessage('test')
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.error).toContain('/help')
  })
})
