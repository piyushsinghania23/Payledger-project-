import React, { useState } from 'react';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';

function PayoutForm({ merchant, apiUrl, onPayoutCreated }) {
  const [amount, setAmount] = useState('');
  const [bankAccountId, setBankAccountId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    // Validate inputs
    if (!amount || parseFloat(amount) <= 0) {
      setError('Amount must be greater than 0');
      return;
    }

    if (!bankAccountId.trim()) {
      setError('Bank account ID is required');
      return;
    }

    try {
      setLoading(true);

      // Convert rupees to paise
      const amountPaise = Math.round(parseFloat(amount) * 100);

      // Generate idempotency key
      const idempotencyKey = uuidv4();

      // Make API request
      const response = await axios.post(
        `${apiUrl}/payouts/`,
        {
          merchant_id: merchant.id,
          amount_paise: amountPaise,
          bank_account_id: bankAccountId,
        },
        {
          headers: {
            'Idempotency-Key': idempotencyKey,
          },
        }
      );

      setSuccess(`Payout request created successfully! Payout ID: ${response.data.id}`);
      setAmount('');
      setBankAccountId('');

      // Notify parent to refresh data
      if (onPayoutCreated) {
        onPayoutCreated();
      }
    } catch (err) {
      if (err.response?.data?.error) {
        setError(err.response.data.error);
      } else if (err.response?.status === 400) {
        setError('Invalid payout request. Check your amount and balance.');
      } else {
        setError('Failed to create payout request');
      }
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const availableRupees = (merchant.available_balance_paise || 0) / 100;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-xl font-bold text-gray-900 mb-4">Request Payout</h3>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded mb-4">
          {success}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Amount (Rupees)
          </label>
          <input
            type="number"
            step="0.01"
            min="0"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="1000.00"
            disabled={loading}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"
          />
          <p className="text-xs text-gray-500 mt-1">
            Available: ₹{availableRupees.toFixed(2)}
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Bank Account ID
          </label>
          <input
            type="text"
            value={bankAccountId}
            onChange={(e) => setBankAccountId(e.target.value)}
            placeholder="e.g., ACCOUNT123456"
            disabled={loading}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md transition-colors"
        >
          {loading ? 'Processing...' : 'Request Payout'}
        </button>
      </form>
    </div>
  );
}

export default PayoutForm;
