import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

/**
 * LeadCard - Reusable card component for displaying lead information in Kanban board
 * 
 * Displays:
 * - Name and phone
 * - Status badge (No atendido / Atendido / Atendido por IA)
 * - Score as progress bar (0-100)
 * - Last message snippet
 * - Click to open ticket detail view
 * - Drag-and-drop enabled
 */
export default function LeadCard({ lead, onClick }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: `lead-${lead.id}`,
    data: {
      type: 'lead',
      lead,
    },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  // Determine status badge
  const getStatusBadge = () => {
    if (lead.treatment_type === 'automated_telegram' || lead.treatment_type === 'automated_call') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
          Atendido por IA
        </span>
      );
    }
    if (lead.last_contacted) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
          Atendido
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
        No atendido
      </span>
    );
  };

  // Get last message snippet
  const getLastMessage = () => {
    // Check if telegram_messages is an array or if we need to fetch it
    if (lead.telegram_messages && Array.isArray(lead.telegram_messages) && lead.telegram_messages.length > 0) {
      const lastMsg = lead.telegram_messages[lead.telegram_messages.length - 1];
      const text = lastMsg.message_text || '';
      return text.length > 50 ? text.substring(0, 50) + '...' : text;
    }
    // Check metadata for last message
    if (lead.metadata && lead.metadata.last_message) {
      const text = lead.metadata.last_message;
      return text.length > 50 ? text.substring(0, 50) + '...' : text;
    }
    return 'Sin mensajes';
  };

  // Calculate score percentage
  const scorePercentage = Math.round(lead.lead_score || 0);
  const scoreColor = 
    scorePercentage >= 70 ? 'bg-green-500' :
    scorePercentage >= 40 ? 'bg-yellow-500' :
    'bg-red-500';

  const handleClick = (e) => {
    // Prevent click when dragging
    if (isDragging) {
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    
    // Only trigger onClick if not dragging
    if (onClick) {
      e.stopPropagation();
      onClick(lead);
    }
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`
        bg-white rounded-lg shadow-sm border border-gray-200 p-3 mb-2 
        hover:shadow-md transition-shadow relative
        ${isDragging ? 'opacity-50 cursor-grabbing' : 'cursor-pointer'}
      `}
    >
      {/* Drag handle - only for dragging */}
      <div
        {...listeners}
        {...attributes}
        className="absolute top-2 right-2 w-6 h-6 flex items-center justify-center cursor-grab active:cursor-grabbing opacity-50 hover:opacity-100"
        onClick={(e) => e.stopPropagation()}
      >
        <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
        </svg>
      </div>
      
      {/* Clickable area for opening chat */}
      <div onClick={handleClick} className="cursor-pointer">
      {/* Header: Name and Status */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold text-gray-900 truncate">
            {lead.name || 'Sin nombre'}
          </h4>
          <p className="text-xs text-gray-500 mt-0.5">
            {lead.phone}
          </p>
        </div>
        {getStatusBadge()}
      </div>

      {/* Score Progress Bar */}
      <div className="mb-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-600">Score</span>
          <span className="text-xs font-medium text-gray-900">{scorePercentage}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className={`${scoreColor} h-2 rounded-full transition-all duration-300`}
            style={{ width: `${scorePercentage}%` }}
          />
        </div>
      </div>

      {/* Last Message Snippet */}
      <div className="mt-2 pt-2 border-t border-gray-100">
        <p className="text-xs text-gray-600 line-clamp-2">
          {getLastMessage()}
        </p>
      </div>

      {/* Tags (if any) */}
      {lead.tags && lead.tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {lead.tags.slice(0, 2).map((tag, idx) => (
            <span
              key={idx}
              className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
      </div>
    </div>
  );
}

