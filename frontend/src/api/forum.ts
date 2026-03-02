import { api as apiClient } from './client';

export interface ForumCategory {
  id: number;
  name: string;
  description?: string;
  board_id?: number;
  display_order: number;
  is_active: boolean;
  thread_count: number;
  created_at: string;
}

export interface ForumThread {
  id: number;
  category_id: number;
  author_id: number;
  author_name: string;
  title: string;
  body: string;
  is_pinned: boolean;
  is_locked: boolean;
  view_count: number;
  reply_count: number;
  is_moderated: boolean;
  approved_at?: string;
  created_at: string;
  updated_at?: string;
}

export interface ForumPost {
  id: number;
  thread_id: number;
  author_id: number;
  author_name: string;
  body: string;
  like_count: number;
  is_moderated: boolean;
  approved_at?: string;
  parent_post_id?: number;
  created_at: string;
  updated_at?: string;
  replies: ForumPost[];
}

export interface ForumListResponse {
  items: ForumThread[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface ThreadDetailResponse {
  thread: ForumThread;
  posts: ForumPost[];
}

export interface ForumThreadCreate {
  category_id: number;
  title: string;
  body: string;
}

export interface ForumPostCreate {
  body: string;
  parent_post_id?: number;
}

export interface LikeResponse {
  liked: boolean;
  like_count: number;
}

export const forumApi = {
  getCategories: async (board_id?: number): Promise<ForumCategory[]> => {
    const params = board_id !== undefined ? { board_id } : {};
    const res = await apiClient.get<ForumCategory[]>('/api/forum/categories', { params });
    return res.data;
  },

  getThreads: async (categoryId: number, page = 1, limit = 20): Promise<ForumListResponse> => {
    const res = await apiClient.get<ForumListResponse>(
      `/api/forum/categories/${categoryId}/threads`,
      { params: { page, limit } },
    );
    return res.data;
  },

  getThread: async (threadId: number): Promise<ThreadDetailResponse> => {
    const res = await apiClient.get<ThreadDetailResponse>(`/api/forum/threads/${threadId}`);
    return res.data;
  },

  createThread: async (data: ForumThreadCreate): Promise<ForumThread> => {
    const res = await apiClient.post<ForumThread>('/api/forum/threads', data);
    return res.data;
  },

  createPost: async (threadId: number, data: ForumPostCreate): Promise<ForumPost> => {
    const res = await apiClient.post<ForumPost>(`/api/forum/threads/${threadId}/posts`, data);
    return res.data;
  },

  likePost: async (postId: number): Promise<LikeResponse> => {
    const res = await apiClient.post<LikeResponse>(`/api/forum/posts/${postId}/like`);
    return res.data;
  },

  searchForum: async (q: string, page = 1, limit = 20): Promise<ForumListResponse> => {
    const res = await apiClient.get<ForumListResponse>('/api/forum/search', {
      params: { q, page, limit },
    });
    return res.data;
  },

  deleteThread: async (threadId: number): Promise<void> => {
    await apiClient.delete(`/api/forum/threads/${threadId}`);
  },

  pinThread: async (threadId: number): Promise<ForumThread> => {
    const res = await apiClient.patch<ForumThread>(`/api/forum/threads/${threadId}/pin`);
    return res.data;
  },

  lockThread: async (threadId: number): Promise<ForumThread> => {
    const res = await apiClient.patch<ForumThread>(`/api/forum/threads/${threadId}/lock`);
    return res.data;
  },
};
