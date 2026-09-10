import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  ArrowUpRight, BadgeCheck, Banknote, CalendarCheck2,
  CheckCircle2, CircleDotDashed, Clock3, Filter, Handshake, ListTodo,
  MessageCircleMore, MessagesSquare, PhoneCall, Target, TriangleAlert,
  UserCheck, Users, WalletCards, XCircle,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { LoadingSpinner } from '@/shared/components/common/LoadingSpinner'
import { Button } from '@/shared/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/shared/components/ui/dialog'
import { cn, formatDateTime } from '@/shared/lib/utils'
import { getErrorMessage } from '@/shared/types/api'
import {
  dashboardService,
  type ManagementDashboardMetrics,
  type ManagementLeadSummary,
} from '../services/dashboard.service'

interface Props {
  brokerId: number | null
  requiresBroker?: boolean
  personal?: boolean
}

type DrilldownKey =
  | 'received' | 'assigned' | 'contacted' | 'advised' | 'without_follow_up'
  | 'reservations' | 'sales' | 'lost' | 'appointments_scheduled'
  | 'appointments_completed' | 'appointments_cancelled' | 'appointments_no_show'

function initialDates() {
  const today = new Date()
  const from = new Date(today)
  from.setDate(from.getDate() - 29)
  return { from: from.toISOString().slice(0, 10), to: today.toISOString().slice(0, 10) }
}

function formatUF(value: number) {
  return `${value.toLocaleString('es-CL', { maximumFractionDigits: 0 })} UF`
}

function formatCLP(value: number) {
  return value ? `$${value.toLocaleString('es-CL')}` : '$0'
}

function timeLabel(minutes: number | null) {
  if (minutes == null) return 'Sin datos'
  if (minutes < 60) return `${Math.round(minutes)} min`
  if (minutes < 1440) return `${(minutes / 60).toLocaleString('es-CL', { maximumFractionDigits: 1 })} h`
  return `${(minutes / 1440).toLocaleString('es-CL', { maximumFractionDigits: 1 })} días`
}

function hourLabel(hours: number | null) {
  if (hours == null) return 'Sin datos'
  return hours < 24 ? `${hours.toLocaleString('es-CL')} h` : `${(hours / 24).toLocaleString('es-CL', { maximumFractionDigits: 1 })} días`
}

export function ManagementDashboard({ brokerId, requiresBroker = false, personal = false }: Props) {
  const navigate = useNavigate()
  const dates = useMemo(initialDates, [])
  const [dateFrom, setDateFrom] = useState(dates.from)
  const [dateTo, setDateTo] = useState(dates.to)
  const [agentId, setAgentId] = useState('')
  const [projectId, setProjectId] = useState('')
  const [source, setSource] = useState('')
  const [data, setData] = useState<ManagementDashboardMetrics | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [drilldown, setDrilldown] = useState<{ key: DrilldownKey; title: string } | null>(null)

  useEffect(() => {
    if (requiresBroker && !brokerId) return
    let cancelled = false
    setIsLoading(true)
    dashboardService.getManagementMetrics({
      broker_id: brokerId,
      date_from: dateFrom,
      date_to: dateTo,
      agent_id: agentId ? Number(agentId) : undefined,
      project_id: projectId ? Number(projectId) : undefined,
      source: source || undefined,
    }).then((result) => {
      if (!cancelled) setData(result)
    }).catch((error) => {
      if (!cancelled) toast.error(getErrorMessage(error))
    }).finally(() => {
      if (!cancelled) setIsLoading(false)
    })
    return () => { cancelled = true }
  }, [agentId, brokerId, dateFrom, dateTo, projectId, requiresBroker, source])

  if (requiresBroker && !brokerId) {
    return <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center"><Filter className="mx-auto mb-3 h-7 w-7 text-blue-600" /><h2 className="font-semibold text-slate-900">Selecciona un broker</h2><p className="mt-1 text-sm text-slate-500">El dashboard de jefatura mantiene los datos separados por empresa.</p></div>
  }

  const commercial = data?.commercial
  const tasks = data?.tasks
  const kpis: Array<{ label: string; value: string | number; detail: string; icon: typeof Users; key?: DrilldownKey; tone?: string }> = [
    { label: 'Leads recibidos', value: commercial?.received ?? 0, detail: 'en el período', icon: Users, key: 'received' },
    { label: 'Asignados', value: commercial?.assigned ?? 0, detail: 'con ejecutivo', icon: UserCheck, key: 'assigned' },
    { label: 'Contactados', value: commercial?.contacted ?? 0, detail: 'contacto registrado', icon: PhoneCall, key: 'contacted' },
    { label: 'Asesorados', value: commercial?.advised ?? 0, detail: 'asesoría verificada', icon: MessagesSquare, key: 'advised' },
    { label: 'Sin seguimiento', value: commercial?.without_follow_up ?? 0, detail: 'requieren atención', icon: TriangleAlert, key: 'without_follow_up', tone: 'rose' },
    { label: 'Primera respuesta', value: timeLabel(commercial?.first_response_minutes ?? null), detail: 'contacto registrado', icon: Clock3, key: 'contacted' },
    { label: 'Reservas', value: commercial?.reservations ?? 0, detail: 'generadas', icon: Handshake, key: 'reservations' },
    { label: 'Ventas cerradas', value: commercial?.sales ?? 0, detail: `${commercial?.conversion_rate ?? 0}% conversión`, icon: BadgeCheck, key: 'sales', tone: 'navy' },
    { label: 'Ventas en UF', value: formatUF(commercial?.sales_uf ?? 0), detail: 'precio de unidades', icon: WalletCards, key: 'sales' },
    { label: 'Ventas en pesos', value: formatCLP(commercial?.sales_clp ?? 0), detail: 'sin convertir UF', icon: Banknote, key: 'sales' },
    { label: 'Ciclo hasta venta', value: commercial?.lead_to_sale_days == null ? 'Sin datos' : `${commercial.lead_to_sale_days} días`, detail: 'promedio ingreso → firma', icon: Target, key: 'sales' },
    { label: 'Perdidos', value: commercial?.lost ?? 0, detail: 'leads y negocios', icon: XCircle, key: 'lost', tone: 'rose' },
  ]

  const currentDrilldown = drilldown ? data?.drilldowns[drilldown.key] : null
  const maxTrend = Math.max(1, ...(data?.trend.map((point) => Math.max(point.leads, point.advised, point.sales)) ?? [1]))

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-[#DCE5F2] bg-white p-3 shadow-sm">
        <div className={cn('grid gap-2 sm:grid-cols-2', personal ? 'lg:grid-cols-4' : 'lg:grid-cols-5')}>
          <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Desde<input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} className="mt-1 block h-9 w-full rounded-lg border border-slate-200 px-2.5 text-xs font-medium text-slate-700" /></label>
          <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Hasta<input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} className="mt-1 block h-9 w-full rounded-lg border border-slate-200 px-2.5 text-xs font-medium text-slate-700" /></label>
          {!personal && <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Ejecutivo<select value={agentId} onChange={(event) => setAgentId(event.target.value)} className="mt-1 block h-9 w-full rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-medium text-slate-700"><option value="">Todos</option>{data?.filters.agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</select></label>}
          <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Proyecto<select value={projectId} onChange={(event) => setProjectId(event.target.value)} className="mt-1 block h-9 w-full rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-medium text-slate-700"><option value="">Todos</option>{data?.filters.projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
          <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Origen<select value={source} onChange={(event) => setSource(event.target.value)} className="mt-1 block h-9 w-full rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-medium text-slate-700"><option value="">Todos</option>{data?.filters.sources.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        </div>
      </div>

      {isLoading && !data ? <div className="flex justify-center rounded-2xl border bg-white py-24"><LoadingSpinner size="lg" /></div> : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            {kpis.map(({ label, value, detail, icon: Icon, key, tone }) => (
              <button key={label} type="button" disabled={!key} onClick={() => key && setDrilldown({ key, title: label })} className={cn('group rounded-2xl border bg-white p-3.5 text-left shadow-[0_6px_24px_rgba(30,64,175,0.05)] transition-all', key && 'hover:-translate-y-0.5 hover:border-blue-300 hover:shadow-md', tone === 'navy' && 'border-slate-800 bg-slate-900 text-white', tone === 'rose' && 'border-rose-200')}>
                <div className="flex items-center justify-between"><span className={cn('text-[10px] font-bold uppercase tracking-[0.1em] text-slate-500', tone === 'navy' && 'text-slate-300')}>{label}</span><Icon className={cn('h-4 w-4 text-blue-600', tone === 'navy' && 'text-blue-300', tone === 'rose' && 'text-rose-600')} /></div>
                <p className="mt-3 truncate text-xl font-bold tracking-tight">{isLoading ? '—' : value}</p>
                <p className={cn('mt-1 text-[11px] text-slate-500', tone === 'navy' && 'text-slate-300')}>{detail}{key && <ArrowUpRight className="ml-1 inline h-3 w-3 opacity-0 transition-opacity group-hover:opacity-100" />}</p>
              </button>
            ))}
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
            <section className="rounded-2xl border border-[#DCE5F2] bg-white p-4 shadow-sm">
              <div className="mb-4 flex items-center justify-between"><div><h2 className="font-bold text-slate-900">{personal ? 'Mi rendimiento comercial' : 'Rendimiento por ejecutivo'}</h2><p className="text-xs text-slate-500">{personal ? 'Tus resultados, seguimiento y carga de trabajo en el período.' : 'Conversión, actividad y carga de trabajo en una sola lectura.'}</p></div><Target className="h-5 w-5 text-blue-600" /></div>
              <div className="overflow-x-auto"><table className="w-full min-w-[780px] text-left text-xs"><thead><tr className="border-b text-[10px] uppercase tracking-wide text-slate-500"><th className="pb-2">Ejecutivo</th><th className="pb-2 text-right">Leads</th><th className="pb-2 text-right">Contactados</th><th className="pb-2 text-right">Asesorados</th><th className="pb-2 text-right">Reservas</th><th className="pb-2 text-right">Ventas</th><th className="pb-2 text-right">Conversión</th><th className="pb-2 text-right">Carga</th><th className="pb-2 text-right">Atrasadas</th></tr></thead><tbody>{data?.by_agent.map((row) => <tr key={row.id} className="border-b border-slate-100 last:border-0"><td className="py-3 font-semibold text-slate-800">{row.name}</td><td className="py-3 text-right">{row.leads}</td><td className="py-3 text-right">{row.contacted}</td><td className="py-3 text-right">{row.advised}</td><td className="py-3 text-right">{row.reservations}</td><td className="py-3 text-right font-semibold">{row.sales}</td><td className="py-3 text-right font-semibold text-blue-700">{row.conversion_rate}%</td><td className="py-3 text-right">{row.active_tasks}</td><td className={cn('py-3 text-right', row.overdue_tasks > 0 && 'font-semibold text-rose-600')}>{row.overdue_tasks}</td></tr>)}</tbody></table></div>
            </section>

            <section className="rounded-2xl border border-slate-800 bg-slate-900 p-4 text-white shadow-sm">
              <div className="mb-4 flex items-center justify-between"><div><h2 className="font-bold">{personal ? 'Mi cumplimiento de tareas' : 'Cumplimiento de tareas'}</h2><p className="text-xs text-slate-400">Integrado al seguimiento comercial.</p></div><ListTodo className="h-5 w-5 text-blue-300" /></div>
              <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4 xl:grid-cols-2">{[
                ['Pendientes', tasks?.pending ?? 0, ListTodo, 'text-slate-200'], ['En curso', tasks?.in_progress ?? 0, CircleDotDashed, 'text-blue-300'], ['Vencidas', tasks?.overdue ?? 0, TriangleAlert, 'text-rose-300'], ['Completadas', tasks?.completed ?? 0, CheckCircle2, 'text-emerald-300'],
              ].map(([label, value, Icon, tone]) => { const IconComponent = Icon as typeof ListTodo; return <div key={label as string} className="rounded-xl border border-slate-700 bg-slate-800/70 p-3"><IconComponent className={cn('mb-2 h-4 w-4', tone as string)} /><p className="text-xl font-bold">{value as number}</p><p className="text-[11px] text-slate-400">{label as string}</p></div> })}</div>
              <div className="mt-3 grid grid-cols-2 gap-3 border-t border-slate-700 pt-3 text-xs"><div><p className="text-slate-400">Cumplimiento</p><p className="mt-0.5 text-lg font-bold">{tasks?.completion_rate ?? 0}%</p></div><div><p className="text-slate-400">A tiempo</p><p className="mt-0.5 text-lg font-bold">{tasks?.on_time_rate ?? 0}%</p></div><div><p className="text-slate-400">Resolución prom.</p><p className="mt-0.5 font-semibold">{hourLabel(tasks?.avg_resolution_hours ?? null)}</p></div><div><p className="text-slate-400">Atraso prom.</p><p className="mt-0.5 font-semibold text-rose-300">{hourLabel(tasks?.avg_delay_hours ?? null)}</p></div></div>
              <Button variant="outline" className="mt-4 w-full border-slate-600 bg-transparent text-white hover:bg-slate-800 hover:text-white" onClick={() => navigate('/tasks')}>Abrir Kanban de tareas</Button>
            </section>
          </div>

          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
            <SmallPanel title="Reuniones" icon={CalendarCheck2}>{[
              ['Agendadas', commercial?.appointments.scheduled ?? 0, 'text-blue-700', 'appointments_scheduled'], ['Realizadas', commercial?.appointments.completed ?? 0, 'text-emerald-700', 'appointments_completed'], ['Canceladas', commercial?.appointments.cancelled ?? 0, 'text-amber-700', 'appointments_cancelled'], ['No asistió', commercial?.appointments.no_show ?? 0, 'text-rose-700', 'appointments_no_show'],
            ].map(([label, value, tone, key]) => <StatRow key={label as string} label={label as string} value={value as number} tone={tone as string} onClick={() => setDrilldown({ key: key as DrilldownKey, title: label as string })} />)}</SmallPanel>
            <SmallPanel title="Resultados por proyecto" icon={Handshake}>{data?.by_project.length ? data.by_project.slice(0, 6).map((row) => <StatRow key={row.id} label={row.name} value={`${row.sales} ventas · ${row.reservations} reservas`} />) : <EmptyCopy />}</SmallPanel>
            <SmallPanel title="Resultados por origen" icon={MessageCircleMore}>{data?.by_source.length ? data.by_source.slice(0, 6).map((row) => <StatRow key={row.source} label={row.source} value={`${row.leads} leads · ${row.conversion_rate}%`} />) : <EmptyCopy />}</SmallPanel>
            <SmallPanel title="Motivos de pérdida" icon={XCircle}>{data?.lost_reasons.length ? data.lost_reasons.slice(0, 6).map((row) => <StatRow key={row.reason} label={row.reason} value={row.count} tone="text-rose-700" />) : <EmptyCopy />}</SmallPanel>
          </div>

          <section className="rounded-2xl border border-[#DCE5F2] bg-white p-4 shadow-sm">
            <div className="mb-4"><h2 className="font-bold text-slate-900">Evolución semanal</h2><p className="text-xs text-slate-500">Leads, asesorías y ventas dentro del período seleccionado.</p></div>
            <div className="flex min-h-48 items-end gap-3 overflow-x-auto pb-2">{data?.trend.map((point) => <div key={point.week} className="flex min-w-16 flex-1 flex-col items-center gap-2"><div className="flex h-36 items-end gap-1"><span title={`${point.leads} leads`} className="w-3 rounded-t bg-slate-300" style={{ height: `${Math.max(3, point.leads / maxTrend * 100)}%` }} /><span title={`${point.advised} asesorados`} className="w-3 rounded-t bg-blue-500" style={{ height: `${Math.max(3, point.advised / maxTrend * 100)}%` }} /><span title={`${point.sales} ventas`} className="w-3 rounded-t bg-emerald-500" style={{ height: `${Math.max(3, point.sales / maxTrend * 100)}%` }} /></div><span className="text-[10px] text-slate-500">{point.label}</span></div>)}</div>
            <div className="flex flex-wrap gap-4 border-t pt-3 text-[11px] text-slate-500"><Legend color="bg-slate-300" label="Leads" /><Legend color="bg-blue-500" label="Asesorados" /><Legend color="bg-emerald-500" label="Ventas" /></div>
          </section>

          <p className="text-[11px] leading-5 text-slate-500">Definiciones: {data?.definitions.contacted} {data?.definitions.first_response} {data?.definitions.without_follow_up} {data?.definitions.sales_clp}</p>
        </>
      )}

      <Dialog open={!!drilldown} onOpenChange={(open) => !open && setDrilldown(null)}><DialogContent className="max-h-[85vh] max-w-3xl overflow-hidden p-0"><DialogHeader className="border-b p-5"><DialogTitle>{drilldown?.title}</DialogTitle><DialogDescription>{currentDrilldown?.total ?? 0} leads componen este indicador. Se muestran hasta 100.</DialogDescription></DialogHeader><div className="max-h-[65vh] overflow-y-auto p-3">{currentDrilldown?.data.length ? currentDrilldown.data.map((lead) => <LeadRow key={lead.id} lead={lead} onOpen={() => navigate(`/leads?lead=${lead.id}`)} />) : <EmptyCopy />}</div></DialogContent></Dialog>
    </div>
  )
}

function SmallPanel({ title, icon: Icon, children }: { title: string; icon: typeof Users; children: ReactNode }) { return <section className="rounded-2xl border border-[#DCE5F2] bg-white p-4 shadow-sm"><div className="mb-3 flex items-center justify-between"><h2 className="text-sm font-bold text-slate-900">{title}</h2><Icon className="h-4 w-4 text-blue-600" /></div><div className="space-y-1">{children}</div></section> }
function StatRow({ label, value, tone = 'text-slate-800', onClick }: { label: string; value: string | number; tone?: string; onClick?: () => void }) { const content = <><span className="truncate text-slate-600">{label}</span><span className={cn('shrink-0 font-bold', tone)}>{value}</span></>; return onClick ? <button type="button" onClick={onClick} className="flex w-full items-center justify-between gap-3 rounded-lg px-2 py-2 text-left text-xs hover:bg-slate-50">{content}</button> : <div className="flex items-center justify-between gap-3 rounded-lg px-2 py-2 text-xs hover:bg-slate-50">{content}</div> }
function EmptyCopy() { return <p className="py-6 text-center text-xs text-slate-400">Sin datos para el período.</p> }
function Legend({ color, label }: { color: string; label: string }) { return <span className="flex items-center gap-1.5"><span className={cn('h-2.5 w-2.5 rounded-sm', color)} />{label}</span> }
function LeadRow({ lead, onOpen }: { lead: ManagementLeadSummary; onOpen: () => void }) { return <button type="button" onClick={onOpen} className="mb-1 flex w-full items-center justify-between gap-4 rounded-xl border border-transparent px-3 py-3 text-left hover:border-blue-100 hover:bg-blue-50/50"><div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-900">{lead.name}</p><p className="mt-0.5 text-xs text-slate-500">{lead.phone} · {lead.source} · {lead.assignee_name || 'Sin ejecutivo'}</p></div><div className="shrink-0 text-right"><span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-600">{lead.stage}</span><p className="mt-1 text-[10px] text-slate-400">{lead.created_at ? formatDateTime(lead.created_at) : ''}</p></div></button> }
