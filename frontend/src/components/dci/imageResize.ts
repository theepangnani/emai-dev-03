/**
 * imageResize — on-device JPEG resize so we never upload raw 8MP camera
 * frames. Lazy-loaded by CheckInCapturePage so the canvas/Image cost only
 * lands on devices that actually take a photo.
 *
 * Strategy: shrink the largest dimension first (quality preserved) and
 * then iteratively step JPEG quality down until we're under maxBytes.
 * Falls back to the original blob if we somehow can't get under target.
 */

const DEFAULT_MAX_BYTES = 500 * 1024;
const MAX_DIMENSION = 1600;
const QUALITY_STEPS = [0.85, 0.75, 0.65, 0.55, 0.45];

export async function resizeJpegBlob(
  input: Blob,
  maxBytes: number = DEFAULT_MAX_BYTES,
): Promise<Blob> {
  if (input.size <= maxBytes) return input;
  const url = URL.createObjectURL(input);
  try {
    const img = await loadImage(url);
    const scale =
      Math.max(img.naturalWidth, img.naturalHeight) > MAX_DIMENSION
        ? MAX_DIMENSION / Math.max(img.naturalWidth, img.naturalHeight)
        : 1;
    const w = Math.round(img.naturalWidth * scale);
    const h = Math.round(img.naturalHeight * scale);
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    if (!ctx) return input;
    ctx.drawImage(img, 0, 0, w, h);

    for (const q of QUALITY_STEPS) {
      const blob = await canvasToBlob(canvas, q);
      if (blob && blob.size <= maxBytes) return blob;
      if (blob && q === QUALITY_STEPS[QUALITY_STEPS.length - 1]) {
        return blob;
      }
    }
    return input;
  } finally {
    URL.revokeObjectURL(url);
  }
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = (err) => reject(err);
    img.src = src;
  });
}

function canvasToBlob(
  canvas: HTMLCanvasElement,
  quality: number,
): Promise<Blob | null> {
  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), 'image/jpeg', quality);
  });
}
