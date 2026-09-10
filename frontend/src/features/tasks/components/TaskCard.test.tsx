import { fireEvent, render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { TaskCard } from './TaskCard'
import type { LeadTask } from '../types'

function makeTask(overrides: Partial<LeadTask> = {}): LeadTask {
  return {
    id: 1,
    lead_id: 10,
    lead_name: 'Ana Pérez',
    lead_phone: '+56911111111',
    title: 'Confirmar documentos',
    status: 'open',
    assigned_to: 7,
    assignee_name: 'Ejecutivo Uno',
    created_by: 7,
    creator_name: 'Ejecutivo Uno',
    completed_by: null,
    due_at: new Date(Date.now() - 60_000).toISOString(),
    reminder_minutes_before: 60,
    reminder_at: null,
    reminder_sent_at: null,
    reminder_acknowledged_at: null,
    completed_at: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  }
}

describe('TaskCard', () => {
  it('shows overdue context and completes through its accessible control', () => {
    const onComplete = vi.fn()
    const task = makeTask()
    const view = render(
      <TaskCard task={task} canComplete onComplete={onComplete} />
    )

    expect(view.getByText(/Vencida/)).toBeTruthy()
    fireEvent.click(view.getByLabelText('Completar tarea'))
    expect(onComplete).toHaveBeenCalledWith(task)
  })

  it('renders completed tasks with a reopen action', () => {
    const onReopen = vi.fn()
    const task = makeTask({ status: 'completed', completed_at: new Date().toISOString() })
    const view = render(
      <TaskCard task={task} canComplete onReopen={onReopen} />
    )

    fireEvent.click(view.getByLabelText('Reabrir tarea'))
    expect(onReopen).toHaveBeenCalledWith(task)
  })

  it('lets the responsible executive start a pending task', () => {
    const onStart = vi.fn()
    const task = makeTask()
    const view = render(
      <TaskCard task={task} canComplete onStart={onStart} />
    )

    fireEvent.click(view.getByRole('button', { name: 'Iniciar' }))
    expect(onStart).toHaveBeenCalledWith(task)
  })
})
