import { apiClient } from '@/shared/lib/api-client';

export interface DealMetrics {
  deals_by_stage: Record<string, number>
  uf_en_pipeline: number
  uf_cerradas: number
  clp_cerradas: number
  total_active_deals: number
  deals_closed: number
  bank_approval_rate: number
  avg_ticket_uf: number
  avg_ticket_clp: number
  reservations_period: number
  promises_signed_period: number
  cancellations_period: number
  cancellation_rate: number
  avg_sales_cycle_days: number | null
  avg_reservation_to_close_days: number | null
  sales_this_week: SalesComparison
  sales_this_month: SalesComparison
  uf_trend: WeeklySalesPoint[]
  monthly_trend: MonthlySalesPoint[]
  sales_by_project: ProjectSales[]
}

export interface SalesComparison {
  sales: number
  uf: number
  clp: number
  previous_sales: number
  previous_uf: number
  sales_delta_percent: number | null
  uf_delta_percent: number | null
  date_from: string
  date_to: string
}

export interface WeeklySalesPoint {
  week: string
  week_start: string
  sales: number
  uf: number
  clp: number
}

export interface MonthlySalesPoint {
  month: string
  month_start: string
  sales: number
  uf: number
  clp: number
}

export interface ProjectSales {
  project_id: number | null
  project_name: string
  sales: number
  uf: number
  clp: number
}

import type {
  Deal,
  DealDetail,
  DealDocument,
  CreateDealRequest,
  TransitionDealRequest,
  CancelDealRequest,
  ReviewRequest,
  SlotRequirement,
  Payment,
  PaymentLinkResponse,
} from '../types';

export const dealsApi = {
  create: (data: CreateDealRequest): Promise<Deal> =>
    apiClient.post('/api/deals', data),

  list: (params?: {
    lead_id?: number;
    property_id?: number;
    stage?: string;
    limit?: number;
    offset?: number;
  }): Promise<Deal[]> =>
    apiClient.get('/api/deals', { params }),

  get: (dealId: number): Promise<DealDetail> =>
    apiClient.get(`/api/deals/${dealId}`),

  transition: (dealId: number, data: TransitionDealRequest): Promise<Deal> =>
    apiClient.post(`/api/deals/${dealId}/transition`, data),

  cancel: (dealId: number, data: CancelDealRequest): Promise<Deal> =>
    apiClient.post(`/api/deals/${dealId}/cancel`, data),

  bankReview: (dealId: number, data: ReviewRequest): Promise<Deal> =>
    apiClient.post(`/api/deals/${dealId}/bank-review`, data),

  jefaturaReview: (dealId: number, data: ReviewRequest): Promise<Deal> =>
    apiClient.post(`/api/deals/${dealId}/jefatura-review`, data),

  uploadDocument: async (
    dealId: number,
    slot: string,
    file: File,
    slotIndex = 0,
  ): Promise<DealDocument> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('slot', slot);
    formData.append('slot_index', String(slotIndex));
    return apiClient.post(`/api/deals/${dealId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  /** Returns a redirect URL for downloading a document (not a fetch call). */
  downloadDocument: (dealId: number, docId: number): string =>
    `/api/deals/${dealId}/documents/${docId}/download`,

  approveDocument: (dealId: number, docId: number, notes?: string): Promise<DealDocument> =>
    apiClient.post(`/api/deals/${dealId}/documents/${docId}/approve`, { notes }),

  rejectDocument: (dealId: number, docId: number, notes: string): Promise<DealDocument> =>
    apiClient.post(`/api/deals/${dealId}/documents/${docId}/reject`, { notes }),

  deleteDocument: (dealId: number, docId: number): Promise<void> =>
    apiClient.delete(`/api/deals/${dealId}/documents/${docId}`),

  getSlotsMeta: (
    deliveryType?: string,
  ): Promise<{ slots: SlotRequirement[]; delivery_type: string }> =>
    apiClient.get('/api/deals/slots-meta', { params: { delivery_type: deliveryType } }),

  createPaymentLink: (dealId: number, data: { amount: number }): Promise<PaymentLinkResponse> =>
    apiClient.post(`/api/deals/${dealId}/payment-link`, data),

  getPayments: (dealId: number): Promise<Payment[]> =>
    apiClient.get(`/api/deals/${dealId}/payments`),

  cancelPayment: (dealId: number, paymentId: number): Promise<Payment> =>
    apiClient.post(`/api/deals/${dealId}/payments/${paymentId}/cancel`, {}),

  getMetrics: (params?: {
    broker_id?: number | null
    date_from?: string
    date_to?: string
  }): Promise<DealMetrics> => {
    const p: Record<string, unknown> = {}
    if (params?.broker_id) p.broker_id = params.broker_id
    if (params?.date_from) p.date_from = params.date_from
    if (params?.date_to) p.date_to = params.date_to
    return apiClient.get('/api/deals/metrics', { params: Object.keys(p).length ? p : undefined })
  },
};
