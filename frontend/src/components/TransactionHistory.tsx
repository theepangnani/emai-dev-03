import type { WalletTransactionItem } from '../api/wallet';
import './TransactionHistory.css';

interface TransactionHistoryProps {
  transactions: WalletTransactionItem[];
  total: number;
  skip: number;
  limit: number;
  onPageChange: (newSkip: number) => void;
}

export default function TransactionHistory({
  transactions,
  total,
  skip,
  limit,
  onPageChange,
}: TransactionHistoryProps) {
  const totalPages = Math.ceil(total / limit);
  const currentPage = Math.floor(skip / limit) + 1;

  const formatType = (type: string) => {
    const map: Record<string, string> = {
      package_credit: 'Package Credit',
      purchase_credit: 'Purchase',
      debit: 'Usage',
      refund: 'Refund',
    };
    return map[type] || type;
  };

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString('en-CA', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });

  if (transactions.length === 0) {
    return (
      <div className="transaction-history">
        <h3>Transaction History</h3>
        <p className="no-transactions">No transactions yet.</p>
      </div>
    );
  }

  return (
    <div className="transaction-history">
      <h3>Transaction History</h3>
      <table className="txn-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Type</th>
            <th>Amount</th>
            <th>Balance</th>
            <th>Note</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((txn) => (
            <tr key={txn.id}>
              <td>{formatDate(txn.created_at)}</td>
              <td>
                <span className={`txn-badge ${txn.transaction_type}`}>
                  {formatType(txn.transaction_type)}
                </span>
              </td>
              <td className={txn.amount >= 0 ? 'amount-positive' : 'amount-negative'}>
                {txn.amount >= 0 ? '+' : ''}
                {txn.amount}
              </td>
              <td>{txn.balance_after}</td>
              <td className="txn-note">{txn.note || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {totalPages > 1 && (
        <div className="txn-pagination">
          <button
            disabled={currentPage <= 1}
            onClick={() => onPageChange(skip - limit)}
          >
            Previous
          </button>
          <span>
            Page {currentPage} of {totalPages}
          </span>
          <button
            disabled={currentPage >= totalPages}
            onClick={() => onPageChange(skip + limit)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
