/**
 * Image validation utilities for the Notes rich-text editor.
 *
 * Constraints:
 * - Max 5 MB per image
 * - Max 10 images per note
 * - Allowed formats: JPEG, PNG, GIF, WebP
 */

export const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB
export const MAX_IMAGES_PER_NOTE = 10;
export const ALLOWED_MIME_TYPES = new Set([
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/webp',
]);
export const ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp'];

export interface ImageValidationError {
  type: 'size' | 'format' | 'count';
  message: string;
}

/**
 * Validate a single image file before insertion.
 */
export function validateImageFile(file: File): ImageValidationError | null {
  if (!ALLOWED_MIME_TYPES.has(file.type)) {
    return {
      type: 'format',
      message: `Unsupported image format "${file.type}". Allowed: JPEG, PNG, GIF, WebP.`,
    };
  }
  if (file.size > MAX_IMAGE_SIZE_BYTES) {
    const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
    return {
      type: 'size',
      message: `Image is too large (${sizeMB} MB). Maximum size is 5 MB.`,
    };
  }
  return null;
}

/**
 * Count images currently in the editor HTML content.
 */
export function countImagesInHtml(html: string): number {
  const matches = html.match(/<img\s/gi);
  return matches ? matches.length : 0;
}

/**
 * Check if adding more images would exceed the per-note limit.
 */
export function canAddImages(currentHtml: string, count: number = 1): ImageValidationError | null {
  const existing = countImagesInHtml(currentHtml);
  if (existing + count > MAX_IMAGES_PER_NOTE) {
    return {
      type: 'count',
      message: `Cannot add ${count > 1 ? `${count} images` : 'image'}. Maximum ${MAX_IMAGES_PER_NOTE} images per note (currently ${existing}).`,
    };
  }
  return null;
}

/**
 * Convert a File to a base64 data URI string.
 */
export function fileToDataUri(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsDataURL(file);
  });
}
