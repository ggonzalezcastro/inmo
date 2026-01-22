import { useState } from 'react';
import { useCampaignStore } from '../store/campaignStore';
import { useAuthStore } from '../store/authStore';
import NavBar from '../components/NavBar';
import CampaignsList from '../components/CampaignsList';
import CampaignBuilder from '../components/CampaignBuilder';
import CampaignAnalytics from '../components/CampaignAnalytics';

/**
 * Campaigns Page - Manage campaigns
 */
export default function Campaigns() {
  const { selectedCampaign, setSelectedCampaign } = useCampaignStore();
  const { isAdmin } = useAuthStore();
  const canEdit = isAdmin(); // Solo admin puede editar
  
  const [view, setView] = useState('list'); // 'list', 'builder', 'analytics'
  const [editingCampaign, setEditingCampaign] = useState(null);

  const handleCampaignClick = (campaign) => {
    if (!canEdit) {
      alert('Solo los administradores pueden editar campañas');
      return;
    }
    setEditingCampaign(campaign);
    setView('builder');
  };

  const handleCreateNew = () => {
    if (!canEdit) {
      alert('Solo los administradores pueden crear campañas');
      return;
    }
    setEditingCampaign(null);
    setView('builder');
  };

  const handleSave = () => {
    setView('list');
    setEditingCampaign(null);
  };

  const handleCancel = () => {
    setView('list');
    setEditingCampaign(null);
  };

  const handleViewAnalytics = (campaign) => {
    setSelectedCampaign(campaign);
    setView('analytics');
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <NavBar />

      {/* Main Content */}
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {view === 'list' && (
          <CampaignsList
            onCampaignClick={handleCampaignClick}
            onCreateNew={handleCreateNew}
            canEdit={canEdit}
          />
        )}

        {view === 'builder' && (
          <div className="mb-4">
            <button
              onClick={() => setView('list')}
              className="mb-4 text-blue-600 hover:text-blue-800 text-sm font-medium"
            >
              ← Volver a lista
            </button>
            <CampaignBuilder
              campaign={editingCampaign}
              onSave={handleSave}
              onCancel={handleCancel}
            />
          </div>
        )}

        {view === 'analytics' && selectedCampaign && (
          <div>
            <button
              onClick={() => setView('list')}
              className="mb-4 text-blue-600 hover:text-blue-800 text-sm font-medium"
            >
              ← Volver a lista
            </button>
            <CampaignAnalytics campaignId={selectedCampaign.id} />
          </div>
        )}
      </main>
    </div>
  );
}

