import React, { useState, useEffect } from 'react';
import axios from 'axios';
import MerchantDashboard from './components/MerchantDashboard.jsx';
import PayoutForm from './components/PayoutForm.jsx';
import PayoutHistory from './components/PayoutHistory.jsx';
import './App.css';

const API_URL = import.meta.env.VITE_API_URL || '/api/v1';

function App() {
  const [merchants, setMerchants] = useState([]);
  const [selectedMerchant, setSelectedMerchant] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch merchants on mount
  useEffect(() => {
    fetchMerchants();
  }, []);

  const fetchMerchants = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_URL}/merchants/`);
      setMerchants(response.data.results || response.data);
      if (response.data.results && response.data.results.length > 0) {
        setSelectedMerchant(response.data.results[0]);
      } else if (response.data && response.data.length > 0) {
        setSelectedMerchant(response.data[0]);
      }
      setError(null);
    } catch (err) {
      setError('Failed to fetch merchants');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleMerchantChange = (merchant) => {
    setSelectedMerchant(merchant);
  };

  const handlePayoutCreated = () => {
    // Refresh the selected merchant's data
    if (selectedMerchant) {
      fetchMerchantDetails(selectedMerchant.id);
    }
  };

  const fetchMerchantDetails = async (merchantId) => {
    try {
      const response = await axios.get(`${API_URL}/merchants/${merchantId}/`);
      const updatedMerchants = merchants.map(m =>
        m.id === merchantId ? response.data : m
      );
      setMerchants(updatedMerchants);
      setSelectedMerchant(response.data);
    } catch (err) {
      console.error('Failed to fetch merchant details:', err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="text-lg text-gray-600">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
          <h1 className="text-3xl font-bold text-gray-900">Playto Payout Engine</h1>
          <p className="text-gray-600 mt-2">Manage merchant payouts and balances</p>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}

        {/* Merchant Selector */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Select Merchant
          </label>
          <select
            value={selectedMerchant?.id || ''}
            onChange={(e) => {
              const merchant = merchants.find(m => m.id === e.target.value);
              handleMerchantChange(merchant);
            }}
            className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">Choose a merchant...</option>
            {merchants.map(merchant => (
              <option key={merchant.id} value={merchant.id}>
                {merchant.name} ({merchant.email})
              </option>
            ))}
          </select>
        </div>

        {selectedMerchant && (
          <div className="space-y-6">
            {/* Dashboard */}
            <MerchantDashboard merchant={selectedMerchant} apiUrl={API_URL} />

            {/* Payout Form */}
            <PayoutForm
              merchant={selectedMerchant}
              apiUrl={API_URL}
              onPayoutCreated={handlePayoutCreated}
            />

            {/* Payout History */}
            <PayoutHistory merchant={selectedMerchant} apiUrl={API_URL} />
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
