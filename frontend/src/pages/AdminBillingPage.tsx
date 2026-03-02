/**
 * AdminBillingPage — Billing admin dashboard at /admin/billing
 *
 * Shows:
 *   - Summary stat cards: Premium Users, MRR (CAD), New This Month, Churn
 *   - Paginated table of all active subscriptions
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import { billingApi, type AdminSubscriptionItem } from '../api/billing';
import './AdminBillingPage.css';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-CA', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    minimumFractionDigits: 2,
  }).format(amount);
}

function planLabel(name: string): string {
  const labels: Record<string, string> = {
    free: 'Free',
    premium_monthly: 'Premium Mo.',
    premium_yearly: 'Premium Yr.',
  };
  return labels[name] ?? name;
}

// ─── Stat card ────────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string;
  value: string;
  sub?: string;
}

function StatCard({ label, value, sub }: StatCardProps) {
  return (
    <div className="abp-stat-card">
      <span className="abp-stat-label">{label}</span>
      <span className="abp-stat-value">{value}</span>
      {sub && <span className="abp-stat-sub">{sub}</span>}
    </div>
  );
}

// ─── Subscription row ─────────────────────────────────────────────────────────

interface SubRowProps {
  item: AdminSubscriptionItem;
}

function SubRow({ item }: SubRowProps) {
  return (
    <tr className="abp-table-row">
      <td className="abp-table-cell abp-cell-user">
        <span className="abp-user-name">{item.user_name ?? '—'}</span>
        <span className="abp-user-email">{item.user_email ?? '—'}</span>
      </td>
      <td className="abp-table-cell">{planLabel(item.plan_name)}</td>
      <td className="abp-table-cell">
        <span className={`abp-status-badge abp-status-badge--${item.status}`}>
          {item.status.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
        </span>
      </td>
      <td className="abp-table-cell">{formatDate(item.created_at)}</td>
      <td className="abp-table-cell">{formatDate(item.current_period_end)}</td>
    </tr>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function AdminBillingPage() {
  const [page, setPage] = useState(1);

  const statsQuery = useQuery({
    queryKey: ['adminBillingStats'],
    queryFn: () => billingApi.getStats().then((r) => r.data),
  });

  const subsQuery = useQuery({
    queryKey: ['adminSubscriptions', page],
    queryFn: () => billingApi.getSubscriptions(page).then((r) => r.data),
  });

  const stats = statsQuery.data;
  const subs = subsQuery.data;
  const totalPages = subs ? Math.ceil(subs.total / subs.page_size) : 1;

  return (
    <DashboardLayout>
      <div className="abp-page">
        <h1 className="abp-title">Billing Admin</h1>

        {/* ─── Stats cards ─────────────────────────────────────── */}
        {statsQuery.isLoading ? (
          <div className="abp-loading">Loading stats...</div>
        ) : statsQuery.isError ? (
          <div className="abp-error">Failed to load billing stats.</div>
        ) : stats ? (
          <div className="abp-stats-grid">
            <StatCard
              label="Premium Users"
              value={String(stats.total_premium)}
            />
            <StatCard
              label="MRR (CAD)"
              value={formatCurrency(stats.monthly_revenue_cad)}
              sub="monthly recurring revenue"
            />
            <StatCard
              label="New This Month"
              value={`+${stats.new_this_month}`}
            />
            <StatCard
              label="Churned This Month"
              value={String(stats.churn_count)}
            />
          </div>
        ) : null}

        {/* ─── Subscriptions table ─────────────────────────────── */}
        <section className="abp-section">
          <h2 className="abp-section-title">Active Subscriptions</h2>

          {subsQuery.isLoading ? (
            <div className="abp-loading">Loading subscriptions...</div>
          ) : subsQuery.isError ? (
            <div className="abp-error">Failed to load subscriptions.</div>
          ) : subs && subs.items.length === 0 ? (
            <div className="abp-empty">No subscriptions found.</div>
          ) : (
            <>
              <div className="abp-table-wrapper">
                <table className="abp-table">
                  <thead>
                    <tr>
                      <th className="abp-table-th">User</th>
                      <th className="abp-table-th">Plan</th>
                      <th className="abp-table-th">Status</th>
                      <th className="abp-table-th">Since</th>
                      <th className="abp-table-th">Period End</th>
                    </tr>
                  </thead>
                  <tbody>
                    {subs?.items.map((item) => (
                      <SubRow key={item.user_id} item={item} />
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="abp-pagination">
                  <button
                    className="abp-page-btn"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1}
                  >
                    &larr; Prev
                  </button>
                  <span className="abp-page-info">
                    Page {page} of {totalPages}
                  </span>
                  <button
                    className="abp-page-btn"
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page >= totalPages}
                  >
                    Next &rarr;
                  </button>
                </div>
              )}

              {subs && (
                <p className="abp-total-count">
                  Showing {subs.items.length} of {subs.total} subscriptions
                </p>
              )}
            </>
          )}
        </section>
      </div>
    </DashboardLayout>
  );
}
