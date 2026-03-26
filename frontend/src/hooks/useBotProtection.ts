import { useState, useRef, useEffect } from 'react';

interface BotProtectionFields {
  website: string;
  started_at: number;
}

interface BotProtection {
  honeypotProps: {
    type: string;
    name: string;
    value: string;
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
    style: React.CSSProperties;
    tabIndex: number;
    autoComplete: string;
    'aria-hidden': boolean;
  };
  getFields: () => BotProtectionFields;
  resetTimer: () => void;
}

export function useBotProtection(): BotProtection {
  const [honeypot, setHoneypot] = useState('');
  const startedAt = useRef<number>(0);

  useEffect(() => {
    startedAt.current = Date.now() / 1000;
  }, []);

  return {
    honeypotProps: {
      type: 'text',
      name: 'website',
      value: honeypot,
      onChange: (e: React.ChangeEvent<HTMLInputElement>) => setHoneypot(e.target.value),
      style: { position: 'absolute' as const, left: '-9999px', opacity: 0, height: 0, width: 0 },
      tabIndex: -1,
      autoComplete: 'off',
      'aria-hidden': true as const,
    },
    getFields: () => ({
      website: honeypot,
      started_at: startedAt.current > 0 ? (Date.now() / 1000) - startedAt.current : 0,
    }),
    resetTimer: () => {
      startedAt.current = Date.now() / 1000;
    },
  };
}
