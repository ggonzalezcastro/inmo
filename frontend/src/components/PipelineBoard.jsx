import { useEffect, useState } from 'react';
import {
  DndContext,
  DragOverlay,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { usePipelineStore, PIPELINE_STAGES } from '../store/pipelineStore';
import { usePipelineRealtime } from '../hooks/useRealtime';
import LeadCard from './LeadCard';

/**
 * PipelineBoard - Kanban board view for managing leads across pipeline stages
 * 
 * Features:
 * - 8 columns (one per stage)
 * - Drag-and-drop leads between stages
 * - Filters: assigned user, campaign, date range, search
 * - Click lead card to open ticket detail
 */
export default function PipelineBoard({ onLeadClick }) {
  const {
    leadsByStage,
    loading,
    error,
    filters,
    fetchAllStages,
    moveLeadToStage,
    setFilters,
  } = usePipelineStore();

  const [activeId, setActiveId] = useState(null);
  const [searchInput, setSearchInput] = useState('');

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  useEffect(() => {
    fetchAllStages();
  }, []); // Fetch on mount

  useEffect(() => {
    // Refetch when filters change
    fetchAllStages();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.assignedTo, filters.campaign, filters.dateFrom, filters.dateTo, filters.search]);

  // Real-time updates for pipeline
  usePipelineRealtime((updates) => {
    if (updates) {
      // Refresh pipeline when updates are received
      fetchAllStages();
    }
  });

  const handleDragStart = (event) => {
    setActiveId(event.active.id);
  };

  const handleDragEnd = async (event) => {
    const { active, over } = event;
    setActiveId(null);

    if (!over) return;

    // Extract lead ID from active (e.g., "lead-7" -> 7)
    const activeIdStr = active.id.toString();
    if (!activeIdStr.startsWith('lead-')) {
      // Not a lead, ignore
      return;
    }
    const leadId = parseInt(activeIdStr.replace('lead-', ''));

    // Extract stage from over - must be a valid stage ID
    const overIdStr = over.id.toString();
    
    // Check if over.id is a valid stage (not another lead)
    const isValidStage = PIPELINE_STAGES.some(stage => stage.id === overIdStr);
    
    if (!isValidStage) {
      // If over.id is another lead (e.g., "lead-7"), it's just a click, not a drag
      // Don't try to move the lead
      return;
    }

    const newStage = overIdStr;

    // Don't move if already in the same stage
    const currentLeads = leadsByStage[newStage] || [];
    if (currentLeads.some(l => l.id === leadId)) {
      return;
    }

    await moveLeadToStage(leadId, newStage, 'Moved via Kanban board');
  };

  const handleSearch = (e) => {
    e.preventDefault();
    setFilters({ search: searchInput });
  };

  const handleFilterChange = (key, value) => {
    setFilters({ [key]: value });
  };

  const getActiveLead = () => {
    if (!activeId) return null;
    const leadId = parseInt(activeId.toString().replace('lead-', ''));
    for (const leads of Object.values(leadsByStage)) {
      const lead = leads.find(l => l.id === leadId);
      if (lead) return lead;
    }
    return null;
  };

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Filters Bar */}
      <div className="bg-white border-b border-gray-200 p-4">
        <div className="flex flex-wrap gap-4 items-end">
          {/* Search */}
          <form onSubmit={handleSearch} className="flex-1 min-w-[200px]">
            <label htmlFor="search" className="block text-xs font-medium text-gray-700 mb-1">
              Buscar
            </label>
            <div className="flex gap-2">
              <input
                id="search"
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Nombre o teléfono..."
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700"
              >
                Buscar
              </button>
            </div>
          </form>

          {/* Assigned To Filter */}
          <div className="min-w-[150px]">
            <label htmlFor="assignedTo" className="block text-xs font-medium text-gray-700 mb-1">
              Asignado a
            </label>
            <select
              id="assignedTo"
              value={filters.assignedTo || ''}
              onChange={(e) => handleFilterChange('assignedTo', e.target.value || null)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Todos</option>
              {/* TODO: Fetch users from API */}
            </select>
          </div>

          {/* Campaign Filter */}
          <div className="min-w-[150px]">
            <label htmlFor="campaign" className="block text-xs font-medium text-gray-700 mb-1">
              Campaña
            </label>
            <select
              id="campaign"
              value={filters.campaign || ''}
              onChange={(e) => handleFilterChange('campaign', e.target.value || null)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Todas</option>
              {/* TODO: Fetch campaigns from API */}
            </select>
          </div>

          {/* Date From */}
          <div className="min-w-[150px]">
            <label htmlFor="dateFrom" className="block text-xs font-medium text-gray-700 mb-1">
              Desde
            </label>
            <input
              id="dateFrom"
              type="date"
              value={filters.dateFrom || ''}
              onChange={(e) => handleFilterChange('dateFrom', e.target.value || null)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Date To */}
          <div className="min-w-[150px]">
            <label htmlFor="dateTo" className="block text-xs font-medium text-gray-700 mb-1">
              Hasta
            </label>
            <input
              id="dateTo"
              type="date"
              value={filters.dateTo || ''}
              onChange={(e) => handleFilterChange('dateTo', e.target.value || null)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Clear Filters */}
          <button
            onClick={() => {
              setSearchInput('');
              setFilters({
                assignedTo: null,
                campaign: null,
                dateFrom: null,
                dateTo: null,
                search: '',
              });
            }}
            className="px-4 py-2 text-sm text-gray-700 hover:text-gray-900"
          >
            Limpiar
          </button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border-l-4 border-red-400 p-4 m-4">
          <p className="text-sm text-red-700">Error: {error}</p>
          <button
            onClick={() => fetchAllStages()}
            className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
          >
            Reintentar
          </button>
        </div>
      )}
      
      {/* Debug info */}
      <div className="px-4 py-2 bg-blue-50 text-xs text-blue-700 border-b border-blue-200">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <span className="font-semibold">
            Total leads cargados: {Object.values(leadsByStage).reduce((sum, leads) => sum + (Array.isArray(leads) ? leads.length : 0), 0)}
          </span>
          <div className="flex gap-4 flex-wrap">
            {PIPELINE_STAGES.map(stage => {
              const count = Array.isArray(leadsByStage[stage.id]) ? leadsByStage[stage.id].length : 0;
              const leads = leadsByStage[stage.id] || [];
              return (
                <span 
                  key={stage.id} 
                  className={count > 0 ? 'text-green-700 font-semibold' : 'text-gray-500'}
                  title={count > 0 ? leads.map(l => `ID ${l.id}: ${l.name || 'Sin nombre'}`).join(', ') : ''}
                >
                  {stage.label}: {count}
                </span>
              );
            })}
          </div>
          <button
            onClick={() => {
              console.log('\n🔍 LOG COMPLETO DE TODOS LOS LEADS EN EL PIPELINE:');
              console.log('='.repeat(80));
              Object.entries(leadsByStage).forEach(([stageId, leads]) => {
                const stage = PIPELINE_STAGES.find(s => s.id === stageId);
                console.log(`\n📌 ETAPA: ${stage?.label || stageId} (${leads.length} leads)`);
                if (Array.isArray(leads) && leads.length > 0) {
                  leads.forEach((lead, idx) => {
                    console.log(`  ${idx + 1}. ID: ${lead.id}`);
                    console.log(`     Nombre: ${lead.name || 'Sin nombre'}`);
                    console.log(`     Teléfono: ${lead.phone}`);
                    console.log(`     Email: ${lead.email || 'N/A'}`);
                    console.log(`     Pipeline Stage: ${lead.pipeline_stage || 'NULL'}`);
                    console.log(`     Score: ${lead.lead_score || 0}`);
                    console.log(`     Status: ${lead.status || 'N/A'}`);
                    console.log(`     Tags: ${lead.tags ? lead.tags.join(', ') : 'Ninguno'}`);
                    console.log(`     ---`);
                  });
                } else {
                  console.log('  (Sin leads)');
                }
              });
              console.log('='.repeat(80));
            }}
            className="px-2 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700"
          >
            📋 Ver Log Completo en Consola
          </button>
        </div>
      </div>

      {/* Kanban Board */}
      <div className="flex-1 overflow-x-auto p-4">
        {loading && (
          <div className="flex items-center justify-center h-64">
            <p className="text-gray-500">Cargando leads...</p>
          </div>
        )}

        {!loading && (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCorners}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <div className="flex gap-4 min-w-max h-full">
              {PIPELINE_STAGES.map((stage) => {
                const stageLeads = leadsByStage[stage.id] || [];
                return (
                  <StageColumn
                    key={stage.id}
                    stage={stage}
                    leads={Array.isArray(stageLeads) ? stageLeads : []}
                    onLeadClick={onLeadClick}
                  />
                );
              })}
            </div>

            <DragOverlay>
              {activeId && getActiveLead() ? (
                <div className="opacity-90 rotate-2">
                  <LeadCard lead={getActiveLead()} onClick={() => {}} />
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>
        )}
      </div>
    </div>
  );
}

/**
 * StageColumn - Individual column in the Kanban board
 */
function StageColumn({ stage, leads, onLeadClick }) {
  const { setNodeRef, isOver } = useDroppable({
    id: stage.id,
  });

  const leadIds = leads.map(l => `lead-${l.id}`);

  return (
    <div
      ref={setNodeRef}
      className={`
        flex-shrink-0 w-72 bg-gray-100 rounded-lg p-3 flex flex-col
        ${isOver ? 'bg-gray-200 ring-2 ring-blue-500' : ''}
      `}
    >
      {/* Column Header */}
      <div className="mb-3 flex-shrink-0">
        <h3 className="text-sm font-semibold text-gray-900">
          {stage.label}
        </h3>
        <p className="text-xs text-gray-600 mt-1">
          {leads.length} {leads.length === 1 ? 'lead' : 'leads'}
        </p>
      </div>

      {/* Leads List */}
      <div className="flex-1 overflow-y-auto">
        <SortableContext
          items={leadIds}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-2">
            {leads.length === 0 ? (
              <div className="text-center py-8 text-gray-400 text-sm">
                Sin leads
              </div>
            ) : (
              leads.map((lead) => (
                <LeadCard
                  key={lead.id}
                  lead={lead}
                  onClick={() => onLeadClick?.(lead)}
                />
              ))
            )}
          </div>
        </SortableContext>
      </div>
    </div>
  );
}

