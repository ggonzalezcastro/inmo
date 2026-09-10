import { fireEvent, render, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { TaskFormDialog } from './TaskFormDialog'
import { tasksService } from '../services/tasks.service'
import type { LeadTask } from '../types'

vi.mock('@/shared/hooks/usePermissions', () => ({
  usePermissions: () => ({ role: 'agent' }),
}))

vi.mock('@/features/appointments/components/LeadSearchCombobox', () => ({
  LeadSearchCombobox: ({ onChange }: { onChange: (lead: unknown) => void }) => (
    <button
      type="button"
      onClick={() => onChange({ id: 42, name: 'Ana Pérez', phone: '+56911111111', assigned_to: 7 })}
    >
      Seleccionar Ana Pérez
    </button>
  ),
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('../services/tasks.service', () => ({
  tasksService: {
    createTask: vi.fn(),
    updateTask: vi.fn(),
    listAgents: vi.fn(),
  },
}))

const createdTask: LeadTask = {
  id: 9,
  lead_id: 42,
  lead_name: 'Ana Pérez',
  lead_phone: '+56911111111',
  title: 'Llamar para confirmar documentos',
  status: 'open',
  assigned_to: 7,
  assignee_name: 'Ejecutivo Uno',
  created_by: 7,
  creator_name: 'Ejecutivo Uno',
  completed_by: null,
  due_at: '2026-08-26T15:00:00Z',
  reminder_minutes_before: 60,
  reminder_at: '2026-08-26T14:00:00Z',
  reminder_sent_at: null,
  reminder_acknowledged_at: null,
  completed_at: null,
  created_at: '2026-08-25T12:00:00Z',
  updated_at: '2026-08-25T12:00:00Z',
}

describe('TaskFormDialog from task inbox', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(tasksService.createTask).mockResolvedValue(createdTask)
  })

  it('requires a lead and creates the task for the selected lead', async () => {
    const onSaved = vi.fn()
    const view = render(
      <TaskFormDialog open onOpenChange={vi.fn()} onSaved={onSaved} />
    )

    const submit = view.getByRole('button', { name: 'Crear tarea' })
    expect(submit).toBeDisabled()

    fireEvent.click(view.getByRole('button', { name: 'Seleccionar Ana Pérez' }))
    expect(view.getByText('Seguimiento para Ana Pérez')).toBeTruthy()

    fireEvent.change(view.getByLabelText('Tarea'), {
      target: { value: 'Llamar para confirmar documentos' },
    })
    fireEvent.click(submit)

    await waitFor(() => {
      expect(tasksService.createTask).toHaveBeenCalledWith(
        42,
        expect.objectContaining({ title: 'Llamar para confirmar documentos' })
      )
      expect(onSaved).toHaveBeenCalledWith(createdTask)
    })
  })
})
