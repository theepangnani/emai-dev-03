import { createContext, useContext, useState, useEffect, useCallback, useRef, type ReactNode } from 'react';

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

export function useFABContext() {
  const ctx = useContext(FABContext);
  if (!ctx) throw new Error('useFABContext must be used within FABProvider');
  return ctx;
}

/**
 * Hook for pages to register a Notes FAB action into the speed dial.
 * Automatically unregisters on unmount.
 */
export function useRegisterNotesFAB(config: NotesFABConfig | null) {
  const { registerNotesFAB, unregisterNotesFAB } = useFABContext();
  const configRef = useRef(config);
  configRef.current = config;

  // Register/update whenever key props change
  useEffect(() => {
    if (configRef.current) {
      registerNotesFAB(configRef.current);
    } else {
      unregisterNotesFAB();
    }
  }, [config?.courseContentId, config?.isOpen, config?.hasNote, registerNotesFAB, unregisterNotesFAB]);

  // Unregister only on unmount
  useEffect(() => {
    return () => unregisterNotesFAB();
  }, [unregisterNotesFAB]);
}
