export interface BrokerPlan {
  id: number
  name: string
  description: string | null
  max_leads: number | null
  max_users: number | null
  max_messages_per_month: number | null
  max_llm_cost_per_month: number | null
  is_default: boolean
  is_active: boolean
  created_at: string
}

export interface PlanCreate {
  name: string
  description?: string
  max_leads?: number | null
  max_users?: number | null
  max_messages_per_month?: number | null
  max_llm_cost_per_month?: number | null
  is_default?: boolean
}
