/**
 * Heuristic to detect OCR-extracted text that may contain quality issues.
 * Scores text on several signals and returns true when score >= 4.
 */
export function looksLikeOCR(text: string): boolean {
  if (!text || text.length < 50) return false;

  const lines = text.split('\n');
  const nonEmptyLines = lines.filter(l => l.trim().length > 0);
  if (nonEmptyLines.length === 0) return false;

  let score = 0;

  // 1. Short average line length (< 40 chars) → +2
  const avgLineLen = nonEmptyLines.reduce((sum, l) => sum + l.trim().length, 0) / nonEmptyLines.length;
  if (avgLineLen < 40) score += 2;

  // 2. >70% lines lacking terminal punctuation → +2
  const punctuationRe = /[.!?:;'")}\]>]$/;
  const linesWithoutPunctuation = nonEmptyLines.filter(l => !punctuationRe.test(l.trim()));
  if (linesWithoutPunctuation.length / nonEmptyLines.length > 0.7) score += 2;

  // 3. Excessive blank lines (>50% of total lines) → +1
  const blankLines = lines.length - nonEmptyLines.length;
  if (blankLines / lines.length > 0.5) score += 1;

  // 4. Many single-char words (>15% of total words) → +2
  const words = text.split(/\s+/).filter(w => w.length > 0);
  if (words.length > 0) {
    const singleCharWords = words.filter(w => w.length === 1 && !/[aAI]/.test(w));
    if (singleCharWords.length / words.length > 0.15) score += 2;
  }

  return score >= 4;
}
