// CB-KIDPHOTO-001 (#4301) — kid profile photo upload + delete API client.
import { api } from './client';

export interface KidPhotoUploadResponse {
  profile_photo_url: string;
}

export async function uploadKidPhoto(
  studentId: number,
  file: File,
): Promise<KidPhotoUploadResponse> {
  const form = new FormData();
  form.append('file', file);
  const response = await api.post(
    `/api/parent/children/${studentId}/photo`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return response.data as KidPhotoUploadResponse;
}

export async function deleteKidPhoto(studentId: number): Promise<void> {
  await api.delete(`/api/parent/children/${studentId}/photo`);
}
