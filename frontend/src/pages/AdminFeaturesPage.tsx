import { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../api/admin';
import type { FeatureFlagItem, FeatureVariantValue } from '../api/admin';
import { DashboardLayout } from '../components/DashboardLayout';
import { ListSkeleton } from '../components/Skeleton';
import { useToast } from '../components/Toast';
import { PageNav } from '../components/PageNav';
import './AdminFeaturesPage.css';

const VARIANT_OPTIONS: FeatureVariantValue[] = ['off', 'on_50', 'on_for_all'];

export function AdminFeaturesPage() {
  const [features, setFeatures] = useState<FeatureFlagItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<Record<string, boolean>>({});
  const [updatingVariant, setUpdatingVariant] = useState<Record<string, boolean>>({});
  const { toast } = useToast();
  const queryClient = useQueryClient();

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
      queryClient.invalidateQueries({ queryKey: ['feature-toggles'] });
    } catch (err) {
      console.error('Failed to toggle feature:', err);
      toast('Failed to update feature', 'error');
    } finally {
      setToggling(prev => ({ ...prev, [key]: false }));
    }
  };

  const handleVariantChange = async (key: string, variant: FeatureVariantValue) => {
    setUpdatingVariant(prev => ({ ...prev, [key]: true }));
    try {
      const result = await adminApi.updateFeatureVariant(key, variant);
      setFeatures(prev =>
        prev.map(f => f.key === key
          ? { ...f, variant: result.variant, updated_at: new Date().toISOString() }
          : f)
      );
      toast(`${key.replace(/_/g, ' ')} variant set to ${variant}`, 'success');
      queryClient.invalidateQueries({ queryKey: ['feature-toggles'] });
    } catch (err) {
      console.error('Failed to update variant:', err);
      toast('Failed to update variant', 'error');
    } finally {
      setUpdatingVariant(prev => ({ ...prev, [key]: false }));
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
                      aria-label={`Toggle ${f.name}`}
                    />
                    <span className="admin-toggle-slider" />
                  </label>
                  <span className={`admin-feature-status ${f.enabled ? 'on' : 'off'}`}>
                    {toggling[f.key] ? '...' : f.enabled ? 'ON' : 'OFF'}
                  </span>
                  {f.variant !== null && f.variant !== undefined && (
                    <label className="admin-feature-variant">
                      <span className="admin-feature-variant-label">Variant</span>
                      <select
                        value={f.variant}
                        disabled={updatingVariant[f.key]}
                        onChange={(e) => handleVariantChange(f.key, e.target.value as FeatureVariantValue)}
                        aria-label={`${f.name} variant`}
                      >
                        {VARIANT_OPTIONS.map(v => (
                          <option key={v} value={v}>{v}</option>
                        ))}
                      </select>
                    </label>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
