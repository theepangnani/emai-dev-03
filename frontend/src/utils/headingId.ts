/** Generate a URL-safe slug from heading text */
export function generateHeadingId(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-');
}

/** Deduplicate IDs by appending a numeric suffix for repeats */
export function deduplicateIds<T extends { id: string }>(items: T[]): T[] {
  const counts = new Map<string, number>();
  return items.map(item => {
    const count = counts.get(item.id) ?? 0;
    counts.set(item.id, count + 1);
    return count === 0 ? item : { ...item, id: `${item.id}-${count}` };
  });
}
