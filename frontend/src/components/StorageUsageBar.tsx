import "./StorageUsageBar.css";
interface StorageUsageBarProps { usedBytes: number; limitBytes: number; uploadLimitBytes: number; showDetails?: boolean; }
function formatBytes(bytes: number): string {
  if (bytes >= 1073741824) return `${(bytes / 1073741824).toFixed(1)} GB`;
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}
export function StorageUsageBar({ usedBytes, limitBytes, uploadLimitBytes, showDetails = true }: StorageUsageBarProps) {
  const pct = limitBytes > 0 ? Math.min((usedBytes / limitBytes) * 100, 100) : 0;
  const isWarning = pct >= 80; const isCritical = pct >= 90;
  const barClass = isCritical ? "storage-bar-fill critical" : isWarning ? "storage-bar-fill warning" : "storage-bar-fill";
  return (
    <div className="storage-usage-bar">
      <div className="storage-bar-header"><span className="storage-label">Storage</span><span className="storage-text">{formatBytes(usedBytes)} / {formatBytes(limitBytes)}</span></div>
      <div className="storage-bar-track"><div className={barClass} style={{ width: `${pct}%` }} /></div>
      {isWarning && <p className={`storage-warning-text ${isCritical ? "critical" : ""}`}>{isCritical ? "Storage almost full!" : "Approaching storage limit."}</p>}
      {showDetails && <p className="storage-detail-text">Per-file limit: {formatBytes(uploadLimitBytes)}</p>}
    </div>
  );
}
