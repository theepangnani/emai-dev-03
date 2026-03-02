import { api } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ResourceType =
  | 'lesson_plan'
  | 'worksheet'
  | 'presentation'
  | 'assessment'
  | 'video_link'
  | 'activity'
  | 'rubric'
  | 'other';

export interface TeacherResource {
  id: number;
  teacher_id: number;
  teacher_name: string | null;
  title: string;
  description: string | null;
  resource_type: ResourceType;
  subject: string | null;
  grade_level: string | null;
  tags: string[];
  is_public: boolean;
  file_key: string | null;
  external_url: string | null;
  download_count: number;
  avg_rating: number;
  rating_count: number;
  curriculum_expectation: string | null;
  linked_lesson_plan_id: number | null;
  created_at: string;
  updated_at: string | null;
}

export interface TeacherResourceCreate {
  title: string;
  description?: string;
  resource_type: ResourceType;
  subject?: string;
  grade_level?: string;
  tags?: string[];
  is_public?: boolean;
  external_url?: string;
  curriculum_expectation?: string;
}

export interface TeacherResourceUpdate {
  title?: string;
  description?: string;
  resource_type?: ResourceType;
  subject?: string;
  grade_level?: string;
  tags?: string[];
  is_public?: boolean;
  external_url?: string;
  curriculum_expectation?: string;
}

export interface ResourceRating {
  id: number;
  resource_id: number;
  teacher_id: number;
  teacher_name: string | null;
  rating: number;
  comment: string | null;
  created_at: string;
}

export interface ResourceCollection {
  id: number;
  teacher_id: number;
  name: string;
  description: string | null;
  resource_ids: number[];
  resources?: TeacherResource[];
  created_at: string;
  updated_at: string | null;
}

export interface ResourceCollectionCreate {
  name: string;
  description?: string;
  resource_ids?: number[];
}

export interface PaginatedResourceResponse {
  items: TeacherResource[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface SearchParams {
  q?: string;
  subject?: string;
  grade_level?: string;
  resource_type?: ResourceType;
  tags?: string;
  page?: number;
  limit?: number;
}

export interface LibraryStats {
  total_resources: number;
  public_resources: number;
  total_downloads: number;
  total_ratings: number;
  avg_rating: number;
}

export interface RemixResult {
  lesson_plan_id: number;
  title: string;
  plan_type: string;
  message: string;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export const resourceLibraryApi = {
  /** Search/browse public resources (teachers also see their own private ones). */
  searchResources: async (params: SearchParams = {}): Promise<PaginatedResourceResponse> => {
    const query = new URLSearchParams();
    if (params.q) query.set('q', params.q);
    if (params.subject) query.set('subject', params.subject);
    if (params.grade_level) query.set('grade_level', params.grade_level);
    if (params.resource_type) query.set('resource_type', params.resource_type);
    if (params.tags) query.set('tags', params.tags);
    if (params.page) query.set('page', String(params.page));
    if (params.limit) query.set('limit', String(params.limit));
    const { data } = await api.get<PaginatedResourceResponse>(`/api/resources/?${query}`);
    return data;
  },

  /** Get all resources created by the current teacher. */
  getMyResources: async (): Promise<TeacherResource[]> => {
    const { data } = await api.get<TeacherResource[]>('/api/resources/mine');
    return data;
  },

  /** Create a new resource. */
  createResource: async (payload: TeacherResourceCreate): Promise<TeacherResource> => {
    const { data } = await api.post<TeacherResource>('/api/resources/', payload);
    return data;
  },

  /** Update an existing resource. */
  updateResource: async (id: number, payload: TeacherResourceUpdate): Promise<TeacherResource> => {
    const { data } = await api.patch<TeacherResource>(`/api/resources/${id}`, payload);
    return data;
  },

  /** Delete a resource. */
  deleteResource: async (id: number): Promise<void> => {
    await api.delete(`/api/resources/${id}`);
  },

  /** Get a single resource (increments download count). */
  getResource: async (id: number): Promise<TeacherResource> => {
    const { data } = await api.get<TeacherResource>(`/api/resources/${id}`);
    return data;
  },

  /** Upload a file to an existing resource. */
  uploadFile: async (resourceId: number, file: File): Promise<TeacherResource> => {
    const form = new FormData();
    form.append('file', file);
    const { data } = await api.post<TeacherResource>(
      `/api/resources/${resourceId}/upload`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
    return data;
  },

  /** Rate a resource (1-5). */
  rateResource: async (id: number, rating: number, comment?: string): Promise<ResourceRating> => {
    const { data } = await api.post<ResourceRating>(`/api/resources/${id}/rate`, {
      rating,
      comment: comment || null,
    });
    return data;
  },

  /** Remix a resource into a stub lesson plan. */
  remixResource: async (id: number): Promise<RemixResult> => {
    const { data } = await api.post<RemixResult>(`/api/resources/${id}/remix`);
    return data;
  },

  /** Get list of distinct subjects (for filter dropdown). */
  getSubjects: async (): Promise<string[]> => {
    const { data } = await api.get<string[]>('/api/resources/subjects');
    return data;
  },

  /** Admin: get library statistics. */
  getStats: async (): Promise<LibraryStats> => {
    const { data } = await api.get<LibraryStats>('/api/resources/stats');
    return data;
  },

  // --- Collections ---

  /** List personal resource collections. */
  getCollections: async (): Promise<ResourceCollection[]> => {
    const { data } = await api.get<ResourceCollection[]>('/api/resources/collections/');
    return data;
  },

  /** Create a new collection. */
  createCollection: async (payload: ResourceCollectionCreate): Promise<ResourceCollection> => {
    const { data } = await api.post<ResourceCollection>('/api/resources/collections/', payload);
    return data;
  },

  /** Add a resource to a collection. */
  addToCollection: async (collectionId: number, resourceId: number): Promise<ResourceCollection> => {
    const { data } = await api.post<ResourceCollection>(
      `/api/resources/collections/${collectionId}/add?resource_id=${resourceId}`,
    );
    return data;
  },

  /** Get a collection with its full resource list. */
  getCollection: async (collectionId: number): Promise<ResourceCollection> => {
    const { data } = await api.get<ResourceCollection>(
      `/api/resources/collections/${collectionId}`,
    );
    return data;
  },
};
