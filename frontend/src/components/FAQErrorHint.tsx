import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { faqApi } from '../api/client';
import './FAQErrorHint.css';

// Simple in-memory cache for FAQ lookups to avoid repeated API calls
const faqCache: Record<string, { id: number; title: string } | null> = {};

interface FAQErrorHintProps {
  faqCode?: string | null;
}

export function FAQErrorHint({ faqCode }: FAQErrorHintProps) {
  const navigate = useNavigate();
  const [faqEntry, setFaqEntry] = useState<{ id: number; title: string } | null>(null);

  useEffect(() => {
    if (!faqCode) return;

    // Check cache first
    if (faqCode in faqCache) {
      setFaqEntry(faqCache[faqCode]);
      return;
    }

    faqApi.getByErrorCode(faqCode).then((data) => {
      const entry = { id: data.id, title: data.title };
      faqCache[faqCode] = entry;
      setFaqEntry(entry);
    }).catch(() => {
      faqCache[faqCode] = null;
      setFaqEntry(null);
    });
  }, [faqCode]);

  if (!faqCode || !faqEntry) return null;

  return (
    <div className="faq-error-hint">
      <span className="faq-error-hint-icon">&#10068;</span>
      <span>Need help? See: </span>
      <button
        className="faq-error-hint-link"
        onClick={() => navigate(`/faq/${faqEntry.id}`)}
      >
        {faqEntry.title}
      </button>
    </div>
  );
}

/**
 * Extract faq_code from an Axios error response.
 * Usage: const faqCode = extractFaqCode(err);
 */
export function extractFaqCode(err: unknown): string | null {
  if (
    err &&
    typeof err === 'object' &&
    'response' in err &&
    (err as any).response?.data?.faq_code
  ) {
    return (err as any).response.data.faq_code;
  }
  return null;
}
