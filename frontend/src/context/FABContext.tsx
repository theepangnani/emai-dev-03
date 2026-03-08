import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';

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

  return (
    <FABContext.Provider value={{ notesFAB, registerNotesFAB, unregisterNotesFAB }}>
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
  // Register/update whenever key props change
  useEffect(() => {
    if (!ctx) return;
    if (config) {
      ctx.registerNotesFAB(config);
    } else {
      ctx.unregisterNotesFAB();
    }
  }, [ctx, config?.courseContentId, config?.isOpen, config?.hasNote]);

  // Unregister only on unmount
  useEffect(() => {
    if (!ctx) return;
    return () => ctx.unregisterNotesFAB();
  }, [ctx]);
}
