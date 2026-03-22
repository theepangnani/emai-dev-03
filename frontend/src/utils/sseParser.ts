export interface SSEEvent {
  event: string;
  data: string;
}

/**
 * Parse an SSE text buffer into discrete events.
 * Events are delimited by double newlines (`\n\n`).
 * Returns parsed events and any remaining incomplete text.
 */
export function parseSSEBuffer(buffer: string): { events: SSEEvent[]; remaining: string } {
  const events: SSEEvent[] = [];
  const blocks = buffer.split('\n\n');
  // The last element may be an incomplete block
  const remaining = blocks.pop() ?? '';

  for (const block of blocks) {
    if (!block.trim()) continue;

    let event = 'message';
    let data = '';

    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) {
        event = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        data = line.slice(5).trim();
      }
    }

    if (data) {
      events.push({ event, data });
    }
  }

  return { events, remaining };
}
