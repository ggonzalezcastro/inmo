import { fireEvent, render, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MetaAdsPage } from './MetaAdsPage'
import { MetaChannelsPage } from './MetaChannelsPage'
import { MetaInboxPage } from './MetaInboxPage'

const state = vi.hoisted(() => ({
  user: { id: 9, broker_id: 3, role: 'admin', name: 'Jefatura' },
}))

const service = vi.hoisted(() => ({
  health: vi.fn(), connections: vi.fn(), assets: vi.fn(), users: vi.fn(), authorize: vi.fn(),
  disconnect: vi.fn(), revalidate: vi.fn(), sync: vi.fn(), updateFeatures: vi.fn(), updateAsset: vi.fn(), templates: vi.fn(),
  conversations: vi.fn(), conversation: vi.fn(), messages: vi.fn(), read: vi.fn(), send: vi.fn(), summary: vi.fn(), draft: vi.fn(), suggestTask: vi.fn(), approveTask: vi.fn(), conflicts: vi.fn(), resolveConflict: vi.fn(),
  adsAssets: vi.fn(), adsProjects: vi.fn(), adsPolicy: vi.fn(), updateAdsPolicy: vi.fn(), adCampaigns: vi.fn(), createAdCampaign: vi.fn(), updateAdCampaign: vi.fn(), transitionAdCampaign: vi.fn(), activateAdCampaign: vi.fn(), pauseAdCampaign: vi.fn(), leadForms: vi.fn(), previewLeadForm: vi.fn(), updateLeadForm: vi.fn(), syncLeadForms: vi.fn(), syncAdsInsights: vi.fn(), adsAnalytics: vi.fn(), adsAnalyticsLeads: vi.fn(), conversionDiagnostics: vi.fn(),
}))

vi.mock('@/features/auth', () => ({ useAuthStore: (selector: (value: unknown) => unknown) => selector({ user: state.user }) }))
vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn(), info: vi.fn(), warning: vi.fn() } }))
vi.mock('../services/meta.service', () => ({ metaService: service }))

const health = {
  configured: true, global_enabled: true, broker_enabled: true,
  channels: { whatsapp: true, instagram: true, messenger: true, ads: true, lead_ads: true, conversions_api: false },
  overrides: {}, graph_api_version: 'v26.0',
  configuration: { app_credentials: true, webhook_verify_token: true, oauth_redirect_configured: true, oauth_redirect_https: true, embedded_signup_config: true, credential_encryption_key: true },
  legacy_whatsapp_fallback_enabled: true,
}
const assets = [{
  id: 5, broker_id: 3, connection_id: 2, asset_type: 'whatsapp_phone', channel: 'whatsapp', external_id: 'phone-1', parent_external_id: 'waba-1', display_name: 'Ventas Norte', owner_type: 'broker', owner_user_id: null, assigned_user_id: 11, capabilities: ['messaging', 'templates'], approval_status: 'approved', status: 'active', is_default: true, ai_mode: 'suggestion', last_synced_at: null, last_error_code: null, created_at: '2026-09-01T10:00:00Z', updated_at: '2026-09-01T10:00:00Z',
}]
const policy = { currency: 'CLP', max_daily_budget: 50000, max_lifetime_budget: 500000, require_budget_increase_confirmation: true, version: 1 }
const analytics = {
  kpis: { spend: 20000, impressions: 1000, reach: 800, clicks: 70, conversations: 12, meta_leads: 8, crm_leads: 7, advised: 5, meetings: 3, reservations: 2, sales: 1, sales_uf: 3200, sales_clp: 128000000, cost_per_conversation: 1666, cost_per_lead: 2857, cost_per_advised: 4000, cost_per_meeting: 6667, cost_per_reservation: 10000, cost_per_sale: 20000 },
  trend: [{ date: '2026-09-01', spend: 20000, leads: 8, conversations: 12 }], campaigns: [], freshness_at: '2026-09-01T10:00:00Z', partial_sync: false,
}
const campaign = {
  id: 41, broker_id: 3, ad_account_asset_id: 20, project_id: 4, created_by_user_id: 11, approved_by_user_id: null,
  operation_uuid: 'operation-41', name: 'Lanzamiento Parque Norte', objective: 'OUTCOME_LEADS', destination_type: 'website', special_ad_category: 'HOUSING',
  status: 'pending_review', daily_budget: 15000, lifetime_budget: null, currency: 'CLP', version: 2, external_id: null, remote_status: null,
  rejection_comment: null, last_error_code: null, last_error_detail: null, submitted_at: '2026-09-01T10:00:00Z', approved_at: null, published_at: null, activated_at: null, paused_at: null,
  created_at: '2026-09-01T09:00:00Z', updated_at: '2026-09-01T10:00:00Z',
  ad_sets: [{ id: 51, name: 'Chile', optimization_goal: 'LINK_CLICKS', billing_event: 'IMPRESSIONS', targeting: { geo_locations: { countries: ['CL'] } }, promoted_object: {}, start_at: '2026-09-10T12:00:00Z', end_at: '2026-09-20T12:00:00Z', external_id: null, remote_status: null }],
  creatives: [{ id: 61, page_asset_id: 5, instagram_asset_id: null, name: 'Creatividad', primary_text: 'Departamentos disponibles según inventario vigente.', headline: 'Conoce el proyecto', description: null, call_to_action: 'LEARN_MORE', destination_url: 'https://example.com/proyecto', media_url: null, media_hash: null, external_id: null, validation_result: {} }],
  ads: [],
  submission_snapshot: {
    name: 'Lanzamiento Parque Norte', ad_account_asset_id: 20, project_id: 4, objective: 'OUTCOME_LEADS', destination_type: 'website', special_ad_category: 'HOUSING', daily_budget: '15000.00', lifetime_budget: null, currency: 'CLP', version: 1,
    ad_set: { name: 'Chile', optimization_goal: 'LINK_CLICKS', billing_event: 'IMPRESSIONS', targeting: { geo_locations: { countries: ['CL'] } }, promoted_object: {}, start_at: '2026-09-10T12:00:00Z', end_at: '2026-09-20T12:00:00Z' },
    creative: { page_asset_id: 5, instagram_asset_id: null, name: 'Creatividad', primary_text: 'Departamentos disponibles según inventario vigente.', headline: 'Conoce el proyecto', description: null, call_to_action: 'LEARN_MORE', destination_url: 'https://example.com/proyecto', media_url: null, media_hash: null },
  },
}

describe('Meta ecosystem screens', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    state.user = { id: 9, broker_id: 3, role: 'admin', name: 'Jefatura' }
    service.health.mockResolvedValue(health)
    service.connections.mockResolvedValue([])
    service.assets.mockResolvedValue(assets)
    service.users.mockResolvedValue([{ id: 11, name: 'Ana Ejecutiva', email: 'ana@example.com', role: 'agent', is_active: true }])
    service.conflicts.mockResolvedValue([])
    service.adsAssets.mockResolvedValue([{ ...assets[0], id: 20, asset_type: 'ad_account', channel: null, external_id: 'act_20', display_name: 'Cuenta Broker', capabilities: ['ads', 'insights'] }])
    service.adsProjects.mockResolvedValue([{ id: 4, name: 'Parque Norte', status: 'en_venta' }])
    service.adsPolicy.mockResolvedValue(policy)
    service.adCampaigns.mockResolvedValue([])
    service.leadForms.mockResolvedValue([])
    service.adsAnalytics.mockResolvedValue(analytics)
    service.conversionDiagnostics.mockResolvedValue([])
    service.conversations.mockResolvedValue({ items: [], next_cursor: null, has_more: false })
  })

  it('separates corporate administration from executive professional channels', async () => {
    const view = render(<MemoryRouter><MetaChannelsPage /></MemoryRouter>)
    await waitFor(() => expect(view.getByText('Disponibilidad para el broker')).toBeTruthy())
    expect(view.getByText('WhatsApp Business')).toBeTruthy()
    expect(view.getByText('Meta Business')).toBeTruthy()
    expect(view.getAllByText('Instagram').length).toBeGreaterThan(0)
    expect(view.getByText(/ID phone-1/)).toBeTruthy()
  })

  it('lets management select the corporate Conversions API dataset', async () => {
    const dataset = { ...assets[0], id: 30, asset_type: 'pixel', channel: null, external_id: 'pixel-30', display_name: 'Dataset CRM', assigned_user_id: null, capabilities: ['conversions'], is_default: false }
    service.assets.mockResolvedValue([...assets, dataset])
    service.updateAsset.mockResolvedValue({ ...dataset, is_default: true })
    const view = render(<MemoryRouter><MetaChannelsPage /></MemoryRouter>)
    await waitFor(() => expect(view.getByText('Dataset CRM')).toBeTruthy())
    fireEvent.click(view.getByRole('button', { name: 'Usar en Conversions API' }))
    await waitFor(() => expect(service.updateAsset).toHaveBeenCalledWith(30, { is_default: true }))
  })

  it('shows spend-to-sale KPIs and complete management filters', async () => {
    const view = render(<MemoryRouter><MetaAdsPage /></MemoryRouter>)
    await waitFor(() => expect(view.getByText('Leads CRM')).toBeTruthy())
    expect(view.getByText('Asesorados')).toBeTruthy()
    expect(view.getByText('Reservas')).toBeTruthy()
    expect(view.getByText('Ventas')).toBeTruthy()
    expect(view.getByLabelText('Cuenta publicitaria')).toBeTruthy()
    expect(view.getByLabelText('Proyecto')).toBeTruthy()
    expect(view.getByLabelText('Ejecutivo')).toBeTruthy()
    fireEvent.click(view.getByRole('button', { name: /conversiones/i }))
    expect(view.getByText('Diagnóstico de Conversions API')).toBeTruthy()
  })

  it('renders the unified inbox empty state with all channel filters', async () => {
    const view = render(<MemoryRouter><MetaInboxPage /></MemoryRouter>)
    await waitFor(() => expect(view.getByText('No hay conversaciones')).toBeTruthy())
    expect(view.getByLabelText('Filtrar por canal')).toBeTruthy()
    expect(view.getByLabelText('Filtrar por proyecto')).toBeTruthy()
    expect(view.getByLabelText('Mensajes desde')).toBeTruthy()
  })

  it('reviews the immutable campaign snapshot before approval', async () => {
    service.adCampaigns.mockResolvedValue([campaign])
    service.transitionAdCampaign.mockResolvedValue({ ...campaign, status: 'approved', version: 3 })
    const view = render(<MemoryRouter><MetaAdsPage /></MemoryRouter>)
    await waitFor(() => expect(view.getByText('Leads CRM')).toBeTruthy())
    fireEvent.click(view.getByRole('button', { name: 'Campañas' }))
    fireEvent.click(view.getByRole('button', { name: 'Aprobar' }))
    expect(view.getByText('Revisión de campaña')).toBeTruthy()
    expect(view.getByText('Sin cambios desde el envío.')).toBeTruthy()
    fireEvent.click(view.getByRole('button', { name: 'Aprobar snapshot' }))
    await waitFor(() => expect(service.transitionAdCampaign).toHaveBeenCalledWith(41, 'approve', 2, undefined))
  })

  it('requires structured spend confirmation before activation', async () => {
    const published = { ...campaign, status: 'published_paused', version: 5, external_id: 'remote-41' }
    service.adCampaigns.mockResolvedValue([published])
    service.activateAdCampaign.mockResolvedValue({ ...published, status: 'active', version: 6 })
    const view = render(<MemoryRouter><MetaAdsPage /></MemoryRouter>)
    await waitFor(() => expect(view.getByText('Leads CRM')).toBeTruthy())
    fireEvent.click(view.getByRole('button', { name: 'Campañas' }))
    fireEvent.click(view.getByRole('button', { name: 'Activar gasto' }))
    expect(view.getByText('Confirmar activación de gasto')).toBeTruthy()
    expect(view.getByText('Cuenta Broker')).toBeTruthy()
    const activate = view.getByRole('button', { name: 'Activar campaña y comenzar gasto' }) as HTMLButtonElement
    expect(activate.disabled).toBe(true)
    fireEvent.click(view.getByLabelText('Confirmo el gasto'))
    fireEvent.click(activate)
    await waitFor(() => expect(service.activateAdCampaign).toHaveBeenCalledWith(41, 5))
  })

  it('previews the normalized lead before saving a form mapping', async () => {
    const form = { id: 71, page_asset_id: 5, project_id: 4, external_id: 'form-71', name: 'Cotiza Parque Norte', status: 'active', questions: [{ key: 'full_name', label: 'Nombre' }, { key: 'phone_number', label: 'Teléfono' }], field_mapping: {}, last_synced_at: null }
    const preview = { lead_payload: { phone: '+56912345678', name: 'María Soto', email: null, tags: ['meta-lead-ad'], metadata: { source: 'meta_lead_ads', project_id: 4 } }, source_values: { full_name: 'María Soto', phone_number: '9 1234 5678' }, warnings: [] }
    service.leadForms.mockResolvedValue([form])
    service.previewLeadForm.mockResolvedValue(preview)
    service.updateLeadForm.mockResolvedValue({ ...form, field_mapping: { full_name: 'name', phone_number: 'phone' } })
    const view = render(<MemoryRouter><MetaAdsPage /></MemoryRouter>)
    await waitFor(() => expect(view.getByText('Leads CRM')).toBeTruthy())
    fireEvent.click(view.getByRole('button', { name: 'Formularios' }))
    fireEvent.click(view.getByRole('button', { name: 'Configurar' }))
    const save = view.getByRole('button', { name: 'Guardar mapeo' }) as HTMLButtonElement
    expect(save.disabled).toBe(true)
    fireEvent.click(view.getByRole('button', { name: 'Previsualizar lead' }))
    await waitFor(() => expect(view.getByText('+56912345678')).toBeTruthy())
    expect(save.disabled).toBe(false)
    fireEvent.click(save)
    await waitFor(() => expect(service.updateLeadForm).toHaveBeenCalledWith(71, { project_id: 4, field_mapping: { full_name: 'name', phone_number: 'phone' } }))
  })
})
