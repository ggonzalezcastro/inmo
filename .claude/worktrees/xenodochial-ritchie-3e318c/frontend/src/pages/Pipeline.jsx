import { useState } from 'react';
import NavBar from '../components/NavBar';
import RoleDebugger from '../components/RoleDebugger';
import PipelineBoard from '../components/PipelineBoard';
import TicketDetail from '../components/TicketDetail';

/**
 * Pipeline Page - Main page for Kanban board view
 * Shows PipelineBoard and optionally TicketDetail in a modal/sidebar
 */
export default function Pipeline() {
  const [selectedLead, setSelectedLead] = useState(null);
  const [showTicketDetail, setShowTicketDetail] = useState(false);

  const handleLeadClick = (lead) => {
    setSelectedLead(lead);
    setShowTicketDetail(true);
  };

  const handleCloseTicket = () => {
    setShowTicketDetail(false);
    setSelectedLead(null);
  };

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      <NavBar />
      <RoleDebugger />

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Pipeline Board */}
        <div className={`flex-1 transition-all duration-300 ${showTicketDetail ? 'w-1/2' : 'w-full'}`}>
          <PipelineBoard onLeadClick={handleLeadClick} />
        </div>

        {/* Ticket Detail Sidebar - Chat completo */}
        {showTicketDetail && selectedLead && (
          <div className="w-1/2 border-l border-gray-200 bg-white flex-shrink-0 flex flex-col">
            <TicketDetail
              leadId={selectedLead.id}
              onClose={handleCloseTicket}
            />
          </div>
        )}
      </div>
    </div>
  );
}

