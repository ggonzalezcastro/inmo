import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Database,
  Facebook,
  Instagram,
  Link2,
  MessageCircle,
  RefreshCw,
  ShieldCheck,
  Unplug,
  Users,
} from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import { EmptyState } from '@/shared/components/common/EmptyState'
import { LoadingSpinner } from '@/shared/components/common/LoadingSpinner'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { useAuthStore } from '@/features/auth'
import { getErrorMessage } from '@/shared/types/api'
import { cn } from '@/shared/lib/utils'
import { metaService } from '../services/meta.service'
import type { BrokerUser, MetaAsset, MetaChannel, MetaConnection, MetaHealth } from '../types'

const CHANNELS: Array<{
  id: MetaChannel
  title: string
  description: string
  icon: typeof MessageCircle
  tint: string
  adminOnly?: boolean
}> = [
  {
    id: 'whatsapp',
    title: 'WhatsApp Business',
    description: 'Números corporativos, plantillas y conversaciones de la corredora.',
    icon: MessageCircle,
    tint: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    adminOnly: true,
  },
  {
    id: 'instagram',
    title: 'Instagram',
    description: 'Mensajes de cuentas profesionales corporativas o asociadas a un ejecutivo.',
    icon: Instagram,
    tint: 'bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200',
  },
  {
    id: 'messenger',
    title: 'Messenger',
    description: 'Mensajes de páginas corporativas o conectadas por el ejecutivo.',
    icon: Facebook,
    tint: 'bg-blue-50 text-blue-700 border-blue-200',
  },
  {
    id: 'business',
    title: 'Meta Business',
    description: 'Páginas, cuentas publicitarias y formularios de Lead Ads.',
    icon: Link2,
    tint: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    adminOnly: true,
  },
]

const FEATURE_LABELS: Array<[keyof MetaHealth['channels'], string]> = [
  ['whatsapp', 'WhatsApp'],
  ['instagram', 'Instagram'],
  ['messenger', 'Messenger'],
  ['ads', 'Campañas'],
  ['lead_ads', 'Lead Ads'],
  ['conversions_api', 'Conversions API'],
]

const selectClass = 'h-9 rounded-lg border border-[#DCE5F2] bg-white px-2.5 text-xs font-medium text-slate-700 outline-none transition focus:border-[#1A56DB] focus:ring-2 focus:ring-blue-100 disabled:bg-slate-50 disabled:text-slate-400'

function ownerLabel(asset: MetaAsset, users: BrokerUser[]) {
  if (asset.owner_type === 'broker') return 'Corporativo'
  return users.find((user) => user.id === asset.owner_user_id)?.name || 'Ejecutivo'
}

function connectionChannels(connection: MetaConnection, assets: MetaAsset[]) {
  const values = new Set(
    assets
      .filter((asset) => asset.connection_id === connection.id)
      .map((asset) => asset.channel || asset.asset_type),
  )
  return Array.from(values).join(' · ') || connection.auth_mode.replace(/_/g, ' ')
}

export function MetaChannelsPage() {
  const user = useAuthStore((state) => state.user)
  const isAdmin = user?.role === 'admin'
  const [searchParams, setSearchParams] = useSearchParams()
  const [health, setHealth] = useState<MetaHealth | null>(null)
  const [connections, setConnections] = useState<MetaConnection[]>([])
  const [assets, setAssets] = useState<MetaAsset[]>([])
  const [users, setUsers] = useState<BrokerUser[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [busyKey, setBusyKey] = useState<string | null>(null)

  const load = useCallback(async () => {
    setIsLoading(true)
    try {
      const [healthResult, connectionResult, assetResult, userResult] = await Promise.all([
        metaService.health(),
        metaService.connections(),
        metaService.assets(),
        isAdmin ? metaService.users() : Promise.resolve([]),
      ])
      setHealth(healthResult)
      setConnections(connectionResult)
      setAssets(assetResult)
      setUsers(userResult.filter((item) => item.is_active && item.role.toLowerCase() === 'agent'))
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }, [isAdmin])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    const result = searchParams.get('meta')
    if (!result) return
    if (result === 'connected') toast.success('Cuenta Meta conectada y activos descubiertos')
    else toast.error('No se pudo completar la conexión con Meta')
    const next = new URLSearchParams(searchParams)
    next.delete('meta')
    next.delete('code')
    next.delete('connection_id')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  const activeAgents = useMemo(() => users.sort((a, b) => a.name.localeCompare(b.name)), [users])

  const connect = async (channel: MetaChannel) => {
    setBusyKey(`connect-${channel}`)
    try {
      const result = await metaService.authorize(channel)
      window.location.assign(result.authorization_url)
    } catch (error) {
      toast.error(getErrorMessage(error))
      setBusyKey(null)
    }
  }

  const updateAsset = async (asset: MetaAsset, changes: Partial<MetaAsset>, message: string) => {
    setBusyKey(`asset-${asset.id}`)
    try {
      const updated = await metaService.updateAsset(asset.id, changes)
      setAssets((current) => current.map((item) => item.id === updated.id ? updated : item))
      toast.success(message)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setBusyKey(null)
    }
  }

  const updateFeature = async (key: string, enabled: boolean) => {
    setBusyKey(`feature-${key}`)
    try {
      const next = await metaService.updateFeatures({ [key]: enabled })
      setHealth(next)
      toast.success('Permisos del broker actualizados')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setBusyKey(null)
    }
  }

  const disconnect = async (connection: MetaConnection) => {
    if (!window.confirm(`¿Desconectar ${connection.display_name || 'esta cuenta'}? Los activos quedarán pausados.`)) return
    setBusyKey(`connection-${connection.id}`)
    try {
      const updated = await metaService.disconnect(connection.id)
      setConnections((current) => current.map((item) => item.id === updated.id ? updated : item))
      setAssets((current) => current.map((asset) => asset.connection_id === connection.id ? { ...asset, status: 'paused', is_default: false } : asset))
      toast.success('Conexión desconectada')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setBusyKey(null)
    }
  }

  const sync = async (connection: MetaConnection) => {
    setBusyKey(`connection-${connection.id}`)
    try {
      const result = await metaService.sync(connection.id)
      toast.success(`${result.asset_count} activos sincronizados`)
      await load()
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setBusyKey(null)
    }
  }

  if (isLoading) {
    return <div className="flex min-h-[70vh] items-center justify-center"><LoadingSpinner size="lg" /></div>
  }

  const conversionDatasets = assets.filter((asset) => asset.asset_type === 'pixel')
  const channelAssets = assets.filter((asset) => asset.asset_type !== 'pixel')

  return (
    <div className="min-h-full bg-[linear-gradient(180deg,#F5F8FD_0%,#FFFFFF_380px)] p-4 sm:p-8">
      <div className="mx-auto max-w-[1440px]">
        <PageHeader
          title="Canales Meta"
          description={isAdmin ? 'Conecta, aprueba y distribuye las identidades de mensajería del equipo.' : 'Conecta tus cuentas profesionales para atender mensajes desde una sola bandeja.'}
          actions={<Button variant="outline" size="sm" onClick={load}><RefreshCw className="mr-1.5 h-3.5 w-3.5" /> Actualizar</Button>}
        />

        {!health?.configured && (
          <div className="mb-5 flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-900">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
            <div><p className="text-sm font-bold">Falta configurar la aplicación de Meta</p><p className="mt-0.5 text-xs leading-5">Jefatura debe completar las credenciales y URL de callback antes de conectar cuentas.</p></div>
          </div>
        )}
        {health?.configured && !health.global_enabled && (
          <div className="mb-5 flex gap-3 rounded-2xl border border-slate-200 bg-white p-4 text-slate-700">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-[#1A56DB]" />
            <div><p className="text-sm font-bold">Integración preparada, todavía en despliegue controlado</p><p className="mt-0.5 text-xs leading-5">El interruptor global debe habilitarse en el servidor para comenzar a operar.</p></div>
          </div>
        )}

        {isAdmin && health && (
          <section className="mb-5 overflow-hidden rounded-2xl border border-[#DDE6F2] bg-white shadow-[0_8px_28px_rgba(30,64,175,0.05)]">
            <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div><h2 className="text-sm font-bold text-slate-900">Disponibilidad para el broker</h2><p className="mt-0.5 text-xs text-slate-500">Activa solo los productos autorizados para esta corredora.</p></div>
              <label className="flex items-center gap-2 text-xs font-semibold text-slate-700">
                <input type="checkbox" checked={health.broker_enabled} disabled={busyKey !== null} onChange={(event) => updateFeature('enabled', event.target.checked)} className="h-4 w-4 accent-[#1A56DB]" />
                Ecosistema Meta activo
              </label>
            </div>
            <div className="grid gap-px bg-slate-100 sm:grid-cols-2 xl:grid-cols-6">
              {FEATURE_LABELS.map(([key, label]) => (
                <label key={key} className="flex items-center justify-between gap-3 bg-white px-4 py-3 text-xs font-medium text-slate-700">
                  {label}
                  <input
                    type="checkbox"
                    checked={health.overrides[key] ?? true}
                    disabled={busyKey !== null || !health.broker_enabled}
                    onChange={(event) => updateFeature(key, event.target.checked)}
                    className="h-4 w-4 accent-[#1A56DB]"
                  />
                </label>
              ))}
            </div>
          </section>
        )}

        <section className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {CHANNELS.filter((channel) => isAdmin || !channel.adminOnly).map((channel) => {
            const Icon = channel.icon
            const channelEnabled = channel.id === 'business'
              ? health?.channels.ads
              : health?.channels[channel.id]
            return (
              <article key={channel.id} className="flex min-h-[190px] flex-col rounded-2xl border border-[#DDE6F2] bg-white p-4 shadow-[0_7px_24px_rgba(30,64,175,0.05)]">
                <div className={cn('mb-4 flex h-10 w-10 items-center justify-center rounded-xl border', channel.tint)}><Icon className="h-5 w-5" /></div>
                <h2 className="text-sm font-bold text-slate-900">{channel.title}</h2>
                <p className="mt-1 flex-1 text-xs leading-5 text-slate-500">{channel.description}</p>
                <Button size="sm" className="mt-4 w-full" disabled={!channelEnabled || busyKey !== null} onClick={() => connect(channel.id)}>
                  <Link2 className="mr-1.5 h-3.5 w-3.5" /> Conectar cuenta
                </Button>
              </article>
            )
          })}
        </section>

        <section className="mb-5 overflow-hidden rounded-2xl border border-[#DDE6F2] bg-white shadow-[0_8px_28px_rgba(30,64,175,0.05)]">
          <header className="flex items-center justify-between border-b border-slate-100 px-4 py-4">
            <div><h2 className="text-sm font-bold text-slate-900">Conexiones</h2><p className="mt-0.5 text-xs text-slate-500">El token nunca se muestra ni se almacena en el navegador.</p></div>
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600">{connections.length}</span>
          </header>
          {connections.length === 0 ? (
            <EmptyState icon={Unplug} title="Aún no hay cuentas conectadas" description="Elige un canal para iniciar la autorización segura en Meta." />
          ) : (
            <div className="divide-y divide-slate-100">
              {connections.map((connection) => (
                <div key={connection.id} className="flex flex-col gap-3 px-4 py-4 lg:flex-row lg:items-center">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-sm font-bold text-slate-900">{connection.display_name || `Cuenta ${connection.external_principal_id}`}</p>
                      <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide', connection.status === 'active' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500')}>{connection.status}</span>
                      <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700">{connection.owner_type === 'broker' ? 'Corporativa' : 'Del ejecutivo'}</span>
                    </div>
                    <p className="mt-1 text-xs capitalize text-slate-500">{connectionChannels(connection, assets)}</p>
                    {connection.expires_at && <p className="mt-1 text-[11px] text-slate-400">Vence {new Date(connection.expires_at).toLocaleDateString('es-CL')}</p>}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {isAdmin && connection.status === 'active' && <Button variant="outline" size="sm" disabled={busyKey !== null} onClick={() => sync(connection)}><RefreshCw className="mr-1.5 h-3.5 w-3.5" /> Sincronizar</Button>}
                    {connection.status === 'active' && <Button variant="outline" size="sm" disabled={busyKey !== null} onClick={() => disconnect(connection)}><Unplug className="mr-1.5 h-3.5 w-3.5" /> Desconectar</Button>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {isAdmin && (
          <section className="mb-5 overflow-hidden rounded-2xl border border-[#C8D9F2] bg-white shadow-[0_8px_28px_rgba(30,64,175,0.06)]">
            <header className="flex flex-col gap-3 border-b border-slate-100 bg-[linear-gradient(115deg,#F4F8FF,#FFFFFF)] px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-100 text-[#1A56DB]"><Database className="h-5 w-5" /></span>
                <div><h2 className="text-sm font-bold text-slate-900">Dataset de conversiones</h2><p className="mt-0.5 text-xs leading-5 text-slate-500">Selecciona el único destino corporativo que recibirá eventos consentidos de Conversions API.</p></div>
              </div>
              <span className="w-fit rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-blue-700">{conversionDatasets.some((asset) => asset.is_default) ? 'Destino seleccionado' : 'Requiere selección'}</span>
            </header>
            {conversionDatasets.length === 0 ? (
              <EmptyState icon={Database} title="Sin datasets descubiertos" description="Sincroniza una conexión Meta Business con acceso a una cuenta publicitaria y sus datasets/píxeles." />
            ) : (
              <div className="divide-y divide-slate-100">
                {conversionDatasets.map((asset) => {
                  const eligible = asset.owner_type === 'broker' && asset.approval_status === 'approved' && asset.status === 'active' && asset.capabilities.includes('conversions')
                  return (
                    <article key={asset.id} className="grid gap-3 px-4 py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2"><p className="truncate text-sm font-bold text-slate-900">{asset.display_name || asset.external_id}</p>{asset.is_default && <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-bold text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" /> En uso</span>}</div>
                        <p className="mt-1 text-xs text-slate-500">ID {asset.external_id} · {ownerLabel(asset, users)}</p>
                        {!eligible && <p className="mt-1 text-[11px] font-semibold text-amber-700">Debe ser corporativo, activo, aprobado y permitir conversiones.</p>}
                      </div>
                      <Button variant={asset.is_default ? 'outline' : 'default'} size="sm" disabled={busyKey !== null || asset.is_default || !eligible} onClick={() => updateAsset(asset, { is_default: true }, 'Dataset de conversiones seleccionado')}>
                        {asset.is_default ? 'Seleccionado' : 'Usar en Conversions API'}
                      </Button>
                    </article>
                  )
                })}
              </div>
            )}
          </section>
        )}

        <section className="overflow-hidden rounded-2xl border border-[#DDE6F2] bg-white shadow-[0_8px_28px_rgba(30,64,175,0.05)]">
          <header className="flex items-center justify-between border-b border-slate-100 px-4 py-4">
            <div><h2 className="text-sm font-bold text-slate-900">Identidades y activos</h2><p className="mt-0.5 text-xs text-slate-500">Cada conversación queda vinculada a un activo exacto y auditable.</p></div>
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600">{channelAssets.length}</span>
          </header>
          {channelAssets.length === 0 ? (
            <EmptyState icon={Users} title="Sin activos descubiertos" description="Conecta una cuenta para importar páginas, números y perfiles profesionales." />
          ) : (
            <div className="divide-y divide-slate-100">
              {channelAssets.map((asset) => (
                <article key={asset.id} className="grid gap-3 px-4 py-4 lg:grid-cols-[minmax(210px,1fr)_150px_170px_170px_120px] lg:items-center">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2"><p className="truncate text-sm font-bold text-slate-900">{asset.display_name || asset.external_id}</p>{asset.is_default && <span title="Activo predeterminado"><CheckCircle2 className="h-4 w-4 text-[#1A56DB]" /></span>}</div>
                    <p className="mt-1 text-xs capitalize text-slate-500">{asset.channel || asset.asset_type} · {ownerLabel(asset, users)} · ID {asset.external_id}</p>
                    {asset.last_error_code && <p className="mt-1 text-[11px] font-medium text-rose-600">Error: {asset.last_error_code}</p>}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <span className={cn('rounded-full px-2 py-1 text-[10px] font-bold', asset.approval_status === 'approved' ? 'bg-emerald-50 text-emerald-700' : asset.approval_status === 'rejected' ? 'bg-rose-50 text-rose-700' : 'bg-amber-50 text-amber-700')}>{asset.approval_status === 'approved' ? 'Aprobado' : asset.approval_status === 'rejected' ? 'Rechazado' : 'Por aprobar'}</span>
                    <span className={cn('rounded-full px-2 py-1 text-[10px] font-bold', asset.status === 'active' ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-500')}>{asset.status}</span>
                  </div>
                  {isAdmin ? (
                    <select aria-label={`Responsable de ${asset.display_name || asset.external_id}`} className={selectClass} value={asset.assigned_user_id ?? ''} disabled={busyKey !== null} onChange={(event) => updateAsset(asset, { assigned_user_id: event.target.value ? Number(event.target.value) : null }, 'Responsable actualizado')}>
                      <option value="">Sin responsable</option>
                      {activeAgents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
                    </select>
                  ) : <span className="text-xs text-slate-500">Asignado a ti</span>}
                  {isAdmin ? (
                    <select aria-label={`Modo de IA de ${asset.display_name || asset.external_id}`} className={selectClass} value={asset.ai_mode} disabled={busyKey !== null} onChange={(event) => updateAsset(asset, { ai_mode: event.target.value as MetaAsset['ai_mode'] }, 'Modo de IA actualizado')}>
                      <option value="suggestion">IA sugiere</option>
                      <option value="supervised_auto">IA automática supervisada</option>
                      <option value="human">Solo humano</option>
                    </select>
                  ) : <span className="flex items-center gap-1.5 text-xs text-slate-500"><Bot className="h-3.5 w-3.5" /> {asset.ai_mode === 'human' ? 'Solo humano' : 'IA asistida'}</span>}
                  {isAdmin && (
                    <div className="flex justify-end gap-2">
                      {asset.approval_status === 'pending_approval' ? (
                        <>
                          <button className="rounded-lg bg-emerald-50 px-2.5 py-2 text-[11px] font-bold text-emerald-700 hover:bg-emerald-100" disabled={busyKey !== null} onClick={() => updateAsset(asset, { approval_status: 'approved', status: 'active' }, 'Activo aprobado')}>Aprobar</button>
                          <button className="rounded-lg bg-rose-50 px-2.5 py-2 text-[11px] font-bold text-rose-700 hover:bg-rose-100" disabled={busyKey !== null} onClick={() => updateAsset(asset, { approval_status: 'rejected', status: 'paused' }, 'Activo rechazado')}>Rechazar</button>
                        </>
                      ) : (
                        <button className="rounded-lg border border-slate-200 px-2.5 py-2 text-[11px] font-bold text-slate-600 hover:bg-slate-50" disabled={busyKey !== null} onClick={() => updateAsset(asset, { status: asset.status === 'active' ? 'paused' : 'active' }, asset.status === 'active' ? 'Activo pausado' : 'Activo reactivado')}>{asset.status === 'active' ? 'Pausar' : 'Activar'}</button>
                      )}
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
