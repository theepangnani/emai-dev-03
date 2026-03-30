import { api } from './client';

export interface ResourceLinkItem {
  id: number;
  course_content_id: number;
  url: string;
  resource_type: string;
  title: string | null;
  topic_heading: string | null;
  description: string | null;
  thumbnail_url: string | null;
  youtube_video_id: string | null;
  display_order: number;
  created_at: string;
  source?: string;
  channel_name?: string | null;
}

export interface SearchResourcesRequest {
  topic: string;
  grade_level?: string;
  course_name?: string;
}

export interface SearchResourceResult {
  id: number;
  url: string;
  resource_type: string;
  title: string | null;
  description: string | null;
  thumbnail_url: string | null;
  youtube_video_id: string | null;
  channel_name: string | null;
  source: string;
}

export interface ResourceLinkGroup {
  topic_heading: string | null;
  links: ResourceLinkItem[];
}

export interface ResourceLinkCreateData {
  url: string;
  title?: string;
  topic_heading?: string;
  description?: string;
}

export const resourceLinksApi = {
  list: async (courseContentId: number) => {
    const response = await api.get(`/api/course-contents/${courseContentId}/links`);
    return response.data as ResourceLinkGroup[];
  },

  add: async (courseContentId: number, data: ResourceLinkCreateData) => {
    const response = await api.post(`/api/course-contents/${courseContentId}/links`, data);
    return response.data as ResourceLinkItem;
  },

  delete: async (linkId: number) => {
    await api.delete(`/api/resource-links/${linkId}`);
  },

  reExtract: async (courseContentId: number) => {
    const response = await api.post(`/api/course-contents/${courseContentId}/extract-links`);
    return response.data as ResourceLinkItem[];
  },

  searchResources: async (courseContentId: number, data: SearchResourcesRequest) => {
    const response = await api.post(`/api/course-contents/${courseContentId}/search-resources`, data);
    return response.data as SearchResourceResult[];
  },

  pinResource: async (linkId: number) => {
    const response = await api.patch(`/api/resource-links/${linkId}`, { source: 'teacher_shared' });
    return response.data as ResourceLinkItem;
  },

  dismissResource: async (linkId: number) => {
    await api.delete(`/api/resource-links/${linkId}`);
  },

  checkYoutubeSearchAvailable: async () => {
    const response = await api.get('/api/features/youtube-search');
    return response.data as { available: boolean };
  },
};
