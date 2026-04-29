/**
 * E6_PLACEHOLDER (CB-EDIGEST-002 #4594).
 *
 * Placeholder for sibling stripe E5 (`DashboardHeader`). The integration
 * merge into `integrate/cb-edigest-002-mvp` will REPLACE this file with
 * the real implementation. Do NOT add behavior here.
 */
export interface DashboardHeaderProps {
  refreshedAt: string;
  lastDigestAt: string | null;
  onRefresh: () => void;
  isRefreshing: boolean;
}

export function DashboardHeader(props: DashboardHeaderProps): JSX.Element {
  // Intentionally minimal — see file header. Reference props so the lint rule
  // for unused parameters is satisfied without renaming the type.
  void props;
  return <div data-testid="dashboard-header-placeholder" />;
}

export default DashboardHeader;
