import { fireEvent, render, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AdvisoryFormDialog } from './AdvisoryFormDialog'
import { tasksService } from '../services/tasks.service'
import type { LeadAdvisory } from '../types'

vi.mock('@/shared/hooks/usePermissions', () => ({
  usePermissions: () => ({ role: 'agent' }),
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('../services/tasks.service', () => ({
  tasksService: {
    createAdvisory: vi.fn(),
    listAgents: vi.fn(),
  },
}))

const savedAdvisory: LeadAdvisory = {
  id: 15,
  lead_id: 42,
  advisor_id: 7,
  advisor_name: 'Ejecutivo Uno',
  recorded_by: 7,
  recorder_name: 'Ejecutivo Uno',
  channel: 'phone',
  occurred_at: '2026-08-25T14:00:00Z',
  notes: 'Revisamos presupuesto y próximos pasos.',
  created_at: '2026-08-25T14:05:00Z',
}

describe('AdvisoryFormDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(tasksService.createAdvisory).mockResolvedValue(savedAdvisory)
  })

  it('registers a verified advisory for the current executive', async () => {
    const onSaved = vi.fn()
    const view = render(
      <AdvisoryFormDialog
        open
        onOpenChange={vi.fn()}
        leadId={42}
        leadName="Ana Pérez"
        defaultAdvisorId={7}
        onSaved={onSaved}
      />
    )

    fireEvent.change(view.getByLabelText('Canal'), { target: { value: 'phone' } })
    fireEvent.change(view.getByLabelText('Resumen opcional'), {
      target: { value: 'Revisamos presupuesto y próximos pasos.' },
    })
    fireEvent.click(view.getByRole('button', { name: 'Registrar asesoría' }))

    await waitFor(() => {
      expect(tasksService.createAdvisory).toHaveBeenCalledWith(
        42,
        expect.objectContaining({
          channel: 'phone',
          notes: 'Revisamos presupuesto y próximos pasos.',
        })
      )
      expect(onSaved).toHaveBeenCalledWith(savedAdvisory)
    })
  })
})
