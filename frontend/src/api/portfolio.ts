/**
 * Portfolio API client — student curated portfolio feature.
 */
import { api } from './client';

export type PortfolioItemType =
  | 'study_guide'
  | 'quiz_result'
  | 'assignment'
  | 'document'
  | 'note'
  | 'achievement';

export interface PortfolioItem {
  id: number;
  portfolio_id: number;
  item_type: PortfolioItemType;
  item_id: number | null;
  title: string;
  description: string | null;
  tags: string[];
  display_order: number;
  created_at: string;
}

export interface Portfolio {
  id: number;
  student_id: number;
  title: string;
  description: string | null;
  is_public: boolean;
  created_at: string;
  updated_at: string | null;
  items: PortfolioItem[];
}

export interface PortfolioCreate {
  title?: string;
  description?: string;
  is_public?: boolean;
}

export interface PortfolioUpdate {
  title?: string;
  description?: string;
  is_public?: boolean;
}

export interface PortfolioItemCreate {
  item_type: PortfolioItemType;
  item_id?: number | null;
  title: string;
  description?: string;
  tags?: string[];
  display_order?: number;
}

export interface PortfolioItemUpdate {
  title?: string;
  description?: string;
  tags?: string[];
  display_order?: number;
}

// -------------------------------------------------------------------------
// API functions
// -------------------------------------------------------------------------

/** Student: get (or auto-create) own portfolio. */
export async function getMyPortfolio(): Promise<Portfolio> {
  const res = await api.get<Portfolio>('/api/portfolio/me');
  return res.data;
}

/** Student: explicitly create a new portfolio. */
export async function createPortfolio(data: PortfolioCreate): Promise<Portfolio> {
  const res = await api.post<Portfolio>('/api/portfolio/', data);
  return res.data;
}

/** Student: update portfolio metadata. */
export async function updatePortfolio(portfolioId: number, data: PortfolioUpdate): Promise<Portfolio> {
  const res = await api.patch<Portfolio>(`/api/portfolio/${portfolioId}`, data);
  return res.data;
}

/** Student: add an item to their portfolio. */
export async function addItem(portfolioId: number, data: PortfolioItemCreate): Promise<PortfolioItem> {
  const res = await api.post<PortfolioItem>(`/api/portfolio/${portfolioId}/items`, data);
  return res.data;
}

/** Student: update a portfolio item. */
export async function updateItem(
  portfolioId: number,
  itemId: number,
  data: PortfolioItemUpdate,
): Promise<PortfolioItem> {
  const res = await api.patch<PortfolioItem>(`/api/portfolio/${portfolioId}/items/${itemId}`, data);
  return res.data;
}

/** Student: remove an item from their portfolio. */
export async function removeItem(portfolioId: number, itemId: number): Promise<void> {
  await api.delete(`/api/portfolio/${portfolioId}/items/${itemId}`);
}

/** Student: reorder items by providing an ordered list of item IDs. */
export async function reorderItems(portfolioId: number, itemIds: number[]): Promise<PortfolioItem[]> {
  const res = await api.post<PortfolioItem[]>(`/api/portfolio/${portfolioId}/reorder`, {
    item_ids: itemIds,
  });
  return res.data;
}

/** Student or parent: get an AI-generated portfolio summary. */
export async function getPortfolioSummary(portfolioId: number): Promise<string> {
  const res = await api.get<{ summary: string }>(`/api/portfolio/${portfolioId}/summary`);
  return res.data.summary;
}

/** Student or parent: export the full portfolio as a JSON object. */
export async function exportPortfolio(portfolioId: number): Promise<object> {
  const res = await api.get<object>(`/api/portfolio/${portfolioId}/export`);
  return res.data;
}

/** Parent: view a linked child's portfolio. */
export async function getChildPortfolio(studentId: number): Promise<Portfolio> {
  const res = await api.get<Portfolio>(`/api/portfolio/student/${studentId}`);
  return res.data;
}
