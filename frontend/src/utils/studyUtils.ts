/**
 * Extract a question count from a focus prompt like "generate 20 tough questions".
 * Returns the extracted number (clamped to 1–50), or defaultCount if not found.
 */
export function extractQuestionCount(prompt: string | undefined, defaultCount = 10): number {
  if (!prompt) return defaultCount;
  const match = prompt.match(/(\d+)\s*\w*\s*questions?/i);
  if (match) {
    const n = parseInt(match[1], 10);
    if (n >= 1 && n <= 50) return n;
  }
  return defaultCount;
}

/**
 * Extract a card count from a focus prompt like "make 20 flashcards".
 * Returns the extracted number (clamped to 1–50), or defaultCount if not found.
 */
export function extractCardCount(prompt: string | undefined, defaultCount = 10): number {
  if (!prompt) return defaultCount;
  const match = prompt.match(/(\d+)\s*\w*\s*(?:flash)?cards?/i);
  if (match) {
    const n = parseInt(match[1], 10);
    if (n >= 1 && n <= 50) return n;
  }
  return defaultCount;
}
