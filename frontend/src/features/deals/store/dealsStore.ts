import { create } from 'zustand';
import type {
  Deal,
  DealDetail,
  DealDocument,
  CreateDealRequest,
  TransitionDealRequest,
  CancelDealRequest,
  ReviewRequest,
} from '../types';
import { dealsApi } from '../services/dealsApi';

interface DealsState {
  // State
  dealsByLeadId: Record<number, Deal[]>;
  dealDetails: Record<number, DealDetail>;
  loading: boolean;
  error: string | null;

  // Actions
  loadDealsForLead: (leadId: number) => Promise<void>;
  loadDealDetail: (dealId: number) => Promise<void>;
  createDeal: (data: CreateDealRequest) => Promise<Deal>;
  transitionDeal: (dealId: number, data: TransitionDealRequest) => Promise<Deal>;
  cancelDeal: (dealId: number, data: CancelDealRequest) => Promise<Deal>;
  submitBankReview: (dealId: number, data: ReviewRequest) => Promise<Deal>;
  submitJefaturaReview: (dealId: number, data: ReviewRequest) => Promise<Deal>;

  // Document actions
  uploadDocument: (dealId: number, slot: string, file: File, slotIndex?: number) => Promise<DealDocument>;
  approveDocument: (dealId: number, docId: number, notes?: string) => Promise<DealDocument>;
  rejectDocument: (dealId: number, docId: number, notes: string) => Promise<DealDocument>;
  deleteDocument: (dealId: number, docId: number) => Promise<void>;

  // Optimistic update helpers
  updateDealInStore: (deal: Deal) => void;
  updateDocumentInStore: (dealId: number, doc: DealDocument) => void;
  removeDocumentFromStore: (dealId: number, docId: number) => void;

  // Live updates (called from WS hook)
  onDealStageChanged: (payload: { deal_id: number; lead_id: number; to_stage: string }) => void;
}

export const useDealsStore = create<DealsState>((set, get) => ({
  dealsByLeadId: {},
  dealDetails: {},
  loading: false,
  error: null,

  loadDealsForLead: async (leadId) => {
    set({ loading: true, error: null });
    try {
      const deals = await dealsApi.list({ lead_id: leadId });
      set((state) => ({
        dealsByLeadId: { ...state.dealsByLeadId, [leadId]: deals },
        loading: false,
      }));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load deals';
      set({ error: message, loading: false });
      throw err;
    }
  },

  loadDealDetail: async (dealId) => {
    set({ loading: true, error: null });
    try {
      const detail = await dealsApi.get(dealId);
      set((state) => ({
        dealDetails: { ...state.dealDetails, [dealId]: detail },
        loading: false,
      }));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load deal detail';
      set({ error: message, loading: false });
      throw err;
    }
  },

  createDeal: async (data) => {
    set({ loading: true, error: null });
    try {
      const deal = await dealsApi.create(data);
      set((state) => {
        const existing = state.dealsByLeadId[data.lead_id] ?? [];
        return {
          dealsByLeadId: { ...state.dealsByLeadId, [data.lead_id]: [...existing, deal] },
          loading: false,
        };
      });
      return deal;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create deal';
      set({ error: message, loading: false });
      throw err;
    }
  },

  transitionDeal: async (dealId, data) => {
    // Optimistic update
    const prevDetails = get().dealDetails;
    const prevByLead = get().dealsByLeadId;
    set((state) => {
      const detail = state.dealDetails[dealId];
      const updatedDetails = detail
        ? { ...state.dealDetails, [dealId]: { ...detail, stage: data.to_stage } }
        : state.dealDetails;
      const updatedByLead = Object.fromEntries(
        Object.entries(state.dealsByLeadId).map(([leadId, deals]) => [
          leadId,
          deals.map((d) => (d.id === dealId ? { ...d, stage: data.to_stage } : d)),
        ]),
      );
      return { dealDetails: updatedDetails, dealsByLeadId: updatedByLead };
    });

    try {
      const deal = await dealsApi.transition(dealId, data);
      get().updateDealInStore(deal);
      return deal;
    } catch (err) {
      // Revert optimistic update
      set({ dealDetails: prevDetails, dealsByLeadId: prevByLead });
      const message = err instanceof Error ? err.message : 'Failed to transition deal';
      set({ error: message });
      throw err;
    }
  },

  cancelDeal: async (dealId, data) => {
    set({ loading: true, error: null });
    try {
      const deal = await dealsApi.cancel(dealId, data);
      get().updateDealInStore(deal);
      set({ loading: false });
      return deal;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to cancel deal';
      set({ error: message, loading: false });
      throw err;
    }
  },

  submitBankReview: async (dealId, data) => {
    set({ loading: true, error: null });
    try {
      const deal = await dealsApi.bankReview(dealId, data);
      get().updateDealInStore(deal);
      set({ loading: false });
      return deal;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to submit bank review';
      set({ error: message, loading: false });
      throw err;
    }
  },

  submitJefaturaReview: async (dealId, data) => {
    set({ loading: true, error: null });
    try {
      const deal = await dealsApi.jefaturaReview(dealId, data);
      get().updateDealInStore(deal);
      set({ loading: false });
      return deal;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to submit jefatura review';
      set({ error: message, loading: false });
      throw err;
    }
  },

  uploadDocument: async (dealId, slot, file, slotIndex) => {
    set({ loading: true, error: null });
    try {
      const doc = await dealsApi.uploadDocument(dealId, slot, file, slotIndex);
      // Reload detail to get fresh required_slots counts
      await get().loadDealDetail(dealId);
      set({ loading: false });
      return doc;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to upload document';
      set({ error: message, loading: false });
      throw err;
    }
  },

  approveDocument: async (dealId, docId, notes) => {
    set({ loading: true, error: null });
    try {
      const doc = await dealsApi.approveDocument(dealId, docId, notes);
      get().updateDocumentInStore(dealId, doc);
      set({ loading: false });
      return doc;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to approve document';
      set({ error: message, loading: false });
      throw err;
    }
  },

  rejectDocument: async (dealId, docId, notes) => {
    set({ loading: true, error: null });
    try {
      const doc = await dealsApi.rejectDocument(dealId, docId, notes);
      get().updateDocumentInStore(dealId, doc);
      set({ loading: false });
      return doc;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to reject document';
      set({ error: message, loading: false });
      throw err;
    }
  },

  deleteDocument: async (dealId, docId) => {
    set({ loading: true, error: null });
    try {
      await dealsApi.deleteDocument(dealId, docId);
      get().removeDocumentFromStore(dealId, docId);
      set({ loading: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete document';
      set({ error: message, loading: false });
      throw err;
    }
  },

  updateDealInStore: (deal) => {
    set((state) => {
      const updatedDetails = state.dealDetails[deal.id]
        ? { ...state.dealDetails, [deal.id]: { ...state.dealDetails[deal.id], ...deal } }
        : state.dealDetails;
      const updatedByLead = state.dealsByLeadId[deal.lead_id]
        ? {
            ...state.dealsByLeadId,
            [deal.lead_id]: state.dealsByLeadId[deal.lead_id].map((d) =>
              d.id === deal.id ? deal : d,
            ),
          }
        : state.dealsByLeadId;
      return { dealDetails: updatedDetails, dealsByLeadId: updatedByLead };
    });
  },

  updateDocumentInStore: (dealId, doc) => {
    set((state) => {
      const detail = state.dealDetails[dealId];
      if (!detail) return state;
      return {
        dealDetails: {
          ...state.dealDetails,
          [dealId]: {
            ...detail,
            documents: detail.documents.map((d) => (d.id === doc.id ? doc : d)),
          },
        },
      };
    });
  },

  removeDocumentFromStore: (dealId, docId) => {
    set((state) => {
      const detail = state.dealDetails[dealId];
      if (!detail) return state;
      return {
        dealDetails: {
          ...state.dealDetails,
          [dealId]: {
            ...detail,
            documents: detail.documents.filter((d) => d.id !== docId),
          },
        },
      };
    });
  },

  onDealStageChanged: (payload) => {
    const { deal_id, lead_id, to_stage } = payload;
    const state = get();
    const isKnown =
      state.dealDetails[deal_id] !== undefined ||
      (state.dealsByLeadId[lead_id]?.some((d) => d.id === deal_id) ?? false);

    if (isKnown) {
      // Optimistically update stage, then reload full detail
      set((s) => {
        const detail = s.dealDetails[deal_id];
        const updatedDetails = detail
          ? { ...s.dealDetails, [deal_id]: { ...detail, stage: to_stage as Deal['stage'] } }
          : s.dealDetails;
        const updatedByLead = s.dealsByLeadId[lead_id]
          ? {
              ...s.dealsByLeadId,
              [lead_id]: s.dealsByLeadId[lead_id].map((d) =>
                d.id === deal_id ? { ...d, stage: to_stage as Deal['stage'] } : d,
              ),
            }
          : s.dealsByLeadId;
        return { dealDetails: updatedDetails, dealsByLeadId: updatedByLead };
      });
      get().loadDealDetail(deal_id).catch(() => {});
    }
  },
}));
