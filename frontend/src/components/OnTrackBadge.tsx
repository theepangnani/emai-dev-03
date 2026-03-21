import { useQuery } from '@tanstack/react-query';
import { parentApi } from '../api/client';
import type { OnTrackSignal } from '../api/client';
import './OnTrackBadge.css';

const LABELS: Record<OnTrackSignal['signal'], string> = {
  green: 'On Track',
  yellow: 'Needs Attention',
  red: 'At Risk',
};

interface OnTrackBadgeProps {
  studentId: number;
}

export function OnTrackBadge({ studentId }: OnTrackBadgeProps) {
  const { data } = useQuery({
    queryKey: ['on-track', studentId],
    queryFn: () => parentApi.getChildOnTrack(studentId),
    enabled: !!studentId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  if (!data) return null;

  const label = LABELS[data.signal];

  return (
    <span
      className={`on-track-badge on-track-badge--${data.signal}`}
      aria-label={`${label}: ${data.reason}`}
    >
      <span className="on-track-dot" />
      {label}
      <span className="on-track-tooltip">{data.reason}</span>
    </span>
  );
}
