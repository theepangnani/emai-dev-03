import { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import type { ReactNode } from 'react';
import { ReportBugLink } from './ReportBugLink';
import './Toast.css';

type ToastType = 'success' | 'error' | 'info';

interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const removeToast = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) { clearTimeout(timer); timers.current.delete(id); }
  }, []);

  const toast = useCallback((message: string, type: ToastType = 'info') => {
    const id = ++nextId;
    setToasts(prev => [...prev.slice(-4), { id, message, type }]);
    const timer = setTimeout(() => removeToast(id), type === 'error' ? 5000 : 3000);
    timers.current.set(id, timer);
  }, [removeToast]);

  useEffect(() => {
    return () => { timers.current.forEach(t => clearTimeout(t)); };
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="toast-container" role="status" aria-live="polite">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`toast toast-${t.type}`}
            onClick={() => removeToast(t.id)}
            {...(t.type === 'error' ? { role: 'alert', 'aria-live': 'assertive' } : {})}
          >
            <span className="toast-icon">
              {t.type === 'success' ? '\u2713' : t.type === 'error' ? '\u2717' : '\u2139'}
            </span>
            <span className="toast-message">{t.message}</span>
            {t.type === 'error' && <ReportBugLink errorMessage={t.message} />}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}
