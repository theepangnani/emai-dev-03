/**
 * Shared helpers for the Bridge components.
 */

export function getInitial(name: string): string {
  return (name.trim()[0] || '?').toUpperCase();
}
