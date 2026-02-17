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
  const cachedValue = faqCode && faqCode in faqCache ? faqCache[faqCode] : null;
  const [faqEntry, setFaqEntry] = useState<{ id: number; title: string } | null>(cachedValue);

  useEffect(() => {
    if (!faqCode) return;

    // Use cache if available
    if (faqCode in faqCache) return;

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

