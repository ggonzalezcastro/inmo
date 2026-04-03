import { apiClient } from '@/shared/lib/api-client'

export interface AvailabilitySlot {
  id: number
  day_of_week: number  // 0=Monday, 6=Sunday
  start_time: string   // "HH:MM"
  end_time: string     // "HH:MM"
  slot_duration_minutes: number
  is_active: boolean
  valid_from: string   // ISO date
  valid_until: string | null
  notes: string | null
}

export interface CreateSlotData {
  day_of_week: number
  start_time: string
  end_time: string
  slot_duration_minutes?: number
  valid_from?: string
  valid_until?: string | null
  notes?: string | null
}

export interface AppointmentBlock {
  id: number
  start_time: string  // ISO datetime
  end_time: string    // ISO datetime
  reason: string
  notes: string | null
}

export interface CreateBlockData {
  start_time: string
  end_time: string
  reason: string
  notes?: string | null
}

export interface IncomeTier {
  min: number
  label: string
  points: number
}

export interface ScoringConfig {
  income_tiers: IncomeTier[]
  dicom_clean_pts: number
  dicom_has_debt_pts: number
}

export const DEFAULT_SCORING_CONFIG: ScoringConfig = {
  income_tiers: [
    { min: 3_000_000, label: 'Excelente', points: 40 },
    { min: 2_000_000, label: 'Alto',      points: 32 },
    { min: 1_000_000, label: 'Medio',     points: 20 },
    { min: 500_000,   label: 'Bajo',      points: 10 },
    { min: 0,         label: 'Insuficiente', points: 0 },
  ],
  dicom_clean_pts: 20,
  dicom_has_debt_pts: 8,
}

// Flat shape used by the UI
export interface QualificationConfig {
  // Score thresholds
  cold_max_score: number
  warm_max_score: number
  hot_min_score: number
  qualified_min_score: number
  // Financial qualification
  min_income_calificado: number
  min_income_potencial: number
  max_acceptable_debt: number
  // Scoring config (income tiers + DICOM)
  scoring_config: ScoringConfig
  // Agent timezone
  timezone: string
  // Full custom prompt (overrides all other prompt sections when set)
  full_custom_prompt?: string
  // Legacy field weights (used by 'weights' tab — kept for backward compat)
  field_weights?: Record<string, number>
  field_priority?: string[]
}

interface ApiLeadConfig {
  cold_max_score?: number
  warm_max_score?: number
  hot_min_score?: number
  qualified_min_score?: number
  max_acceptable_debt?: number
  scoring_config?: ScoringConfig
  qualification_criteria?: {
    calificado?: { min_monthly_income?: number }
    potencial?: { min_monthly_income?: number }
  }
}

interface ApiConfigResponse {
  lead_config: ApiLeadConfig
  prompt_config?: { timezone?: string; full_custom_prompt?: string }
}

export interface AgentPromptEntry {
  default: string
  custom: string
}

export interface AgentPromptsConfig {
  qualifier: AgentPromptEntry
  scheduler: AgentPromptEntry
  follow_up: AgentPromptEntry
  multi_agent_enabled: boolean
}

export const settingsService = {
  async getConfig(): Promise<QualificationConfig> {
    const res = await apiClient.get<ApiConfigResponse>('/api/broker/config')
    const l = res.lead_config ?? {}
    const qc = l.qualification_criteria ?? {}
    return {
      cold_max_score: l.cold_max_score ?? 20,
      warm_max_score: l.warm_max_score ?? 50,
      hot_min_score: l.hot_min_score ?? 50,
      qualified_min_score: l.qualified_min_score ?? 75,
      min_income_calificado: qc.calificado?.min_monthly_income ?? 1_000_000,
      min_income_potencial: qc.potencial?.min_monthly_income ?? 500_000,
      max_acceptable_debt: l.max_acceptable_debt ?? 500_000,
      scoring_config: l.scoring_config ?? DEFAULT_SCORING_CONFIG,
      timezone: res.prompt_config?.timezone ?? 'America/Santiago',
      full_custom_prompt: res.prompt_config?.full_custom_prompt ?? '',
      field_weights: (l as any).field_weights ?? { name: 5, phone: 10, monthly_income: 40, dicom_status: 20 },
      field_priority: (l as any).field_priority ?? ['name', 'phone', 'monthly_income', 'dicom_status'],
    }
  },

  async getPromptPreview(): Promise<string> {
    const res = await apiClient.get<{ prompt: string }>('/api/broker/config/prompt/preview')
    return res.prompt
  },

  async getAgentPrompts(): Promise<AgentPromptsConfig> {
    return apiClient.get<AgentPromptsConfig>('/api/broker/config/agent-prompts')
  },

  async saveAgentPrompts(prompts: { qualifier: string; scheduler: string; follow_up: string }): Promise<void> {
    await apiClient.put('/api/broker/config/agent-prompts', prompts)
  },

  async getCalendarStatus(): Promise<{ connected: boolean; email: string | null; calendar_id: string | null }> {
    return apiClient.get('/api/broker/calendar/status')
  },

  async getCalendarAuthUrl(): Promise<{ auth_url: string }> {
    return apiClient.get('/api/broker/calendar/auth-url')
  },

  async disconnectCalendar(): Promise<void> {
    await apiClient.delete('/api/broker/calendar/disconnect')
  },

  // Combined status for both providers
  async getAllCalendarStatus(): Promise<{
    provider: 'google' | 'outlook' | 'none' | null
    google: { connected: boolean; email: string | null }
    outlook: { connected: boolean; email: string | null }
  }> {
    return apiClient.get('/api/broker/calendar/all-status')
  },

  // Outlook Calendar
  async getOutlookCalendarAuthUrl(): Promise<{ auth_url: string }> {
    return apiClient.get('/api/broker/calendar/outlook/auth-url')
  },

  async disconnectOutlookCalendar(): Promise<void> {
    await apiClient.delete('/api/broker/calendar/outlook/disconnect')
  },

  async getAvailabilitySlots(): Promise<AvailabilitySlot[]> {
    return apiClient.get('/api/broker/calendar/availability')
  },

  async createAvailabilitySlot(data: CreateSlotData): Promise<AvailabilitySlot> {
    return apiClient.post('/api/broker/calendar/availability', data)
  },

  async updateAvailabilitySlot(id: number, data: Partial<CreateSlotData>): Promise<AvailabilitySlot> {
    return apiClient.put(`/api/broker/calendar/availability/${id}`, data)
  },

  async deleteAvailabilitySlot(id: number): Promise<void> {
    await apiClient.delete(`/api/broker/calendar/availability/${id}`)
  },

  async getBlocks(): Promise<AppointmentBlock[]> {
    return apiClient.get('/api/broker/calendar/blocks')
  },

  async createBlock(data: CreateBlockData): Promise<AppointmentBlock> {
    return apiClient.post('/api/broker/calendar/blocks', data)
  },

  async deleteBlock(id: number): Promise<void> {
    await apiClient.delete(`/api/broker/calendar/blocks/${id}`)
  },

  async saveConfig(cfg: QualificationConfig): Promise<void> {
    await apiClient.put('/api/broker/config/leads', {
      cold_max_score: cfg.cold_max_score,
      warm_max_score: cfg.warm_max_score,
      hot_min_score: cfg.hot_min_score,
      qualified_min_score: cfg.qualified_min_score,
      max_acceptable_debt: cfg.max_acceptable_debt,
      scoring_config: cfg.scoring_config,
      qualification_criteria: {
        calificado: {
          min_monthly_income: cfg.min_income_calificado,
          dicom_status: ['clean'],
          max_debt_amount: 0,
        },
        potencial: {
          min_monthly_income: cfg.min_income_potencial,
          dicom_status: ['clean', 'has_debt'],
          max_debt_amount: cfg.max_acceptable_debt,
        },
        no_calificado: {
          conditions: [
            { monthly_income_below: cfg.min_income_potencial },
            { debt_amount_above: cfg.max_acceptable_debt },
          ],
        },
      },
    })
    await apiClient.put('/api/broker/config/prompt', {
      timezone: cfg.timezone,
      full_custom_prompt: cfg.full_custom_prompt ?? null,
    })
  },
}


