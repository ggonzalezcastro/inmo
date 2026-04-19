import { useState, useEffect } from 'react'
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor,
  useSensor, useSensors, type DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates,
  useSortable, verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, Calendar, CalendarOff, Users } from 'lucide-react'
import { Switch } from '@/shared/components/ui/switch'
import { toast } from 'sonner'
import { settingsService } from '../services/settings.service'

const blue = '#1A56DB'
const blueLt = '#EBF5FF'
const border = '#E5E7EB'

interface Agent {
  id: number
  name: string
  email: string
  assignment_priority: number | null
  calendar_connected: boolean
}

function SortableAgent({ agent, index }: { agent: Agent; index: number }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: agent.id })

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        boxShadow: isDragging ? '0 8px 24px rgba(26,86,219,0.18)' : undefined,
        borderColor: isDragging ? blue : border,
        zIndex: isDragging ? 50 : undefined,
      }}
      className="group flex items-center gap-3 rounded-xl border bg-white px-4 py-3 select-none"
    >
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing touch-none shrink-0 opacity-40 group-hover:opacity-80 transition-opacity"
        style={{ color: blue }}
      >
        <GripVertical className="h-4 w-4" />
      </button>
      <span
        className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold"
        style={{ background: blueLt, color: blue }}
      >
        {index + 1}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-[#111827] leading-tight">{agent.name}</p>
        <p className="text-xs text-[#9CA3AF] leading-tight">{agent.email}</p>
      </div>
      {agent.calendar_connected ? (
        <Calendar className="h-4 w-4 text-green-500 shrink-0" title="Calendario conectado" />
      ) : (
        <CalendarOff className="h-4 w-4 text-gray-300 shrink-0" title="Sin calendario" />
      )}
    </div>
  )
}

interface AssignmentTabProps {
  priorityEnabled: boolean
  onToggle: (enabled: boolean) => Promise<void>
}

export function AssignmentTab({ priorityEnabled, onToggle }: AssignmentTabProps) {
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [toggling, setToggling] = useState(false)

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  useEffect(() => {
    settingsService.getAgents()
      .then((data) => {
        // Sort by priority (nulls last), then by name
        const sorted = [...data].sort((a, b) => {
          if (a.assignment_priority === null && b.assignment_priority === null) return a.name.localeCompare(b.name)
          if (a.assignment_priority === null) return 1
          if (b.assignment_priority === null) return -1
          return a.assignment_priority - b.assignment_priority
        })
        setAgents(sorted)
      })
      .catch(() => toast.error('Error al cargar agentes'))
      .finally(() => setLoading(false))
  }, [])

  async function handleToggle(enabled: boolean) {
    setToggling(true)
    try {
      await onToggle(enabled)
      toast.success(enabled ? 'Modo prioridad activado' : 'Round-robin activado')
    } catch {
      toast.error('Error al guardar configuración')
    } finally {
      setToggling(false)
    }
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const oldIndex = agents.findIndex((a) => a.id === active.id)
    const newIndex = agents.findIndex((a) => a.id === over.id)
    const reordered = arrayMove(agents, oldIndex, newIndex)
    setAgents(reordered)

    try {
      await settingsService.updateAgentPriority(reordered.map((a) => a.id))
      toast.success('Prioridad guardada')
    } catch {
      toast.error('Error al guardar prioridad')
      // Revert on failure
      setAgents(agents)
    }
  }

  return (
    <div className="space-y-6">
      {/* Toggle */}
      <div className="flex items-start justify-between gap-4 rounded-xl border bg-white px-5 py-4">
        <div>
          <p className="text-sm font-semibold text-[#111827]">Modo prioridad</p>
          <p className="text-xs text-[#9CA3AF] mt-0.5">
            Asigna leads por orden de prioridad en vez de round-robin por carga
          </p>
        </div>
        <Switch
          checked={priorityEnabled}
          onCheckedChange={handleToggle}
          disabled={toggling}
        />
      </div>

      {/* Info / Agent list */}
      {!priorityEnabled ? (
        <div className="rounded-xl border border-dashed bg-[#F9FAFB] px-5 py-6 text-center">
          <Users className="mx-auto h-8 w-8 text-[#D1D9E6] mb-2" />
          <p className="text-sm text-[#6B7280]">
            Los leads se asignan automáticamente al agente con menos carga
          </p>
          <p className="text-xs text-[#9CA3AF] mt-1">
            Activa el modo prioridad para definir un orden manual
          </p>
        </div>
      ) : loading ? (
        <div className="rounded-xl border bg-white px-5 py-8 text-center">
          <p className="text-sm text-[#9CA3AF]">Cargando agentes…</p>
        </div>
      ) : agents.length === 0 ? (
        <div className="rounded-xl border border-dashed bg-[#F9FAFB] px-5 py-6 text-center">
          <p className="text-sm text-[#6B7280]">No hay agentes activos para ordenar</p>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-[#6B7280] font-medium uppercase tracking-wide px-1">
            Orden de asignación — arrastra para reordenar
          </p>
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={agents.map((a) => a.id)}
              strategy={verticalListSortingStrategy}
            >
              <div className="space-y-2">
                {agents.map((agent, idx) => (
                  <SortableAgent key={agent.id} agent={agent} index={idx} />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        </div>
      )}
    </div>
  )
}
