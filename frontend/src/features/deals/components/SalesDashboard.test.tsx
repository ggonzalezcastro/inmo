import { fireEvent, render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { DealMetrics } from '../services/dealsApi'
import { DealUFTrendChart } from './DealUFTrendChart'
import { SalesInsightsPanel } from './SalesInsightsPanel'
import { SalesKPIGrid } from './SalesKPIGrid'

const metrics: DealMetrics = {
  deals_by_stage: { reserva: 2, escritura_firmada: 3 },
  uf_en_pipeline: 12000,
  uf_cerradas: 9000,
  clp_cerradas: 360000000,
  total_active_deals: 5,
  deals_closed: 3,
  bank_approval_rate: 75,
  avg_ticket_uf: 3000,
  avg_ticket_clp: 120000000,
  reservations_period: 4,
  promises_signed_period: 3,
  cancellations_period: 1,
  cancellation_rate: 20,
  avg_sales_cycle_days: 32.5,
  avg_reservation_to_close_days: 18,
  sales_this_week: {
    sales: 2, uf: 6000, clp: 240000000, previous_sales: 1, previous_uf: 3000,
    sales_delta_percent: 100, uf_delta_percent: 100, date_from: '2026-08-24', date_to: '2026-08-25',
  },
  sales_this_month: {
    sales: 3, uf: 9000, clp: 360000000, previous_sales: 2, previous_uf: 6000,
    sales_delta_percent: 50, uf_delta_percent: 50, date_from: '2026-08-01', date_to: '2026-08-25',
  },
  uf_trend: [{ week: '24 ago', week_start: '2026-08-24', sales: 2, uf: 6000, clp: 240000000 }],
  monthly_trend: [{ month: 'ago 2026', month_start: '2026-08-01', sales: 3, uf: 9000, clp: 360000000 }],
  sales_by_project: [{ project_id: 4, project_name: 'Parque Norte', sales: 3, uf: 9000, clp: 360000000 }],
}

describe('Sales dashboard components', () => {
  it('shows weekly, monthly and operating sales indicators', () => {
    const view = render(
      <>
        <SalesKPIGrid metrics={metrics} isLoading={false} />
        <SalesInsightsPanel metrics={metrics} isLoading={false} />
      </>,
    )

    expect(view.getByText('Ventas semanales')).toBeTruthy()
    expect(view.getByText('Ventas mensuales')).toBeTruthy()
    expect(view.getByText('Promesas firmadas')).toBeTruthy()
    expect(view.getByText('Parque Norte')).toBeTruthy()
    expect(view.getByText('3 ventas')).toBeTruthy()
  })

  it('switches the sales evolution between weekly and monthly data', () => {
    const view = render(
      <DealUFTrendChart data={metrics.uf_trend} monthlyData={metrics.monthly_trend} isLoading={false} />,
    )

    const monthlyButton = view.getByRole('button', { name: 'Mensual' })
    fireEvent.click(monthlyButton)
    expect(monthlyButton.getAttribute('aria-pressed')).toBe('true')
  })
})
