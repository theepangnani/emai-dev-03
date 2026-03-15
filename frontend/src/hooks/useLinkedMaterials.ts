import { useQuery } from '@tanstack/react-query';
import { courseContentsApi, type LinkedMaterialItem } from '../api/client';

/**
 * Hook to fetch linked materials (master + siblings) for a course content.
 * Returns empty array for standalone materials.
 */
export function useLinkedMaterials(contentId: number | undefined, materialGroupId: number | null | undefined) {
  return useQuery<LinkedMaterialItem[]>({
    queryKey: ['linked-materials', contentId],
    queryFn: () => courseContentsApi.getLinkedMaterials(contentId!),
    enabled: !!contentId && !!materialGroupId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
