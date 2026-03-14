import { renderHook, act, waitFor } from '@testing-library/react'
import { useHelpChat } from '../useHelpChat'

// Helper to build a ReadableStream from SSE lines
function makeSSEStream(lines: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const line of lines) {
        controller.enqueue(encoder.encode(line))
      }
      controller.close()
    },
  })
}

function mockFetchOk(lines: string[]) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    body: makeSSEStream(lines),
  }))
}

function mockFetchStatus(status: number) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: false,
    status,
    body: null,
  }))
}

function mockFetchReject(err: unknown) {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(err))
}

describe('useHelpChat', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
    localStorage.setItem('token', 'test-token')
  })

  afterEach(() => {
    localStorage.removeItem('token')
  })

  it('sends correct fields and reads streamed help response', async () => {
    mockFetchOk([
      'data: {"type":"token","text":"ClassBridge "}\n\n',
      'data: {"type":"token","text":"helps."}\n\n',
      'data: {"type":"done","sources":["features"],"videos":[]}\n\n',
    ])

    const { result } = renderHook(() => useHelpChat())

    act(() => {
      result.current.sendMessage('What can ClassBridge do?')
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    const assistantMsg = result.current.messages.find(m => m.role === 'assistant')
    expect(assistantMsg).toBeDefined()
    expect(assistantMsg!.content).toBe('ClassBridge helps.')
    expect(assistantMsg!.sources).toEqual(['features'])

    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      expect.stringContaining('/api/help/chat/stream'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        body: expect.stringContaining('"message":"What can ClassBridge do?"'),
      })
    )
  })

  it('handles search event correctly', async () => {
    const searchPayload = {
      type: 'search',
      reply: 'Here\'s what I found for **"find courses"**:',
      intent: 'search',
      search_results: [
        { entity_type: 'course', id: 1, title: 'Math 101', description: null, actions: [] },
      ],
    }
    mockFetchOk([`data: ${JSON.stringify(searchPayload)}\n\n`])

    const { result } = renderHook(() => useHelpChat())

    act(() => {
      result.current.sendMessage('find courses')
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    const assistantMsg = result.current.messages.find(m => m.role === 'assistant')
    expect(assistantMsg).toBeDefined()
    expect(assistantMsg!.intent).toBe('search')
    expect(assistantMsg!.search_results).toHaveLength(1)
    expect(assistantMsg!.content).toContain('find courses')
  })

  it('includes conversation history from previous messages', async () => {
    // Set up both calls on a single mock so calls[1] is available
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        body: makeSSEStream([
          'data: {"type":"token","text":"Response"}\n\n',
          'data: {"type":"done","sources":[],"videos":[]}\n\n',
        ]),
      })
      .mockResolvedValueOnce({
        ok: true,
        body: makeSSEStream([
          'data: {"type":"token","text":"Follow-up response"}\n\n',
          'data: {"type":"done","sources":[],"videos":[]}\n\n',
        ]),
      })
    )

    const { result } = renderHook(() => useHelpChat())

    // Send first message
    act(() => {
      result.current.sendMessage('Hello')
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    act(() => {
      result.current.sendMessage('Follow up')
    })

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(4)
    })

    // Second call body should include conversation
    const secondCall = vi.mocked(fetch).mock.calls[1]
    const body = JSON.parse(secondCall[1]!.body as string)
    expect(body).toHaveProperty('conversation')
    expect(body).not.toHaveProperty('conversation_history')
  })

  it('shows rate limit error for 429 responses', async () => {
    mockFetchStatus(429)

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
    mockFetchStatus(401)

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
    mockFetchReject(new Error('Network Error'))

    const { result } = renderHook(() => useHelpChat())

    act(() => {
      result.current.sendMessage('test')
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.error).toContain('/help')
  })

  it('removes placeholder on error', async () => {
    mockFetchReject(new Error('Network Error'))

    const { result } = renderHook(() => useHelpChat())

    act(() => {
      result.current.sendMessage('test')
    })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    // Only the user message should remain; the placeholder assistant message is removed
    expect(result.current.messages.every(m => m.role !== 'assistant')).toBe(true)
  })
})
