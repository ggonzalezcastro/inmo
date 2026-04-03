import { useEffect, useState } from 'react';
import { useLeadsStore } from '../store/leadsStore';
import { useAuthStore } from '../store/authStore';
import NavBar from './NavBar';
import RoleDebugger from './RoleDebugger';
import LeadTable from './LeadTable';
import LeadFilters from './LeadFilters';
import { agentsAPI } from '../services/api';


export default function Dashboard() {
  const { leads, total, loading, fetchLeads, filters, setFilters } = useLeadsStore();
  const { isAdmin, getUserRole } = useAuthStore();
  const userRole = getUserRole();
  const [workload, setWorkload] = useState([]);
  
  // Redirect if not admin
  useEffect(() => {
    if (userRole && !isAdmin()) {
      window.location.href = '/pipeline';
    }
  }, [userRole, isAdmin]);

  // Load agent workload for admin
  useEffect(() => {
    if (isAdmin()) {
      agentsAPI.getWorkload()
        .then((res) => setWorkload(res.data || []))
        .catch(() => {});
    }
  }, []);
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

        {/* Agent Workload Table (admin only) */}
        {isAdmin() && workload.length > 0 && (
          <div className="mt-8 bg-white shadow rounded-lg overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">📅 Carga de asesores (últimos 30 días)</h2>
            </div>
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Asesor</th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Reuniones (30d)</th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Leads asignados</th>
                  <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Calendario</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {workload.map((row) => (
                  <tr key={row.id} className="hover:bg-gray-50">
                    <td className="px-6 py-3">
                      <div className="font-medium text-gray-900">{row.name}</div>
                      <div className="text-xs text-gray-500">{row.email}</div>
                    </td>
                    <td className="px-6 py-3 text-center font-semibold text-gray-800">{row.appointments_30d}</td>
                    <td className="px-6 py-3 text-center text-gray-700">{row.leads_assigned}</td>
                    <td className="px-6 py-3 text-center">
                      {row.calendar_connected ? (
                        <span className="inline-flex items-center gap-1 text-green-600 font-medium">
                          <span>✓</span> Activo
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}

