import { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef, type ReactNode } from 'react';

export interface NotesFABConfig {
  courseContentId: number;
  isOpen: boolean;
  onToggle: () => void;
  hasNote?: boolean;
}

/** §6.114 — Study guide context for chatbot Q&A mode */
export interface StudyGuideContext {
  id: number;
  title: string;
  courseId?: number;
}

interface FABContextValue {
  notesFAB: NotesFABConfig | null;
  registerNotesFAB: (config: NotesFABConfig) => void;
  unregisterNotesFAB: () => void;
  studyGuideContext: StudyGuideContext | null;
  setStudyGuideContext: (ctx: StudyGuideContext | null) => void;
  openChatWithQuestion: (text: string) => void;
  clearPendingQuestion: () => void;
  getPendingQuestion: () => string | null;
  subscribePendingQuestion: (listener: () => void) => () => void;
}

const FABContext = createContext<FABContextValue | null>(null);

export function FABProvider({ children }: { children: ReactNode }) {
  const [notesFAB, setNotesFAB] = useState<NotesFABConfig | null>(null);
  const [studyGuideContext, setStudyGuideContextState] = useState<StudyGuideContext | null>(null);
  const pendingQuestionRef = useRef<string | null>(null);
  const pendingQuestionListeners = useRef<Set<() => void>>(new Set());

  const registerNotesFAB = useCallback((config: NotesFABConfig) => {
    setNotesFAB(config);
  }, []);

  const unregisterNotesFAB = useCallback(() => {
    setNotesFAB(null);
  }, []);

  const setStudyGuideContext = useCallback((ctx: StudyGuideContext | null) => {
    setStudyGuideContextState(ctx);
  }, []);

  const openChatWithQuestion = useCallback((text: string) => {
    pendingQuestionRef.current = text;
    pendingQuestionListeners.current.forEach(fn => fn());
  }, []);

  const clearPendingQuestion = useCallback(() => {
    pendingQuestionRef.current = null;
  }, []);

  const subscribePendingQuestion = useCallback((listener: () => void) => {
    pendingQuestionListeners.current.add(listener);
    return () => { pendingQuestionListeners.current.delete(listener); };
  }, []);

  const getPendingQuestion = useCallback(() => pendingQuestionRef.current, []);

  const value = useMemo(() => ({
    notesFAB, registerNotesFAB, unregisterNotesFAB,
    studyGuideContext, setStudyGuideContext,
    openChatWithQuestion, clearPendingQuestion, getPendingQuestion, subscribePendingQuestion,
  }), [notesFAB, registerNotesFAB, unregisterNotesFAB, studyGuideContext, setStudyGuideContext, openChatWithQuestion, clearPendingQuestion, getPendingQuestion, subscribePendingQuestion]);

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
  studyGuideContext: null,
  setStudyGuideContext: () => {},
  openChatWithQuestion: () => {},
  clearPendingQuestion: () => {},
  getPendingQuestion: () => null,
  subscribePendingQuestion: () => () => {},
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
