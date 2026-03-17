import { useState } from 'react';
import type { PackageTier } from '../api/wallet';
import './PackageSelector.css';

interface PackageSelectorProps {
  tiers: PackageTier[];
  currentPackage: string;
  onEnroll: (name: string) => void;
  isLoading?: boolean;
}

export default function PackageSelector({
  tiers,
  currentPackage,
  onEnroll,
  isLoading,
}: PackageSelectorProps) {
  const [selectedTier, setSelectedTier] = useState<string | null>(null);

  const formatPrice = (cents: number) =>
    cents === 0 ? 'Free' : `$${(cents / 100).toFixed(2)}/mo`;

  return (
    <div className="package-selector">
      <h3>Subscription Tiers</h3>
      <div className="package-grid">
        {tiers.map((tier) => {
          const isCurrent = tier.name === currentPackage;
          return (
            <div
              key={tier.id}
              className={`package-card ${isCurrent ? 'current' : ''} ${
                selectedTier === tier.name ? 'selected' : ''
              }`}
              onClick={() => !isCurrent && setSelectedTier(tier.name)}
            >
              {isCurrent && <span className="badge-current">Current</span>}
              <h4>{tier.name.charAt(0).toUpperCase() + tier.name.slice(1)}</h4>
              <p className="price">{formatPrice(tier.price_cents)}</p>
              <p className="credits">
                {tier.monthly_credits > 0
                  ? `${tier.monthly_credits} credits/month`
                  : 'Basic allocation'}
              </p>
              {!isCurrent && (
                <button
                  className="btn-enroll"
                  disabled={isLoading}
                  onClick={(e) => {
                    e.stopPropagation();
                    onEnroll(tier.name);
                  }}
                >
                  {tier.price_cents > 0 ? 'Upgrade' : 'Switch'}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
