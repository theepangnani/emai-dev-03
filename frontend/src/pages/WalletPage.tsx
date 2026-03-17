import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { walletApi } from '../api/wallet';
import PackageSelector from '../components/PackageSelector';
import TransactionHistory from '../components/TransactionHistory';
import './WalletPage.css';

export default function WalletPage() {
  const queryClient = useQueryClient();
  const [txnSkip, setTxnSkip] = useState(0);
  const txnLimit = 20;

  const { data: wallet, isLoading: walletLoading } = useQuery({
    queryKey: ['wallet'],
    queryFn: walletApi.getWallet,
  });

  const { data: packages } = useQuery({
    queryKey: ['wallet-packages'],
    queryFn: walletApi.getPackages,
  });

  const { data: transactions } = useQuery({
    queryKey: ['wallet-transactions', txnSkip],
    queryFn: () => walletApi.getTransactions(txnSkip, txnLimit),
  });

  const enrollMutation = useMutation({
    mutationFn: walletApi.enrollPackage,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wallet'] });
      queryClient.invalidateQueries({ queryKey: ['wallet-transactions'] });
    },
  });

  if (walletLoading) {
    return <div className="wallet-page"><p>Loading wallet...</p></div>;
  }

  return (
    <div className="wallet-page">
      <h2>Digital Wallet</h2>

      {wallet && (
        <div className="wallet-balance-card">
          <div className="balance-section">
            <div className="balance-item">
              <span className="balance-label">Total Credits</span>
              <span className="balance-value total">{wallet.total_credits}</span>
            </div>
            <div className="balance-item">
              <span className="balance-label">Package Credits</span>
              <span className="balance-value">{wallet.package_credits}</span>
            </div>
            <div className="balance-item">
              <span className="balance-label">Purchased Credits</span>
              <span className="balance-value">{wallet.purchased_credits}</span>
            </div>
          </div>
          <div className="package-badge">
            {wallet.package.charAt(0).toUpperCase() + wallet.package.slice(1)} Plan
          </div>
        </div>
      )}

      {packages && wallet && (
        <PackageSelector
          tiers={packages}
          currentPackage={wallet.package}
          onEnroll={(name) => enrollMutation.mutate(name)}
          isLoading={enrollMutation.isPending}
        />
      )}

      {transactions && (
        <TransactionHistory
          transactions={transactions.items}
          total={transactions.total}
          skip={txnSkip}
          limit={txnLimit}
          onPageChange={setTxnSkip}
        />
      )}
    </div>
  );
}
