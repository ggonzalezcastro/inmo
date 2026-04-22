/**
 * Subscribe to deal-related WebSocket events for the current broker.
 * Call once in a top-level component (e.g. AppShell) — not per-page.
 */
import { useCallback } from 'react'
import { useWebSocketEvent, type WSEvent } from '@/shared/context/WebSocketContext'
import { useDealsStore } from '../store/dealsStore'
import { usePropertiesStore } from '@/features/properties/store/propertiesStore'
import type { PropertyStatus } from '@/features/properties/types'

interface DealStageChangedPayload {
  deal_id: number
  lead_id: number
  property_id: number
  from_stage: string
  to_stage: string
}

interface DealDocumentChangedPayload {
  deal_id: number
  doc_id: number
  slot: string
  status: string
}

interface PropertyStatusChangedPayload {
  property_id: number
  status: string
  deal_id: number
}

export function useDealsLive(brokerId: number | undefined) {
  const { onDealStageChanged, updateDocumentInStore, loadDealDetail } = useDealsStore()

  const handleEvent = useCallback(
    (event: WSEvent) => {
      if (event.type === 'deal_stage_changed') {
        const payload = event.data as DealStageChangedPayload
        onDealStageChanged({
          deal_id: payload.deal_id,
          lead_id: payload.lead_id,
          to_stage: payload.to_stage,
        })
      }

      if (event.type === 'deal_document_changed') {
        const payload = event.data as DealDocumentChangedPayload
        // Reload the full deal detail to get the updated document state
        loadDealDetail(payload.deal_id).catch(() => {})
      }

      if (event.type === 'property_status_changed') {
        const payload = event.data as PropertyStatusChangedPayload
        usePropertiesStore.getState().updateProperty(payload.property_id, {
          status: payload.status as PropertyStatus,
        })
      }
    },
    [onDealStageChanged, updateDocumentInStore, loadDealDetail],
  )

  useWebSocketEvent(handleEvent, !!brokerId)
}
