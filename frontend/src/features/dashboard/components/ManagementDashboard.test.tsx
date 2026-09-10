import { render, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ManagementDashboard } from './ManagementDashboard'
import { dashboardService, type ManagementDashboardMetrics } from '../services/dashboard.service'

vi.mock('sonner', () => ({ toast: { error: vi.fn() } }))
vi.mock('../services/dashboard.service', async (importOriginal) => {
  const original = await importOriginal<typeof import('../services/dashboard.service')>()
  return { ...original, dashboardService: { ...original.dashboardService, getManagementMetrics: vi.fn() } }
})

const metrics: ManagementDashboardMetrics = {
  period: { date_from: '2026-08-01', date_to: '2026-08-31' },
  filters: { agents: [{ id: 7, name: 'Ejecutivo Uno' }], projects: [{ id: 3, name: 'Proyecto Centro' }], sources: ['Meta Ads'] },
  commercial: {
    received: 20, assigned: 18, contacted: 15, advised: 11, without_follow_up: 3,
    first_response_minutes: 42, appointments: { scheduled: 5, completed: 4, cancelled: 1, no_show: 2 },
    reservations: 3, sales: 2, sales_uf: 8000, sales_clp: 300000000,
    conversion_rate: 10, lead_to_sale_days: 28, lost: 4,
  },
  tasks: {
    created: 10, pending: 3, in_progress: 2, overdue: 1, completed: 5,
    completion_rate: 50, on_time_rate: 80, avg_resolution_hours: 18, avg_delay_hours: 4,
  },
  by_agent: [{ id: 7, name: 'Ejecutivo Uno', leads: 20, contacted: 15, advised: 11, reservations: 3, sales: 2, conversion_rate: 10, active_tasks: 5, overdue_tasks: 1, completed_tasks: 5, on_time_rate: 80 }],
  by_project: [{ id: 3, name: 'Proyecto Centro', deals: 4, reservations: 3, sales: 2, uf: 8000, clp: 300000000 }],
  by_source: [{ source: 'Meta Ads', leads: 20, contacted: 15, advised: 11, sales: 2, conversion_rate: 10 }],
  lost_reasons: [{ reason: 'Precio', count: 4 }],
  trend: [{ week: '2026-08-17', label: '17/08', leads: 20, advised: 11, sales: 2, tasks_completed: 5 }],
  drilldowns: { received: { total: 20, data: [] } },
  definitions: { contacted: 'Contacto registrado.', first_response: 'Primera respuesta.', without_follow_up: 'Sin seguimiento.', sales_clp: 'Ventas CLP.' },
}

describe('ManagementDashboard', () => {
  it('shows commercial and task management metrics together', async () => {
    vi.mocked(dashboardService.getManagementMetrics).mockResolvedValue(metrics)
    const view = render(<MemoryRouter><ManagementDashboard brokerId={1} /></MemoryRouter>)

    await waitFor(() => expect(view.getByText('Rendimiento por ejecutivo')).toBeTruthy())
    expect(view.getByText('Cumplimiento de tareas')).toBeTruthy()
    expect(view.getByText('Ventas cerradas')).toBeTruthy()
    expect(view.getByText('Resultados por proyecto')).toBeTruthy()
    expect(view.getAllByText('Meta Ads').length).toBeGreaterThan(0)
  })

  it('shows the same dashboard as a personal view without an executive filter', async () => {
    vi.mocked(dashboardService.getManagementMetrics).mockResolvedValue(metrics)
    const view = render(<MemoryRouter><ManagementDashboard brokerId={1} personal /></MemoryRouter>)

    await waitFor(() => expect(view.getByText('Mi rendimiento comercial')).toBeTruthy())
    expect(view.getByText('Mi cumplimiento de tareas')).toBeTruthy()
    expect(view.queryByLabelText('Ejecutivo')).toBeNull()
  })
})
