import { useState, useEffect } from 'react';
import { adminApi } from '../api/admin';
import type { FeatureFlagItem } from '../api/admin';
import { DashboardLayout } from '../components/DashboardLayout';
import { ListSkeleton } from '../components/Skeleton';
import { useToast } from '../components/Toast';
import { PageNav } from '../components/PageNav';
import './AdminFeaturesPage.css';

export function AdminFeaturesPage() {
  const [features, setFeatures] = useState<FeatureFlagItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<Record<string, boolean>>({});
  const { toast } = useToast();

  const loadFeatures = async () => {
    setLoading(true);
    try {
      const data = await adminApi.getFeatures();
      setFeatures(data);
    } catch (err) {
      console.error('Failed to load features:', err);
      toast('Failed to load features', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadFeatures(); }, []);

  const handleToggle = async (key: string, currentEnabled: boolean) => {
    setToggling(prev => ({ ...prev, [key]: true }));
    try {
      const result = await adminApi.updateFeatureToggle(key, !currentEnabled);
      setFeatures(prev =>
        prev.map(f => f.key === key ? { ...f, enabled: result.enabled, updated_at: new Date().toISOString() } : f)
      );
      toast(`${key.replace(/_/g, ' ')} ${result.enabled ? 'enabled' : 'disabled'}`, 'success');
    } catch (err) {
      console.error('Failed to toggle feature:', err);
      toast('Failed to update feature', 'error');
    } finally {
      setToggling(prev => ({ ...prev, [key]: false }));
    }
  };

  return (
    <DashboardLayout>
      <div className="admin-features-page">
        <PageNav items={[
          { label: 'Dashboard', to: '/dashboard' },
          { label: 'Feature Management' },
        ]} />

        <div className="admin-features-header">
          <h2>Feature Management</h2>
          <p className="admin-features-subtitle">
            Toggle platform features on or off. Changes take effect within 5 minutes for all users.
          </p>
        </div>

        {loading ? (
          <ListSkeleton rows={3} />
        ) : features.length === 0 ? (
          <p className="admin-features-empty">No features configured.</p>
        ) : (
          <div className="admin-features-list">
            {features.map(f => (
              <div key={f.key} className={`admin-feature-card ${f.enabled ? 'enabled' : 'disabled'}`}>
                <div className="admin-feature-info">
                  <div className="admin-feature-name">{f.name}</div>
                  {f.description && (
                    <div className="admin-feature-desc">{f.description}</div>
                  )}
                  {f.updated_at && (
                    <div className="admin-feature-updated">
                      Last updated: {new Date(f.updated_at).toLocaleDateString()}
                    </div>
                  )}
                </div>
                <div className="admin-feature-toggle">
                  <label className="admin-toggle-switch">
                    <input
                      type="checkbox"
                      checked={f.enabled}
                      disabled={toggling[f.key]}
                      onChange={() => handleToggle(f.key, f.enabled)}
                    />
                    <span className="admin-toggle-slider" />
                  </label>
                  <span className={`admin-feature-status ${f.enabled ? 'on' : 'off'}`}>
                    {toggling[f.key] ? '...' : f.enabled ? 'ON' : 'OFF'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
