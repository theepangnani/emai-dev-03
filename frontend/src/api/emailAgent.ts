/**
 * AI Email Agent API client — Phase 5.
 *
 * All requests use the shared `api` axios instance which automatically
 * injects the Bearer token and handles 401 refresh/redirect.
 */
import { api } from './client';

// ─── Request / Response Types ─────────────────────────────────────────────────

export interface EmailThreadSummary {
  id: number;
  subject: string;
  recipient_emails: string[];
  recipient_names: string[];
  message_count: number;
  last_message_at: string | null;
  ai_summary: string | null;
  tags: string[];
  is_archived: boolean;
  created_at: string;
}

export interface EmailMessageItem {
  id: number;
  thread_id: number;
  direction: 'outbound' | 'inbound';
  from_email: string;
  from_name: string | null;
  to_emails: string[];
  subject: string;
  body_text: string;
  body_html: string | null;
  ai_draft: boolean;
  ai_tone: string | null;
  status: 'draft' | 'sent' | 'delivered' | 'failed' | 'received';
  sent_at: string | null;
  received_at: string | null;
  created_at: string;
}

export interface EmailThreadDetail extends EmailThreadSummary {
  ai_summary_generated_at: string | null;
  messages: EmailMessageItem[];
}

export interface SendMessageRequest {
  thread_id?: number;
  recipient_emails: string[];
  recipient_names?: string[];
  subject: string;
  body_text: string;
  body_html?: string;
  ai_draft?: boolean;
  ai_tone?: string;
}

export interface AIDraftRequest {
  prompt: string;
  context: string;
  tone?: 'formal' | 'friendly' | 'concise' | 'empathetic';
  language?: 'en' | 'fr';
}

export interface AIDraftResponse {
  subject: string;
  body: string;
  tone: string;
}

export interface AIImproveRequest {
  current_body: string;
  instruction: string;
}

export interface SearchParams {
  q?: string;
  from?: string;
  to?: string;
  date_from?: string;
  date_to?: string;
  skip?: number;
  limit?: number;
}

export interface SearchResponse {
  results: EmailMessageItem[];
  total: number;
  skip: number;
  limit: number;
  query: string | null;
}

export interface EmailStats {
  sent_count: number;
  received_count: number;
  threads_count: number;
  drafts_count: number;
}

export interface ListThreadsParams {
  tab?: 'inbox' | 'sent' | 'drafts' | 'archived';
  tag?: string;
  archived?: boolean;
  skip?: number;
  limit?: number;
}

// ─── API Client ───────────────────────────────────────────────────────────────

export const emailAgentApi = {
  // ── Threads ──────────────────────────────────────────────────────────────

  /**
   * List the current user's email threads.
   * Use `tab` to filter: "inbox" | "sent" | "drafts" | "archived"
   */
  getThreads: (params?: ListThreadsParams) =>
    api.get<EmailThreadSummary[]>('/api/email-agent/threads', { params }),

  /** Get a single thread with all its messages. */
  getThread: (id: number) =>
    api.get<EmailThreadDetail>(`/api/email-agent/threads/${id}`),

  /** Archive (soft-delete) a thread. */
  archiveThread: (id: number) =>
    api.delete(`/api/email-agent/threads/${id}`),

  // ── Messages ─────────────────────────────────────────────────────────────

  /**
   * Send a new email or reply.
   * Omit `thread_id` to create a new thread; provide it to add a reply.
   */
  sendMessage: (data: SendMessageRequest) =>
    api.post<EmailMessageItem>('/api/email-agent/messages', data),

  /** Get a single email message by ID. */
  getMessage: (id: number) =>
    api.get<EmailMessageItem>(`/api/email-agent/messages/${id}`),

  // ── AI Assistance ─────────────────────────────────────────────────────────

  /**
   * Draft a new email using AI.
   * Returns {subject, body, tone}.
   */
  draftWithAI: (data: AIDraftRequest) =>
    api.post<AIDraftResponse>('/api/email-agent/ai/draft', data),

  /**
   * Improve an existing draft based on a plain-language instruction.
   * e.g. "make it shorter", "translate to French", "more formal"
   */
  improveDraft: (data: AIImproveRequest) =>
    api.post<{ body: string }>('/api/email-agent/ai/improve', data),

  /** Generate (or regenerate) a 2-4 sentence AI summary for a thread. */
  summarizeThread: (id: number) =>
    api.post<{ summary: string; generated_at: string }>(`/api/email-agent/threads/${id}/summarize`),

  /** Suggest a reply to the most recent message in a thread. */
  suggestReply: (id: number) =>
    api.post<{ suggested_reply: string }>(`/api/email-agent/threads/${id}/suggest-reply`),

  /** Extract action items from a thread. */
  extractActionItems: (id: number) =>
    api.post<{ action_items: string[] }>(`/api/email-agent/threads/${id}/action-items`),

  // ── Search ────────────────────────────────────────────────────────────────

  /** Full-text search across the user's email threads and messages. */
  search: (params: SearchParams) =>
    api.get<SearchResponse>('/api/email-agent/search', { params }),

  // ── Stats ─────────────────────────────────────────────────────────────────

  /** Get aggregate email statistics for the current user. */
  getStats: () =>
    api.get<EmailStats>('/api/email-agent/stats'),
};
