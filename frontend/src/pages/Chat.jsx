import { useEffect } from 'react';
import { useLeadsStore } from '../store/leadsStore';
import NavBar from '../components/NavBar';
import ChatTest from '../components/ChatTest';

/**
 * Chat Page - Chat interface for lead generation
 */
export default function Chat() {
  const { fetchLeads } = useLeadsStore();

  useEffect(() => {
    // Refresh leads when component mounts
    fetchLeads();
    
    // Listen for new lead creation from chat
    const handleLeadCreated = () => {
      fetchLeads();
    };
    window.addEventListener('leadCreated', handleLeadCreated);
    
    return () => {
      window.removeEventListener('leadCreated', handleLeadCreated);
    };
  }, [fetchLeads]);

  return (
    <div className="min-h-screen bg-gray-100">
      <NavBar />
      
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Chat de Prueba - Generador de Leads</h2>
          <div className="h-[calc(100vh-250px)] min-h-[600px]">
            <ChatTest />
          </div>
        </div>
      </main>
    </div>
  );
}


