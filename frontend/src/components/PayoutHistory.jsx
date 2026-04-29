import React, { useState, useEffect } from 'react';
import axios from 'axios';

function PayoutHistory({ merchant, apiUrl }) {
  const [payouts, setPayouts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchPayouts();
    // Refresh every 5 seconds to show live status updates
    const interval = setInterval(fetchPayouts, 5000);
    return () => clearInterval(interval);
  }, [merchant.id]);

  const fetchPayouts = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${apiUrl}/payouts/?merchant=${merchant.id}`);
      const payoutList = response.data.results || response.data;
      setPayouts(Array.isArray(payoutList) ? payoutList : []);
      setError(null);
    } catch (err) {
      setError('Failed to fetch payout history');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'pending':
        return 'bg-yellow-50 text-yellow-800 border-yellow-200';
      case 'processing':
        return 'bg-blue-50 text-blue-800 border-blue-200';
      case 'completed':
        return 'bg-green-50 text-green-800 border-green-200';
      case 'failed':
        return 'bg-red-50 text-red-800 border-red-200';
      default:
        return 'bg-gray-50 text-gray-800 border-gray-200';
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'pending':
        return '🟡 Pending';
      case 'processing':
        return '🔵 Processing';
      case 'completed':
        return '✅ Completed';
      case 'failed':
        return '❌ Failed';
      default:
        return status;
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString() + ' ' +
           new Date(dateString).toLocaleTimeString();
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-xl font-bold text-gray-900 mb-4">Payout History</h3>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {loading && payouts.length === 0 ? (
        <div className="text-center text-gray-500 py-8">Loading payouts...</div>
      ) : payouts.length === 0 ? (
        <div className="text-center text-gray-500 py-8">No payouts yet</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-semibold text-gray-900">
                  Payout ID
                </th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-gray-900">
                  Amount
                </th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-gray-900">
                  Bank Account
                </th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-gray-900">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-gray-900">
                  Created
                </th>
              </tr>
            </thead>
            <tbody>
              {payouts.map((payout) => (
                <tr key={payout.id} className="border-b border-gray-200 hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <code className="text-xs bg-gray-100 px-2 py-1 rounded">
                      {payout.id.substring(0, 8)}...
                    </code>
                  </td>
                  <td className="px-4 py-3 font-semibold text-gray-900">
                    ₹{(payout.amount_paise / 100).toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {payout.bank_account_id}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor(payout.status)}`}>
                      {getStatusBadge(payout.status)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {formatDate(payout.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default PayoutHistory;
