import { fireEvent, render, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { LeadDrawer } from './LeadDrawer'
import type { Lead } from '@/features/leads/types'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('@/shared/hooks/usePermissions', () => ({
  usePermissions: () => ({ isSuperAdmin: false }),
}))

vi.mock('@/features/leads/components/LeadFollowUpPanel', () => ({
  LeadFollowUpPanel: ({ lead }: { lead: Lead }) => (
    <div>Seguimiento activo para {lead.name}</div>
  ),
}))

vi.mock('../services/chat.service', () => ({
  chatService: { getMessages: vi.fn().mockResolvedValue([]) },
}))

vi.mock('../services/appointment.service', () => ({
  appointmentService: { getForLead: vi.fn().mockResolvedValue([]) },
}))

vi.mock('../services/pipeline.service', () => ({
  pipelineService: { listAgents: vi.fn().mockResolvedValue([]) },
}))

const lead: Lead = {
  id: 42,
  broker_id: 1,
  assigned_to: 7,
  name: 'Ana Pérez',
  phone: '+56911111111',
  email: 'ana@example.com',
  status: 'warm',
  lead_score: 72,
  pipeline_stage: 'perfilamiento',
  lead_metadata: {},
  tags: [],
  created_at: '2026-08-25T12:00:00Z',
}

describe('LeadDrawer follow-up tab', () => {
  it('opens task and note follow-up directly from Pipeline', async () => {
    const view = render(
      <LeadDrawer lead={lead} onClose={vi.fn()} onMoveStage={vi.fn()} />
    )

    fireEvent.click(view.getByRole('button', { name: /Seguimiento/ }))

    await waitFor(() => {
      expect(view.getByText('Seguimiento activo para Ana Pérez')).toBeTruthy()
    })
  })
})
