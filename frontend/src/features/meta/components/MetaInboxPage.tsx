import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  Bot,
  Check,
  ChevronDown,
  Clock3,
  Facebook,
  Inbox,
  Instagram,
  ListTodo,
  Loader2,
  MessageCircle,
  Paperclip,
  RefreshCw,
  Search,
  Send,
  Sparkles,
  UserRound,
  WandSparkles,
  WifiOff,
  X,
} from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import { EmptyState } from '@/shared/components/common/EmptyState'
import { LoadingSpinner } from '@/shared/components/common/LoadingSpinner'
import { PipelineStageBadge } from '@/shared/components/common/PipelineStageBadge'
import { useAuthStore } from '@/features/auth'
import { useWebSocketEvent, useWebSocketStatus } from '@/shared/context/WebSocketContext'
import { PIPELINE_STAGES } from '@/shared/lib/constants'
import { cn } from '@/shared/lib/utils'
import { getErrorMessage } from '@/shared/types/api'
import { metaService, type MetaConversationFilters } from '../services/meta.service'
import type {
  BrokerUser,
  MetaAsset,
  MetaAssignmentConflict,
  MetaConversation,
  MetaConversationDetail,
  MetaMessage,
  MetaTaskSuggestion,
  MetaTemplate,
} from '../types'

const fieldClass = 'h-9 min-w-0 rounded-lg border border-[#DCE5F2] bg-white px-2.5 text-xs font-medium text-slate-700 outline-none transition focus:border-[#1A56DB] focus:ring-2 focus:ring-blue-100'

const channelConfig = {
  whatsapp: { label: 'WhatsApp', icon: MessageCircle, color: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  instagram: { label: 'Instagram', icon: Instagram, color: 'bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200' },
  facebook: { label: 'Messenger', icon: Facebook, color: 'bg-blue-50 text-blue-700 border-blue-200' },
}

function formatRelative(value: string | null) {
  if (!value) return ''
  const date = new Date(value)
  const diff = Date.now() - date.getTime()
  if (diff < 60_000) return 'Ahora'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} min`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} h`
  if (diff < 604_800_000) return `${Math.floor(diff / 86_400_000)} d`
  return date.toLocaleDateString('es-CL', { day: '2-digit', month: 'short' })
}

function isWindowExpired(conversation: MetaConversation | null) {
  return conversation?.channel === 'whatsapp'
    && !!conversation.messaging_window_expires_at
    && new Date(conversation.messaging_window_expires_at).getTime() <= Date.now()
}

function isSocialWindowExpired(conversation: MetaConversation | null) {
  return !!conversation
    && ['instagram', 'facebook'].includes(conversation.channel)
    && (!conversation.messaging_window_expires_at || new Date(conversation.messaging_window_expires_at).getTime() <= Date.now())
}

function ConversationRow({ item, selected, onClick }: { item: MetaConversation; selected: boolean; onClick: () => void }) {
  const config = channelConfig[item.channel]
  const Icon = config.icon
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'group w-full border-b border-slate-100 px-4 py-3.5 text-left transition',
        selected ? 'bg-[#EEF4FF]' : 'bg-white hover:bg-slate-50',
      )}
    >
      <div className="flex gap-3">
        <div className={cn('mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border', config.color)}><Icon className="h-4 w-4" /></div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <p className={cn('truncate text-[13px] text-slate-900', item.unread_count ? 'font-bold' : 'font-semibold')}>{item.lead.name || item.lead.phone}</p>
            <span className="shrink-0 text-[10px] font-medium text-slate-400">{formatRelative(item.last_message_at)}</span>
          </div>
          <p className={cn('mt-0.5 truncate text-xs', item.unread_count ? 'font-medium text-slate-700' : 'text-slate-500')}>
            {item.last_message_direction === 'out' && <span className="mr-1 text-slate-400">Tú:</span>}
            {item.last_message || 'Sin mensajes todavía'}
          </p>
          <div className="mt-2 flex items-center gap-1.5">
            <span className="max-w-[115px] truncate rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-500 ring-1 ring-slate-200">{item.asset?.name || config.label}</span>
            {item.assignment_conflict && <span className="rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-700">Conflicto</span>}
            {item.unread_count > 0 && <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-[#1A56DB] px-1 text-[10px] font-bold text-white">{item.unread_count}</span>}
          </div>
        </div>
      </div>
    </button>
  )
}

function MessageBubble({ message }: { message: MetaMessage }) {
  const outbound = message.direction === 'out'
  const attachmentUrls = (message.attachments || []).flatMap((attachment) => {
    const payload = attachment.payload as Record<string, unknown> | undefined
    const candidate = attachment.url || payload?.url
    return typeof candidate === 'string' && candidate.startsWith('https://') ? [candidate] : []
  })
  return (
    <div className={cn('flex', outbound ? 'justify-end' : 'justify-start')}>
      <div className={cn('max-w-[82%] rounded-2xl px-3.5 py-2.5 shadow-sm', outbound ? 'rounded-br-md bg-[#1A56DB] text-white' : 'rounded-bl-md border border-slate-200 bg-white text-slate-800')}>
        {message.message_type !== 'text' && <p className={cn('mb-1 text-[10px] font-bold uppercase tracking-wide', outbound ? 'text-blue-100' : 'text-slate-400')}>{message.message_type}</p>}
        <p className="whitespace-pre-wrap break-words text-[13px] leading-5">{message.message_text || 'Contenido multimedia'}</p>
        {attachmentUrls.map((url) => <a key={url} href={url} target="_blank" rel="noreferrer" className={cn('mt-2 flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-[11px] font-bold underline-offset-2 hover:underline', outbound ? 'bg-blue-700 text-white' : 'bg-slate-100 text-[#1A56DB]')}><Paperclip className="h-3.5 w-3.5" /> Abrir adjunto</a>)}
        <div className={cn('mt-1.5 flex items-center justify-end gap-1.5 text-[9px]', outbound ? 'text-blue-100' : 'text-slate-400')}>
          {message.generation_mode === 'ai_draft' && <span className="flex items-center gap-0.5"><Sparkles className="h-2.5 w-2.5" /> IA revisada</span>}
          <span>{new Date(message.created_at).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })}</span>
          {outbound && <span>{message.status === 'failed' ? 'Error' : message.status === 'read' ? 'Leído' : message.status === 'delivered' ? 'Entregado' : 'Enviado'}</span>}
        </div>
        {message.status === 'failed' && <p className="mt-1 text-[10px] font-semibold text-rose-100">Meta rechazó este envío</p>}
      </div>
    </div>
  )
}

export function MetaInboxPage() {
  const user = useAuthStore((state) => state.user)
  const isAdmin = user?.role === 'admin'
  const [searchParams, setSearchParams] = useSearchParams()
  const initialConversation = Number(searchParams.get('conversation')) || null
  const [items, setItems] = useState<MetaConversation[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(initialConversation)
  const [detail, setDetail] = useState<MetaConversationDetail | null>(null)
  const [assets, setAssets] = useState<MetaAsset[]>([])
  const [users, setUsers] = useState<BrokerUser[]>([])
  const [projects, setProjects] = useState<Array<{ id: number; name: string; status: string }>>([])
  const [conflicts, setConflicts] = useState<MetaAssignmentConflict[]>([])
  const [filters, setFilters] = useState<MetaConversationFilters>({ limit: 30, conflict_only: searchParams.get('conflicts') === '1' || undefined })
  const [search, setSearch] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isDetailLoading, setIsDetailLoading] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [text, setText] = useState('')
  const [generationMode, setGenerationMode] = useState<'manual' | 'ai_draft'>('manual')
  const [isSending, setIsSending] = useState(false)
  const [summary, setSummary] = useState<string | null>(null)
  const [isSummarizing, setIsSummarizing] = useState(false)
  const [draftInstruction, setDraftInstruction] = useState('')
  const [isDrafting, setIsDrafting] = useState(false)
  const [taskSuggestion, setTaskSuggestion] = useState<MetaTaskSuggestion | null>(null)
  const [isTaskBusy, setIsTaskBusy] = useState(false)
  const [templates, setTemplates] = useState<MetaTemplate[]>([])
  const [templateId, setTemplateId] = useState('')
  const [templateVariables, setTemplateVariables] = useState<Record<string, string>>({})
  const [showMedia, setShowMedia] = useState(false)
  const [mediaUrl, setMediaUrl] = useState('')
  const [mediaType, setMediaType] = useState<'image' | 'video' | 'audio' | 'document'>('image')
  const { connected } = useWebSocketStatus()
  const messagesEndRef = useRef<HTMLDivElement | null>(null)

  const loadList = useCallback(async (append = false) => {
    append ? setIsLoadingMore(true) : setIsLoading(true)
    try {
      const response = await metaService.conversations({
        ...filters,
        search: search.trim() || undefined,
        cursor: append ? nextCursor || undefined : undefined,
      })
      setItems((current) => append ? [...current, ...response.items] : response.items)
      setNextCursor(response.next_cursor)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
      setIsLoadingMore(false)
    }
  }, [filters, nextCursor, search])

  useEffect(() => {
    Promise.all([
      metaService.assets(),
      isAdmin ? metaService.users() : Promise.resolve([]),
      isAdmin ? metaService.conflicts() : Promise.resolve([]),
      metaService.adsProjects().catch(() => []),
    ]).then(([assetResult, userResult, conflictResult, projectResult]) => {
      setAssets(assetResult)
      setUsers(userResult.filter((item) => item.is_active && item.role.toLowerCase() === 'agent'))
      setConflicts(conflictResult)
      setProjects(projectResult)
    }).catch((error) => toast.error(getErrorMessage(error)))
  }, [isAdmin])

  useEffect(() => {
    const timeout = window.setTimeout(() => loadList(false), 250)
    return () => window.clearTimeout(timeout)
  }, [filters, search]) // eslint-disable-line react-hooks/exhaustive-deps

  const loadDetail = useCallback(async (conversationId: number, quiet = false) => {
    if (!quiet) setIsDetailLoading(true)
    try {
      const response = await metaService.conversation(conversationId)
      setDetail(response)
      setItems((current) => current.map((item) => item.id === conversationId ? { ...response.conversation, unread_count: 0 } : item))
      await metaService.read(conversationId)
      window.setTimeout(() => messagesEndRef.current?.scrollIntoView({ block: 'end' }), 20)
    } catch (error) {
      toast.error(getErrorMessage(error))
      if (!quiet) setSelectedId(null)
    } finally {
      setIsDetailLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!selectedId) {
      setDetail(null)
      setSummary(null)
      setTaskSuggestion(null)
      setMediaUrl('')
      setShowMedia(false)
      return
    }
    loadDetail(selectedId)
  }, [loadDetail, selectedId])

  useEffect(() => {
    if (!detail?.conversation.asset?.id || !isWindowExpired(detail.conversation)) {
      setTemplates([])
      setTemplateId('')
      setTemplateVariables({})
      return
    }
    metaService.templates(detail.conversation.asset.id).then(setTemplates).catch(() => setTemplates([]))
  }, [detail?.conversation.asset?.id, detail?.conversation.messaging_window_expires_at])

  useWebSocketEvent(useCallback((event) => {
    if (!['meta_message_received', 'meta_message_sent', 'meta_message_status_changed', 'meta_assignment_conflict', 'meta_assignment_conflict_resolved'].includes(event.type)) return
    const data = event.data as { conversation_id?: number }
    loadList(false)
    if (selectedId && data.conversation_id === selectedId) loadDetail(selectedId, true)
    if (isAdmin && event.type.includes('conflict')) metaService.conflicts().then(setConflicts).catch(() => {})
  }, [isAdmin, loadDetail, loadList, selectedId]))

  const chooseConversation = (conversationId: number) => {
    setSelectedId(conversationId)
    const next = new URLSearchParams(searchParams)
    next.set('conversation', String(conversationId))
    setSearchParams(next, { replace: true })
  }

  const closeConversation = () => {
    setSelectedId(null)
    const next = new URLSearchParams(searchParams)
    next.delete('conversation')
    setSearchParams(next, { replace: true })
  }

  const olderMessages = async () => {
    if (!selectedId || !detail?.messages.next_before_id) return
    try {
      const page = await metaService.messages(selectedId, detail.messages.next_before_id)
      setDetail((current) => current ? { ...current, messages: { ...page, items: [...page.items, ...current.messages.items] } } : current)
    } catch (error) {
      toast.error(getErrorMessage(error))
    }
  }

  const sendMessage = async () => {
    if (!selectedId || !detail) return
    const template = templates.find((item) => item.id === Number(templateId))
    const templateParts = (template?.components || []).flatMap((component) => {
      const componentType = String(component.type || '').toLowerCase()
      const placeholders = Array.from(String(component.text || '').matchAll(/\{\{(\d+)\}\}/g))
      if (!placeholders.length || !['header', 'body'].includes(componentType)) return []
      const parameters = placeholders
        .sort((a, b) => Number(a[1]) - Number(b[1]))
        .map((match) => ({ type: 'text', text: templateVariables[`${componentType}-${match[1]}`]?.trim() || '' }))
      return [{ type: componentType, parameters }]
    })
    if (isWindowExpired(detail.conversation) && !template) {
      toast.error('Selecciona una plantilla aprobada para reabrir la conversación')
      return
    }
    if (!template && !text.trim() && !mediaUrl.trim()) return
    if (mediaUrl.trim() && !mediaUrl.trim().startsWith('https://')) {
      toast.error('El adjunto debe tener una URL pública que comience con https://')
      return
    }
    if (templateParts.some((part) => part.parameters.some((parameter) => !parameter.text))) {
      toast.error('Completa todas las variables de la plantilla')
      return
    }
    setIsSending(true)
    try {
      await metaService.send(selectedId, {
        text: text.trim(),
        generation_mode: generationMode,
        template_name: template?.name,
        template_language: template?.language,
        template_components: templateParts,
        media_url: mediaUrl.trim() || undefined,
        media_type: mediaUrl.trim() ? mediaType : undefined,
      })
      setText('')
      setTemplateId('')
      setTemplateVariables({})
      setGenerationMode('manual')
      setMediaUrl('')
      setShowMedia(false)
      await loadDetail(selectedId, true)
      await loadList(false)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsSending(false)
    }
  }

  const createDraft = async () => {
    if (!selectedId) return
    setIsDrafting(true)
    try {
      const response = await metaService.draft(selectedId, draftInstruction.trim() || undefined)
      setText(response.draft)
      setGenerationMode('ai_draft')
      toast.info('Borrador generado: revísalo antes de enviar')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsDrafting(false)
    }
  }

  const createSummary = async () => {
    if (!selectedId) return
    setIsSummarizing(true)
    try {
      setSummary((await metaService.summary(selectedId)).summary)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsSummarizing(false)
    }
  }

  const suggestTask = async () => {
    if (!selectedId) return
    setIsTaskBusy(true)
    try {
      const suggestion = await metaService.suggestTask(selectedId)
      setTaskSuggestion(suggestion)
      if (!suggestion.suggested) toast.info(suggestion.reason || 'No se detectó un compromiso concreto')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsTaskBusy(false)
    }
  }

  const approveTask = async () => {
    if (!selectedId || !taskSuggestion?.title || !taskSuggestion.due_at) {
      toast.error('Revisa el título y la fecha antes de crear la tarea')
      return
    }
    setIsTaskBusy(true)
    try {
      await metaService.approveTask(selectedId, {
        title: taskSuggestion.title,
        due_at: taskSuggestion.due_at,
        reminder_minutes_before: taskSuggestion.reminder_minutes_before,
        evidence_message_id: taskSuggestion.evidence_message_id,
        assigned_to: detail?.conversation.lead.assigned_to ?? undefined,
      })
      setTaskSuggestion(null)
      toast.success('Tarea creada con la evidencia de la conversación')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsTaskBusy(false)
    }
  }

  const resolveConflict = async (conflict: MetaAssignmentConflict, resolution: 'keep_current' | 'transfer_to_asset_owner') => {
    try {
      await metaService.resolveConflict(conflict.id, resolution)
      setConflicts((current) => current.filter((item) => item.id !== conflict.id))
      toast.success('Conflicto de asignación resuelto')
      loadList(false)
    } catch (error) {
      toast.error(getErrorMessage(error))
    }
  }

  const selected = detail?.conversation || items.find((item) => item.id === selectedId) || null
  const currentConflict = conflicts.find((conflict) => conflict.lead_id === selected?.lead.id && conflict.asset_id === selected?.asset?.id)
  const filteredAssets = useMemo(() => assets.filter((asset) => asset.channel && asset.approval_status === 'approved'), [assets])

  return (
    <div className="flex h-[calc(100vh-53px)] min-h-[620px] bg-[#F5F8FD] lg:h-screen">
      <aside className={cn('w-full shrink-0 border-r border-[#DDE6F2] bg-white lg:flex lg:w-[360px] lg:flex-col xl:w-[390px]', selectedId ? 'hidden lg:flex' : 'flex flex-col')}>
        <div className="border-b border-slate-100 px-4 py-4">
          <div className="flex items-center justify-between"><div><h1 className="text-lg font-bold tracking-tight text-slate-900">Bandeja Meta</h1><p className="mt-0.5 text-[11px] text-slate-500">WhatsApp, Instagram y Messenger</p></div><Button variant="ghost" size="sm" onClick={() => loadList(false)}><RefreshCw className="h-3.5 w-3.5" /></Button></div>
          <div className="relative mt-3"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar por nombre, teléfono o email" className="h-9 w-full rounded-xl border border-[#DCE5F2] bg-slate-50 pl-9 pr-3 text-xs outline-none focus:border-[#1A56DB] focus:bg-white focus:ring-2 focus:ring-blue-100" /></div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <select aria-label="Filtrar por canal" className={fieldClass} value={filters.channel || ''} onChange={(event) => setFilters((current) => ({ ...current, channel: event.target.value || undefined }))}>
              <option value="">Todos los canales</option><option value="whatsapp">WhatsApp</option><option value="instagram">Instagram</option><option value="facebook">Messenger</option>
            </select>
            <select aria-label="Filtrar por etapa" className={fieldClass} value={filters.pipeline_stage || ''} onChange={(event) => setFilters((current) => ({ ...current, pipeline_stage: event.target.value || undefined }))}>
              <option value="">Todas las etapas</option>{PIPELINE_STAGES.map((stage) => <option key={stage.key} value={stage.key}>{stage.label}</option>)}
            </select>
            {isAdmin && <select aria-label="Filtrar por ejecutivo" className={fieldClass} value={filters.assigned_user_id || ''} onChange={(event) => setFilters((current) => ({ ...current, assigned_user_id: event.target.value ? Number(event.target.value) : undefined }))}><option value="">Todo el equipo</option>{users.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</select>}
            <select aria-label="Filtrar por activo" className={fieldClass} value={filters.asset_id || ''} onChange={(event) => setFilters((current) => ({ ...current, asset_id: event.target.value ? Number(event.target.value) : undefined }))}><option value="">Todos los activos</option>{filteredAssets.map((asset) => <option key={asset.id} value={asset.id}>{asset.display_name || asset.external_id}</option>)}</select>
            <select aria-label="Filtrar por proyecto" className={fieldClass} value={filters.project_id || ''} onChange={(event) => setFilters((current) => ({ ...current, project_id: event.target.value ? Number(event.target.value) : undefined }))}><option value="">Todos los proyectos</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select>
            <input aria-label="Mensajes desde" title="Mensajes desde" type="date" className={fieldClass} value={filters.from_at ? new Date(filters.from_at).toLocaleDateString('en-CA') : ''} onChange={(event) => setFilters((current) => ({ ...current, from_at: event.target.value ? new Date(`${event.target.value}T00:00:00`).toISOString() : undefined }))} />
            <input aria-label="Mensajes hasta" title="Mensajes hasta" type="date" className={fieldClass} value={filters.to_at ? new Date(filters.to_at).toLocaleDateString('en-CA') : ''} onChange={(event) => setFilters((current) => ({ ...current, to_at: event.target.value ? new Date(`${event.target.value}T23:59:59.999`).toISOString() : undefined }))} />
          </div>
          {isAdmin && <label className="mt-2 flex items-center gap-2 text-[11px] font-semibold text-slate-600"><input type="checkbox" checked={filters.conflict_only || false} onChange={(event) => setFilters((current) => ({ ...current, conflict_only: event.target.checked || undefined }))} className="h-3.5 w-3.5 accent-rose-600" /> Solo conflictos de asignación</label>}
        </div>
        <div className="flex-1 overflow-y-auto">
          {isLoading ? <div className="flex justify-center py-24"><LoadingSpinner size="lg" /></div> : items.length === 0 ? <EmptyState icon={Inbox} title="No hay conversaciones" description="Los mensajes que coincidan con tus filtros aparecerán aquí." /> : <>{items.map((item) => <ConversationRow key={item.id} item={item} selected={selectedId === item.id} onClick={() => chooseConversation(item.id)} />)}{nextCursor && <div className="p-3"><Button variant="outline" size="sm" className="w-full" disabled={isLoadingMore} onClick={() => loadList(true)}>{isLoadingMore ? <Loader2 className="h-4 w-4 animate-spin" /> : <><ChevronDown className="mr-1.5 h-3.5 w-3.5" /> Cargar más</>}</Button></div>}</>}
        </div>
      </aside>

      <main className={cn('min-w-0 flex-1 flex-col bg-[radial-gradient(circle_at_top,#F8FAFF_0%,#EEF3F9_78%)]', selectedId ? 'flex' : 'hidden lg:flex')}>
        {!selectedId ? (
          <div className="flex flex-1 items-center justify-center"><EmptyState icon={MessageCircle} title="Elige una conversación" description="Aquí verás el historial completo y podrás responder por el activo correcto." /></div>
        ) : isDetailLoading || !detail ? (
          <div className="flex flex-1 items-center justify-center"><LoadingSpinner size="lg" /></div>
        ) : (
          <>
            <header className="flex h-[66px] shrink-0 items-center gap-3 border-b border-[#DDE6F2] bg-white px-3 sm:px-5">
              <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden" onClick={closeConversation}><ArrowLeft className="h-4 w-4" /></button>
              <div className={cn('flex h-9 w-9 items-center justify-center rounded-xl border', channelConfig[detail.conversation.channel].color)}>{(() => { const Icon = channelConfig[detail.conversation.channel].icon; return <Icon className="h-4 w-4" /> })()}</div>
              <div className="min-w-0 flex-1"><div className="flex items-center gap-2"><h2 className="truncate text-sm font-bold text-slate-900">{detail.conversation.lead.name || detail.conversation.lead.phone}</h2>{detail.conversation.assignment_conflict && <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600" />}</div><p className="truncate text-[11px] text-slate-500">{detail.conversation.asset?.name || channelConfig[detail.conversation.channel].label} · {detail.conversation.lead.assigned_agent_name || 'Sin asignar'}</p></div>
              <Link to={`/leads?lead=${detail.conversation.lead.id}`} className="rounded-lg border border-[#DCE5F2] bg-white px-3 py-2 text-[11px] font-bold text-[#1A56DB] hover:bg-blue-50">Ver lead</Link>
            </header>

            {detail.conversation.assignment_conflict && <div className="flex items-center gap-2 border-b border-rose-200 bg-rose-50 px-4 py-2 text-xs font-semibold text-rose-800"><AlertTriangle className="h-4 w-4" /> Jefatura debe resolver quién atenderá este contacto antes de enviar.</div>}
            {!connected && <div className="flex items-center gap-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs font-semibold text-amber-900"><WifiOff className="h-4 w-4" /> Sin conexión en tiempo real. Puedes consultar el historial; los nuevos mensajes aparecerán al reconectar.</div>}

            <div className="flex-1 overflow-y-auto px-3 py-5 sm:px-6">
              <div className="mx-auto max-w-3xl space-y-3">
                {detail.messages.has_more && <div className="flex justify-center"><Button variant="outline" size="sm" onClick={olderMessages}>Cargar mensajes anteriores</Button></div>}
                {detail.messages.items.length === 0 ? <EmptyState title="Sin mensajes" description="Esta conversación todavía no tiene contenido." /> : detail.messages.items.map((message) => <MessageBubble key={message.id} message={message} />)}
                <div ref={messagesEndRef} />
              </div>
            </div>

            <footer className="shrink-0 border-t border-[#DDE6F2] bg-white px-3 py-3 sm:px-5">
              <div className="mx-auto max-w-3xl">
                {isWindowExpired(detail.conversation) && (
                  <div className="mb-2 rounded-xl border border-amber-200 bg-amber-50 p-2.5"><p className="flex items-center gap-1.5 text-[11px] font-bold text-amber-900"><Clock3 className="h-3.5 w-3.5" /> Ventana de WhatsApp cerrada</p><select aria-label="Plantilla aprobada" value={templateId} onChange={(event) => { setTemplateId(event.target.value); setTemplateVariables({}) }} className={cn(fieldClass, 'mt-2 w-full')}><option value="">Selecciona una plantilla aprobada</option>{templates.map((template) => <option key={template.id} value={template.id}>{template.name} · {template.language}</option>)}</select>{templates.find((item) => item.id === Number(templateId))?.components.flatMap((component) => Array.from(String(component.text || '').matchAll(/\{\{(\d+)\}\}/g)).map((match) => ({ key: `${String(component.type || '').toLowerCase()}-${match[1]}`, label: `Variable ${match[1]} · ${String(component.type || '').toLowerCase()}` }))).map((variable) => <input key={variable.key} aria-label={variable.label} value={templateVariables[variable.key] || ''} onChange={(event) => setTemplateVariables((current) => ({ ...current, [variable.key]: event.target.value }))} placeholder={variable.label} className={cn(fieldClass, 'mt-2 w-full bg-white')} />)}</div>
                )}
                {isSocialWindowExpired(detail.conversation) && <div className="mb-2 rounded-xl border border-amber-200 bg-amber-50 p-2.5"><p className="flex items-center gap-1.5 text-[11px] font-bold text-amber-900"><Clock3 className="h-3.5 w-3.5" /> Ventana de respuesta cerrada</p><p className="mt-1 text-[10px] leading-4 text-amber-800">Instagram y Messenger no permiten iniciar una conversación fría. Podrás responder cuando el contacto vuelva a escribir.</p></div>}
                {generationMode === 'ai_draft' && <div className="mb-2 flex items-center justify-between rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-[11px] font-semibold text-violet-800"><span className="flex items-center gap-1.5"><Sparkles className="h-3.5 w-3.5" /> Borrador de IA: revísalo antes de enviar</span><button onClick={() => setGenerationMode('manual')}><X className="h-3.5 w-3.5" /></button></div>}
                {showMedia && <div className="mb-2 grid gap-2 rounded-xl border border-slate-200 bg-slate-50 p-2.5 sm:grid-cols-[130px_1fr_auto]"><select aria-label="Tipo de adjunto" className={fieldClass} value={mediaType} onChange={(event) => setMediaType(event.target.value as typeof mediaType)}><option value="image">Imagen</option><option value="video">Video</option>{detail.conversation.channel !== 'instagram' && <><option value="audio">Audio</option><option value="document">Documento</option></>}</select><input aria-label="URL pública del adjunto" value={mediaUrl} onChange={(event) => setMediaUrl(event.target.value)} placeholder="https://archivo-publico…" className={fieldClass} /><Button variant="ghost" size="icon" onClick={() => { setShowMedia(false); setMediaUrl('') }}><X className="h-4 w-4" /></Button><p className="text-[10px] text-slate-500 sm:col-span-3">Usa un enlace HTTPS público. Meta descargará el archivo para enviarlo por este canal.</p></div>}
                <div className="flex items-end gap-2 rounded-2xl border border-[#DCE5F2] bg-white p-2 shadow-[0_4px_18px_rgba(15,23,42,0.06)] focus-within:border-[#1A56DB] focus-within:ring-2 focus-within:ring-blue-100">
                  <Button type="button" variant="ghost" size="icon" className="h-9 w-9 shrink-0 rounded-xl text-slate-500" disabled={isWindowExpired(detail.conversation) || isSocialWindowExpired(detail.conversation) || detail.conversation.assignment_conflict || isSending} onClick={() => setShowMedia((current) => !current)} title="Adjuntar mediante URL pública"><Paperclip className="h-4 w-4" /></Button>
                  <textarea aria-label="Escribir mensaje" value={text} onChange={(event) => { setText(event.target.value); if (generationMode === 'ai_draft') setGenerationMode('manual') }} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendMessage() } }} disabled={detail.conversation.assignment_conflict || isSocialWindowExpired(detail.conversation) || isSending} placeholder={isWindowExpired(detail.conversation) ? 'Mensaje opcional junto a la plantilla' : isSocialWindowExpired(detail.conversation) ? 'Espera un nuevo mensaje del contacto' : 'Escribe un mensaje…'} rows={2} className="max-h-32 min-h-[44px] flex-1 resize-none border-0 bg-transparent px-2 py-1.5 text-[13px] leading-5 outline-none placeholder:text-slate-400" />
                  <Button size="icon" className="h-9 w-9 shrink-0 rounded-xl" disabled={isSending || detail.conversation.assignment_conflict || isSocialWindowExpired(detail.conversation) || (!text.trim() && !templateId && !mediaUrl.trim())} onClick={sendMessage}>{isSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}</Button>
                </div>
              </div>
            </footer>
          </>
        )}
      </main>

      <aside className={cn('hidden w-[310px] shrink-0 overflow-y-auto border-l border-[#DDE6F2] bg-white 2xl:block', selectedId ? '' : '2xl:hidden')}>
        {detail && (
          <div className="divide-y divide-slate-100">
            <section className="p-4"><p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">Contexto comercial</p><div className="mt-3 flex items-center gap-2"><UserRound className="h-4 w-4 text-slate-400" /><p className="text-sm font-bold text-slate-900">{detail.conversation.lead.name || 'Lead sin nombre'}</p></div><div className="mt-3 space-y-2 text-xs text-slate-600"><div className="flex justify-between gap-3"><span>Etapa</span>{detail.conversation.lead.pipeline_stage ? <PipelineStageBadge stage={detail.conversation.lead.pipeline_stage} /> : <span>Sin etapa</span>}</div><div className="flex justify-between gap-3"><span>Ejecutivo</span><span className="text-right font-semibold text-slate-800">{detail.conversation.lead.assigned_agent_name || 'Sin asignar'}</span></div><div className="flex justify-between gap-3"><span>Canal</span><span className="font-semibold text-slate-800">{channelConfig[detail.conversation.channel].label}</span></div><div className="flex justify-between gap-3"><span>Activo</span><span className="max-w-[150px] truncate text-right font-semibold text-slate-800">{detail.conversation.asset?.name || '—'}</span></div></div></section>

            {currentConflict && <section className="bg-rose-50 p-4"><p className="flex items-center gap-1.5 text-xs font-bold text-rose-800"><AlertTriangle className="h-4 w-4" /> Conflicto de responsable</p><p className="mt-1.5 text-[11px] leading-5 text-rose-700">El lead ya tenía ejecutivo y el activo pertenece a otra persona. El envío queda bloqueado.</p><div className="mt-3 grid gap-2"><Button size="sm" onClick={() => resolveConflict(currentConflict, 'keep_current')}>Mantener ejecutivo actual</Button>{currentConflict.asset_owner_id && <Button variant="outline" size="sm" onClick={() => resolveConflict(currentConflict, 'transfer_to_asset_owner')}>Transferir al dueño del canal</Button>}</div></section>}

            <section className="p-4"><div className="flex items-center justify-between"><p className="flex items-center gap-1.5 text-xs font-bold text-slate-800"><Sparkles className="h-4 w-4 text-violet-600" /> Resumen con IA</p><Button variant="ghost" size="sm" disabled={isSummarizing} onClick={createSummary}>{isSummarizing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Generar'}</Button></div>{summary ? <p className="mt-2 whitespace-pre-wrap rounded-xl bg-violet-50 p-3 text-[11px] leading-5 text-violet-950">{summary}</p> : <p className="mt-2 text-[11px] leading-5 text-slate-500">Resume interés, objeciones, compromisos y próxima acción sin inventar datos.</p>}</section>

            <section className="p-4"><p className="flex items-center gap-1.5 text-xs font-bold text-slate-800"><WandSparkles className="h-4 w-4 text-[#1A56DB]" /> Borrador de respuesta</p><input value={draftInstruction} onChange={(event) => setDraftInstruction(event.target.value)} placeholder="Opcional: tono o intención" className={cn(fieldClass, 'mt-3 w-full')} /><Button variant="outline" size="sm" className="mt-2 w-full" disabled={isDrafting || detail.conversation.assignment_conflict} onClick={createDraft}>{isDrafting ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Bot className="mr-1.5 h-3.5 w-3.5" />} Crear borrador editable</Button></section>

            <section className="p-4"><div className="flex items-center justify-between"><p className="flex items-center gap-1.5 text-xs font-bold text-slate-800"><ListTodo className="h-4 w-4 text-amber-600" /> Próxima tarea</p><Button variant="ghost" size="sm" disabled={isTaskBusy} onClick={suggestTask}>Detectar</Button></div>{taskSuggestion?.suggested && <div className="mt-3 space-y-2 rounded-xl border border-amber-200 bg-amber-50 p-3"><label className="block text-[10px] font-bold uppercase text-amber-800">Título<input value={taskSuggestion.title || ''} onChange={(event) => setTaskSuggestion((current) => current ? { ...current, title: event.target.value } : current)} className={cn(fieldClass, 'mt-1 w-full bg-white')} /></label><label className="block text-[10px] font-bold uppercase text-amber-800">Vencimiento<input type="datetime-local" value={taskSuggestion.due_at ? new Date(new Date(taskSuggestion.due_at).getTime() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16) : ''} onChange={(event) => setTaskSuggestion((current) => current ? { ...current, due_at: event.target.value ? new Date(event.target.value).toISOString() : null } : current)} className={cn(fieldClass, 'mt-1 w-full bg-white')} /></label>{taskSuggestion.evidence && <p className="text-[10px] leading-4 text-amber-800">Evidencia: “{taskSuggestion.evidence}”</p>}<Button size="sm" className="w-full" disabled={isTaskBusy || !taskSuggestion.title || !taskSuggestion.due_at} onClick={approveTask}><Check className="mr-1.5 h-3.5 w-3.5" /> Aprobar y crear</Button></div>}</section>
          </div>
        )}
      </aside>
    </div>
  )
}
