import axios from 'axios';

const API_BASE_URL =
  import.meta.env.VITE_API_URL ??
  (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000');

export interface WaitlistMunicipality {
  name: string;
  count: number;
}

export interface WaitlistStats {
  total: number | null;
  by_municipality: WaitlistMunicipality[];
}

/**
 * Public (unauthenticated) waitlist stats — CB-DEMO-001 (#3604).
 * Uses a bare axios call to avoid the authenticated interceptor chain.
 */
export async function getWaitlistStats(): Promise<WaitlistStats> {
  const response = await axios.get<WaitlistStats>(
    `${API_BASE_URL}/api/v1/public/waitlist-stats`,
    { timeout: 10_000 },
  );
  return response.data;
}
