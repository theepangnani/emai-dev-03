/**
 * Extract faq_code from an Axios error response.
 * Usage: const faqCode = extractFaqCode(err);
 */
export function extractFaqCode(err: unknown): string | null {
  if (
    err &&
    typeof err === 'object' &&
    'response' in err &&
    (err as Record<string, unknown>).response &&
    typeof (err as Record<string, unknown>).response === 'object'
  ) {
    const response = (err as { response: { data?: { faq_code?: string } } }).response;
    if (response.data?.faq_code) {
      return response.data.faq_code;
    }
  }
  return null;
}
