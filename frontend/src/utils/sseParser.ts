export interface SSEEvent {
  event: string;
  data: string;
}

/**
 * Parse an SSE buffer into discrete events.
 * Returns parsed events and any remaining incomplete data.
 */
export function parseSSEBuffer(buffer: string): { events: SSEEvent[]; remaining: string } {
  const events: SSEEvent[] = [];
  const blocks = buffer.split('\n\n');
  // Last block may be incomplete — keep as remaining
  const remaining = blocks.pop() ?? '';

  for (const block of blocks) {
    if (!block.trim()) continue;
    let event = 'message';
    let data = '';
    for (const line of block.split('\n')) {
      if (line.startsWith('event: ')) {
        event = line.slice(7).trim();
      } else if (line.startsWith('data: ')) {
        data += (data ? '\n' : '') + line.slice(6);
      } else if (line.startsWith('data:')) {
        // "data:" with no space — value is rest of line
        data += (data ? '\n' : '') + line.slice(5);
      }
    }
    if (data) {
      events.push({ event, data });
    }
  }

  return { events, remaining };
}
