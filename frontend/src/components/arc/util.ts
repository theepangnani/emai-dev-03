/**
 * CB-AVATAR-COLORS-001 #4312 — Arc per-user color variant.
 *
 * Deterministic hash of user.id picks one of 6 curated variants. Each user
 * sees their own consistent Arc color across sessions. Default 'rose' for
 * unauthenticated / null id (e.g. login page or stories).
 */
export const ARC_VARIANTS = ['rose', 'sky', 'pine', 'purple', 'amber', 'teal'] as const;
export type ArcVariant = typeof ARC_VARIANTS[number];

export function getArcVariant(userId: number | null | undefined): ArcVariant {
  if (userId == null) return 'rose';
  const idx = Math.abs(userId) % ARC_VARIANTS.length;
  return ARC_VARIANTS[idx];
}
