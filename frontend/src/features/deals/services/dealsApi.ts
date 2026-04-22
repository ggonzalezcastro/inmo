import { apiClient } from '@/shared/lib/api-client';
import type {
  Deal,
  DealDetail,
  DealDocument,
  CreateDealRequest,
  TransitionDealRequest,
  CancelDealRequest,
  ReviewRequest,
  SlotRequirement,
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
};
