import { useEffect } from 'react';
import { useLeadsStore } from '../store/leadsStore';
import { useAuthStore } from '../store/authStore';
import NavBar from '../components/NavBar';
import LeadTable from '../components/LeadTable';
import LeadFilters from '../components/LeadFilters';

/**
 * Leads Page - Shows all leads (admin) or assigned leads (agent)
 */
export default function Leads() {
  const { leads, total, loading, fetchLeads, filters, setFilters } = useLeadsStore();
  const { isAdmin, getUserRole } = useAuthStore();
  const userRole = getUserRole();
  const isAdminUser = isAdmin();
  
  useEffect(() => {
    // Filter by assigned_to if agent
    if (!isAdminUser && userRole === 'agent') {
      // Agent only sees their assigned leads
      // The backend should filter by assigned_to automatically based on user context
      fetchLeads({ ...filters, assignedTo: 'me' });
    } else {
      fetchLeads(filters);
    }
  }, []);
  
  const handleAssignLead = async (leadId, agentId) => {
    try {
      const { ticketAPI } = await import('../services/api');
      await ticketAPI.updateField(leadId, 'assigned_to', agentId);
      fetchLeads(); // Refresh
    } catch (error) {
      console.error('Error assigning lead:', error);
      alert('Error al asignar lead');
      throw error;
    }
  };
  
  return (
    <div className="min-h-screen bg-gray-100">
      <NavBar />
      
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 sm:px-0">
          <h1 className="text-3xl font-bold text-gray-900 mb-6">
            {isAdminUser ? '📋 Leads' : '📋 Mis Leads'}
          </h1>
          
          {isAdminUser && (
            <p className="text-sm text-gray-600 mb-4">
              Gestiona todos los leads del broker. Puedes asignar leads a agentes desde la tabla.
            </p>
          )}
          
          {!isAdminUser && (
            <p className="text-sm text-gray-600 mb-4">
              Aquí puedes ver los leads que te han sido asignados.
            </p>
          )}
          
          {/* Filters */}
          <LeadFilters filters={filters} onFilterChange={setFilters} onApply={fetchLeads} />
          
          {/* Table */}
          <LeadTable 
            leads={leads} 
            loading={loading} 
            total={total}
            onAssignLead={isAdminUser ? handleAssignLead : undefined}
          />
        </div>
      </main>
    </div>
  );
}

