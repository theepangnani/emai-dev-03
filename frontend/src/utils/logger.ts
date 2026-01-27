/**
 * Frontend logging utility.
 * In development: logs to console and sends to backend.
 * In production: only sends errors to backend, minimal console output.
 */

import { api } from '../api/client';

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogContext {
  url?: string;
  userAgent?: string;
  userId?: number;
  component?: string;
  [key: string]: unknown;
}

interface LogEntry {
  level: LogLevel;
  message: string;
  context: LogContext;
  timestamp: string;
}

class Logger {
  private isDevelopment: boolean;
  private buffer: LogEntry[] = [];
  private flushInterval: number | null = null;
  private readonly BUFFER_SIZE = 10;
  private readonly FLUSH_INTERVAL_MS = 5000;

  constructor() {
    this.isDevelopment = import.meta.env.DEV;

    // Start periodic flush in production
    if (!this.isDevelopment) {
      this.flushInterval = window.setInterval(() => this.flush(), this.FLUSH_INTERVAL_MS);
    }

    // Flush on page unload
    window.addEventListener('beforeunload', () => this.flush());
  }

  private getContext(additionalContext?: Partial<LogContext>): LogContext {
    return {
      url: window.location.href,
      userAgent: navigator.userAgent,
      ...additionalContext,
    };
  }

  private log(level: LogLevel, message: string, context?: Partial<LogContext>): void {
    const entry: LogEntry = {
      level,
      message,
      context: this.getContext(context),
      timestamp: new Date().toISOString(),
    };

    // Console logging based on environment
    if (this.isDevelopment) {
      // Development: log everything to console
      const consoleMethods: Record<LogLevel, (...args: unknown[]) => void> = {
        debug: console.debug,
        info: console.info,
        warn: console.warn,
        error: console.error,
      };
      consoleMethods[level](`[${level.toUpperCase()}] ${message}`, context || '');
    } else {
      // Production: only log errors to console
      if (level === 'error') {
        console.error(`[ERROR] ${message}`);
      }
    }

    // Send to backend
    if (this.isDevelopment) {
      // Development: send immediately
      this.sendToBackend(entry);
    } else {
      // Production: buffer and batch (only warnings and errors)
      if (level === 'warn' || level === 'error') {
        this.buffer.push(entry);
        if (this.buffer.length >= this.BUFFER_SIZE) {
          this.flush();
        }
      }
    }
  }

  private async sendToBackend(entry: LogEntry): Promise<void> {
    try {
      await api.post('/api/logs/', {
        level: entry.level,
        message: entry.message,
        context: entry.context,
      });
    } catch {
      // Silently fail - don't create infinite loops on logging failures
    }
  }

  private async flush(): Promise<void> {
    if (this.buffer.length === 0) return;

    const entries = [...this.buffer];
    this.buffer = [];

    try {
      await api.post('/api/logs/batch', {
        entries: entries.map((e) => ({
          level: e.level,
          message: e.message,
          context: e.context,
        })),
      });
    } catch {
      // Silently fail
    }
  }

  debug(message: string, context?: Partial<LogContext>): void {
    this.log('debug', message, context);
  }

  info(message: string, context?: Partial<LogContext>): void {
    this.log('info', message, context);
  }

  warn(message: string, context?: Partial<LogContext>): void {
    this.log('warn', message, context);
  }

  error(message: string, context?: Partial<LogContext>): void {
    this.log('error', message, context);
  }

  // Log errors from catch blocks with full error details
  logError(error: unknown, message?: string, context?: Partial<LogContext>): void {
    const errorMessage = error instanceof Error ? error.message : String(error);
    const stack = error instanceof Error ? error.stack : undefined;

    this.error(message || errorMessage, {
      ...context,
      errorMessage,
      stack,
    });
  }

  destroy(): void {
    if (this.flushInterval) {
      window.clearInterval(this.flushInterval);
    }
    this.flush();
  }
}

// Export singleton instance
export const logger = new Logger();

// Also export the class for testing
export { Logger };
