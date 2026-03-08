import { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef, type ReactNode } from 'react';

export interface NotesFABConfig {
  courseContentId: number;
  isOpen: boolean;
  onToggle: () => void;
  hasNote?: boolean;
}

interface FABContextValue {
  notesFAB: NotesFABConfig | null;
  registerNotesFAB: (config: NotesFABConfig) => void;
  unregisterNotesFAB: () => void;
}

const FABContext = createContext<FABContextValue | null>(null);

export function FABProvider({ children }: { children: ReactNode }) {
  const [notesFAB, setNotesFAB] = useState<NotesFABConfig | null>(null);

  const registerNotesFAB = useCallback((config: NotesFABConfig) => {
    setNotesFAB(config);
  }, []);

  const unregisterNotesFAB = useCallback(() => {
    setNotesFAB(null);
  }, []);

  const value = useMemo(() => ({ notesFAB, registerNotesFAB, unregisterNotesFAB }), [notesFAB, registerNotesFAB, unregisterNotesFAB]);

  return (
    <FABContext.Provider value={value}>
      {children}
    </FABContext.Provider>
  );
}

const NOOP_FAB_CONTEXT: FABContextValue = {
  notesFAB: null,
  registerNotesFAB: () => {},
  unregisterNotesFAB: () => {},
};

export function useFABContext() {
  const ctx = useContext(FABContext);
  return ctx ?? NOOP_FAB_CONTEXT;
}

/**
 * Hook for pages to register a Notes FAB action into the speed dial.
 * Automatically unregisters on unmount.
 */
export function useRegisterNotesFAB(config: NotesFABConfig | null) {
  const ctx = useContext(FABContext);
  const unregisterRef = useRef<(() => void) | undefined>(undefined);
  unregisterRef.current = ctx?.unregisterNotesFAB;

  // Register/update whenever key props change
  useEffect(() => {
    if (!ctx) return;
    if (config) {
      ctx.registerNotesFAB(config);
    } else {
      ctx.unregisterNotesFAB();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config?.courseContentId, config?.isOpen, config?.hasNote]);

  // Unregister only on unmount
  useEffect(() => {
    return () => unregisterRef.current?.();
  }, []);
}
