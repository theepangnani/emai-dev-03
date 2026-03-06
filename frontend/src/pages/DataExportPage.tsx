import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { dataExportApi, type DataExportRequest } from '../api/dataExport';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import './DataExportPage.css';

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '--';
  return new Date(dateStr).toLocaleString();
}

function statusLabel(status: string): string {
  switch (status) {
    case 'pending': return 'Pending';
    case 'processing': return 'Processing...';
    case 'completed': return 'Ready';
    case 'failed': return 'Failed';
    case 'expired': return 'Expired';
    default: return status;
  }
}

function statusClass(status: string): string {
  switch (status) {
    case 'completed': return 'export-status-ready';
    case 'failed': return 'export-status-failed';
    case 'expired': return 'export-status-expired';
    case 'pending':
    case 'processing': return 'export-status-pending';
    default: return '';
  }
}

export function DataExportPage() {
  const queryClient = useQueryClient();
  const [downloading, setDownloading] = useState<string | null>(null);

  const exportsQuery = useQuery({
    queryKey: ['dataExports'],
    queryFn: dataExportApi.listExports,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (Array.isArray(data) && data.some((e: DataExportRequest) => e.status === 'pending' || e.status === 'processing')) {
        return 5000;
      }
      return false;
    },
  });

  const requestMutation = useMutation({
    mutationFn: dataExportApi.requestExport,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dataExports'] });
    },
  });

  const handleDownload = async (token: string) => {
    setDownloading(token);
    try {
      await dataExportApi.downloadExport(token);
    } catch {
      // Error handled by axios interceptor
    } finally {
      setDownloading(null);
    }
  };

  const exports = exportsQuery.data || [];
  const hasActiveExport = exports.some(
    (e) => e.status === 'pending' || e.status === 'processing'
  );

  return (
    <DashboardLayout>
      <div className="data-export-page">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Settings', to: '/dashboard' },
          { label: 'Data Export' },
        ]} />

        <div className="data-export-header">
          <div>
            <h1 className="data-export-title">Export My Data</h1>
            <p className="data-export-desc">
              Download a copy of your personal data stored in ClassBridge.
              This includes your profile, messages, study materials, grades,
              notifications, and any uploaded files. Your export will be
              available for 48 hours after generation.
            </p>
          </div>
        </div>

        <div className="data-export-action">
          <button
            className="data-export-btn"
            onClick={() => requestMutation.mutate()}
            disabled={requestMutation.isPending || hasActiveExport}
          >
            {requestMutation.isPending
              ? 'Requesting...'
              : hasActiveExport
                ? 'Export in progress...'
                : 'Request Data Export'}
          </button>
          {requestMutation.isError && (
            <p className="data-export-error">
              {(requestMutation.error as Error & { response?: { data?: { detail?: string } } })
                ?.response?.data?.detail || 'Failed to request export. Please try again later.'}
            </p>
          )}
        </div>

        <div className="data-export-info">
          <h3>What is included in the export?</h3>
          <ul>
            <li>Your profile information (name, email, role, settings)</li>
            <li>Student profile details (if applicable)</li>
            <li>Linked children information (for parent accounts)</li>
            <li>Courses and enrollment data</li>
            <li>Assignments and grades</li>
            <li>Study guides, flashcards, and quizzes</li>
            <li>Quiz results and scores</li>
            <li>Messages and conversations</li>
            <li>Tasks</li>
            <li>Notifications</li>
            <li>Teacher communications</li>
            <li>Uploaded course material files</li>
          </ul>
        </div>

        {exportsQuery.isLoading && <p className="data-export-loading">Loading export history...</p>}

        {exports.length > 0 && (
          <div className="data-export-history">
            <h3>Export History</h3>
            <div className="data-export-list">
              {exports.map((exp) => (
                <div key={exp.id} className="data-export-item">
                  <div className="data-export-item-info">
                    <span className={`data-export-status ${statusClass(exp.status)}`}>
                      {statusLabel(exp.status)}
                    </span>
                    <span className="data-export-date">
                      Requested: {formatDate(exp.created_at)}
                    </span>
                    {exp.expires_at && exp.status === 'completed' && (
                      <span className="data-export-expires">
                        Expires: {formatDate(exp.expires_at)}
                      </span>
                    )}
                  </div>
                  <div className="data-export-item-actions">
                    {exp.download_url && exp.status === 'completed' && (
                      <button
                        className="data-export-download-btn"
                        onClick={() => {
                          const token = exp.download_url!.split('/exports/')[1]?.split('/download')[0];
                          if (token) handleDownload(token);
                        }}
                        disabled={downloading !== null}
                      >
                        {downloading ? 'Downloading...' : 'Download'}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
