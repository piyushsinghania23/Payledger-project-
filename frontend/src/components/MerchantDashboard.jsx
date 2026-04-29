import React from 'react';

function MerchantDashboard({ merchant, apiUrl }) {
  const balanceRupees = (merchant.balance_paise || 0) / 100;
  const heldRupees = (merchant.held_balance_paise || 0) / 100;
  const availableRupees = (merchant.available_balance_paise || 0) / 100;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-2xl font-bold text-gray-900 mb-4">{merchant.name}</h2>
      <p className="text-gray-600 mb-6">{merchant.email}</p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Total Balance */}
        <div className="bg-blue-50 rounded-lg p-4">
          <div className="text-sm font-medium text-gray-600">Total Balance</div>
          <div className="text-2xl font-bold text-blue-600 mt-2">
            ₹{balanceRupees.toFixed(2)}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {merchant.balance_paise} paise
          </div>
        </div>

        {/* Held Balance */}
        <div className="bg-yellow-50 rounded-lg p-4">
          <div className="text-sm font-medium text-gray-600">Held Balance</div>
          <div className="text-2xl font-bold text-yellow-600 mt-2">
            ₹{heldRupees.toFixed(2)}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            In pending payouts
          </div>
        </div>

        {/* Available Balance */}
        <div className="bg-green-50 rounded-lg p-4">
          <div className="text-sm font-medium text-gray-600">Available Balance</div>
          <div className="text-2xl font-bold text-green-600 mt-2">
            ₹{availableRupees.toFixed(2)}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            Ready for withdrawal
          </div>
        </div>
      </div>
    </div>
  );
}

export default MerchantDashboard;
