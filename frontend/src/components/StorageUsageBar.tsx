/**
 * StorageUsageBar — compact iCloud/Google Drive-style storage usage indicator (#572).
 * Displays used vs. total quota with a CSS progress bar.
 */
import { useQuery } from '@tanstack/react-query';
import { storageApi, type StorageUsage } from '../api/storage';
import './StorageUsageBar.css';

function formatMb(mb: number): string {
  if (mb >= 1024) {
    return `${(mb / 1024).toFixed(1)} GB`;
  }
  return `${mb.toFixed(0)} MB`;
}

export function StorageUsageBar() {
  const { data, isLoading, isError } = useQuery<StorageUsage>({
    queryKey: ['storageUsage'],
    queryFn: storageApi.getUsage,
    staleTime: 60_000, // refresh every minute
  });

  if (isLoading) {
    return <div className="storage-usage-bar storage-usage-loading">Loading storage info...</div>;
  }

  if (isError || !data) {
    return null;
  }

  const { used_mb, quota_mb, usage_percent } = data;
  const isFree = quota_mb <= 512; // 500 MB free tier
  const isNearLimit = usage_percent >= 80;
  const isOverLimit = usage_percent >= 95;

  const barClass = isOverLimit
    ? 'storage-bar-fill storage-bar-danger'
    : isNearLimit
    ? 'storage-bar-fill storage-bar-warning'
    : 'storage-bar-fill';

  return (
    <div className="storage-usage-bar">
      <div className="storage-usage-header">
        <span className="storage-usage-label">Storage</span>
        <span className="storage-usage-numbers">
          {formatMb(used_mb)} / {formatMb(quota_mb)}{' '}
          <span className="storage-usage-percent">({usage_percent.toFixed(1)}%)</span>
        </span>
      </div>
      <div className="storage-bar-track" role="progressbar" aria-valuenow={usage_percent} aria-valuemin={0} aria-valuemax={100}>
        <div
          className={barClass}
          style={{ width: `${Math.min(usage_percent, 100)}%` }}
        />
      </div>
      {isFree && (
        <p className="storage-upgrade-hint">
          Upgrade to Premium for 5 GB of storage.
        </p>
      )}
    </div>
  );
}
