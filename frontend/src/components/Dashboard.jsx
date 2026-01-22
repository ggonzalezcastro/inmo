import { useEffect, useState } from 'react';
import { useLeadsStore } from '../store/leadsStore';
import { useAuthStore } from '../store/authStore';
import NavBar from './NavBar';
import RoleDebugger from './RoleDebugger';
import LeadTable from './LeadTable';
import LeadFilters from './LeadFilters';


export default function Dashboard() {
  const { leads, total, loading, fetchLeads, filters, setFilters } = useLeadsStore();
  const { isAdmin, getUserRole } = useAuthStore();
  const userRole = getUserRole();
  
  // Redirect if not admin
  useEffect(() => {
    if (userRole && !isAdmin()) {
      window.location.href = '/pipeline';
    }
  }, [userRole, isAdmin]);
  const [stats, setStats] = useState({
    total_leads: 0,
    cold: 0,
    warm: 0,
    hot: 0,
    avg_score: 0,
  });
  
  useEffect(() => {
    fetchLeads();
    
    // Listen for new lead creation from chat
    const handleLeadCreated = () => {
      fetchLeads();
    };
    window.addEventListener('leadCreated', handleLeadCreated);
    
    return () => {
      window.removeEventListener('leadCreated', handleLeadCreated);
    };
  }, []);
  
  useEffect(() => {
    // Calculate stats
    setStats({
      total_leads: total,
      cold: leads.filter((l) => l.status === 'cold').length,
      warm: leads.filter((l) => l.status === 'warm').length,
      hot: leads.filter((l) => l.status === 'hot').length,
      avg_score: leads.length > 0
        ? (leads.reduce((sum, l) => sum + l.lead_score, 0) / leads.length).toFixed(1)
        : 0,
    });
  }, [leads, total]);
  
  const handleApplyFilters = async () => {
    await fetchLeads();
  };
  
  return (
    <div className="min-h-screen bg-gray-100">
      <NavBar />
      <RoleDebugger />
      
      {/* Stats */}
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-5">
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <dt className="text-sm font-medium text-gray-500">Total Leads</dt>
              <dd className="mt-1 text-3xl font-semibold text-gray-900">
                {stats.total_leads}
              </dd>
            </div>
          </div>
          
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <dt className="text-sm font-medium text-gray-500">Cold</dt>
              <dd className="mt-1 text-3xl font-semibold text-blue-600">
                {stats.cold}
              </dd>
            </div>
          </div>
          
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <dt className="text-sm font-medium text-gray-500">Warm</dt>
              <dd className="mt-1 text-3xl font-semibold text-yellow-600">
                {stats.warm}
              </dd>
            </div>
          </div>
          
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <dt className="text-sm font-medium text-gray-500">Hot</dt>
              <dd className="mt-1 text-3xl font-semibold text-red-600">
                {stats.hot}
              </dd>
            </div>
          </div>
          
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <dt className="text-sm font-medium text-gray-500">Avg Score</dt>
              <dd className="mt-1 text-3xl font-semibold text-gray-900">
                {stats.avg_score}
              </dd>
            </div>
          </div>
        </div>
        
        {/* Filters */}
        <LeadFilters onApply={handleApplyFilters} />
        
        {/* Table */}
        <LeadTable 
          leads={leads} 
          loading={loading} 
          total={total}
          onAssignLead={async (leadId, agentId) => {
            try {
              const { ticketAPI } = await import('../services/api');
              await ticketAPI.updateField(leadId, 'assigned_to', agentId);
              fetchLeads(); // Refresh
            } catch (error) {
              console.error('Error assigning lead:', error);
              throw error;
            }
          }}
        />
      </main>
    </div>
  );
}

