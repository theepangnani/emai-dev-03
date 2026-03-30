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

  pin: async (linkId: number) => {
    const response = await api.patch(`/api/resource-links/${linkId}/pin`);
    return response.data as ResourceLinkItem;
  },

  dismiss: async (linkId: number) => {
    await api.delete(`/api/resource-links/${linkId}/dismiss`);
  },

  reExtract: async (courseContentId: number) => {
    const response = await api.post(`/api/course-contents/${courseContentId}/extract-links`);
    return response.data as ResourceLinkItem[];
  },
};
