import { api } from './client';

export interface StorageUsage {
  used_bytes: number;
  used_mb: number;
  quota_bytes: number;
  quota_mb: number;
  usage_percent: number;
}

export interface StorageQuota {
  tier: string;
  quota_bytes: number;
  quota_mb: number;
  quota_gb: number;
  max_file_size_bytes: number;
  max_file_size_mb: number;
}

export const storageApi = {
  getUsage: () => api.get<StorageUsage>('/api/storage/usage').then(r => r.data),
  getQuota: () => api.get<StorageQuota>('/api/storage/quota').then(r => r.data),
};
