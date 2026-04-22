export type DealStage =
  | 'draft'
  | 'reserva'
  | 'docs_pendientes'
  | 'en_aprobacion_bancaria'
  | 'promesa_redaccion'
  | 'promesa_firmada'
  | 'escritura_firmada'
  | 'cancelado';

export type DeliveryType = 'inmediata' | 'futura' | 'desconocida';
export type DocumentStatus = 'pendiente' | 'recibido' | 'aprobado' | 'rechazado';

export interface Deal {
  id: number;
  broker_id: number;
  lead_id: number;
  property_id: number;
  created_by_user_id: number | null;
  stage: DealStage;
  // Denormalized display fields from API
  lead_name?: string | null;
  property_label?: string | null;
  delivery_type: DeliveryType;
  bank_review_status: string | null;
  jefatura_review_required: boolean;
  jefatura_review_status: string | null;
  jefatura_review_notes: string | null;
  reserva_at: string | null;
  docs_completos_at: string | null;
  bank_decision_at: string | null;
  promesa_signed_at: string | null;
  escritura_signed_at: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  cancellation_notes: string | null;
  escritura_planned_date: string | null;
  deal_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DealDocument {
  id: number;
  deal_id: number;
  slot: string;
  slot_index: number;
  co_titular_index: number;
  status: DocumentStatus;
  original_filename: string | null;
  mime_type: string | null;
  size_bytes: number | null;
  sha256: string | null;
  uploaded_by_user_id: number | null;
  uploaded_by_ai: boolean;
  uploaded_at: string | null;
  reviewed_by_user_id: number | null;
  reviewed_at: string | null;
  review_notes: string | null;
  created_at: string;
  download_url: string | null;
}

export interface SlotRequirement {
  slot_key: string;
  label: string;
  required_for_stage: string;
  max_count: number;
  supports_co_titular: boolean;
  optional: boolean;
  required: boolean;
  mime_whitelist: string[];
  uploaded_count: number;
  approved_count: number;
}

export interface DealDetail extends Deal {
  documents: DealDocument[];
  required_slots: SlotRequirement[];
}

export interface CreateDealRequest {
  lead_id: number;
  property_id: number;
  delivery_type: DeliveryType;
}

export interface TransitionDealRequest {
  to_stage: DealStage;
  notes?: string;
}

export interface CancelDealRequest {
  reason: string;
  notes?: string;
}

export interface ReviewRequest {
  decision: string;
  notes?: string;
}
