/**
 * LanguageToggle — EN/FR switcher for the dashboard header.
 *
 * On click, updates the in-memory locale, persists to localStorage,
 * and dispatches a "localechange" event so subscribers can re-render.
 */
import { useState } from 'react';
import { setLocale, getLocale, type Locale } from '../i18n';
import './LanguageToggle.css';

interface LanguageToggleProps {
  /** Called after the locale is changed (optional — for syncing to backend) */
  onLocaleChange?: (locale: Locale) => void;
}

export function LanguageToggle({ onLocaleChange }: LanguageToggleProps = {}) {
  const [locale, setLocaleState] = useState<Locale>(getLocale());

  const toggle = () => {
    const next: Locale = locale === 'en' ? 'fr' : 'en';
    setLocale(next);
    setLocaleState(next);
    // Notify any components listening for locale changes
    window.dispatchEvent(new CustomEvent('localechange', { detail: next }));
    onLocaleChange?.(next);
  };

  return (
    <button
      onClick={toggle}
      className="language-toggle"
      aria-label={locale === 'en' ? 'Switch to French' : "Passer à l'anglais"}
      title={locale === 'en' ? 'Passer en français' : 'Switch to English'}
    >
      {locale === 'en' ? 'FR' : 'EN'}
    </button>
  );
}
