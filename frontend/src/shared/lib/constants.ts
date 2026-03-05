export const PIPELINE_STAGES = [
  { key: 'entrada', label: 'Entrada' },
  { key: 'perfilamiento', label: 'Perfilamiento' },
  { key: 'calificacion_financiera', label: 'Calificación Financiera' },
  { key: 'agendado', label: 'Agendado' },
  { key: 'seguimiento', label: 'Seguimiento' },
  { key: 'referidos', label: 'Referidos' },
  { key: 'ganado', label: 'Ganado' },
  { key: 'perdido', label: 'Perdido' },
] as const

export const LEAD_STATUS_CONFIG = {
  cold: { label: 'Frío', className: 'bg-slate-100 text-slate-600 border-slate-200' },
  warm: { label: 'Tibio', className: 'bg-amber-100 text-amber-700 border-amber-200' },
  hot: { label: 'Caliente', className: 'bg-rose-100 text-rose-600 border-rose-200' },
  converted: { label: 'Convertido', className: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
  lost: { label: 'Perdido', className: 'bg-slate-200 text-slate-700 border-slate-300' },
} as const

export const CALIFICACION_CONFIG = {
  CALIFICADO: { label: 'Calificado', className: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
  POTENCIAL: { label: 'Potencial', className: 'bg-amber-100 text-amber-700 border-amber-200' },
  NO_CALIFICADO: { label: 'No Calificado', className: 'bg-rose-100 text-rose-600 border-rose-200' },
} as const

export const PIPELINE_STAGE_CONFIG = {
  entrada: { label: 'Entrada', color: 'bg-slate-100 text-slate-700 border-slate-200' },
  perfilamiento: { label: 'Perfilamiento', color: 'bg-blue-100 text-blue-700 border-blue-200' },
  calificacion_financiera: { label: 'Cal. Financiera', color: 'bg-violet-100 text-violet-700 border-violet-200' },
  agendado: { label: 'Agendado', color: 'bg-indigo-100 text-indigo-700 border-indigo-200' },
  seguimiento: { label: 'Seguimiento', color: 'bg-amber-100 text-amber-700 border-amber-200' },
  referidos: { label: 'Referidos', color: 'bg-cyan-100 text-cyan-700 border-cyan-200' },
  ganado: { label: 'Ganado', color: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
  perdido: { label: 'Perdido', color: 'bg-rose-100 text-rose-600 border-rose-200' },
} as const

export const APPOINTMENT_STATUS_CONFIG = {
  scheduled: { label: 'Programada', className: 'bg-blue-100 text-blue-700 border-blue-200' },
  confirmed: { label: 'Confirmada', className: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
  cancelled: { label: 'Cancelada', className: 'bg-rose-100 text-rose-600 border-rose-200' },
  completed: { label: 'Completada', className: 'bg-slate-100 text-slate-600 border-slate-200' },
  no_show: { label: 'No Asistió', className: 'bg-amber-100 text-amber-700 border-amber-200' },
} as const

export const DICOM_CONFIG = {
  clean: { label: 'Limpio', className: 'text-emerald-600' },
  has_debt: { label: 'Con Deuda', className: 'text-rose-600' },
  unknown: { label: 'Desconocido', className: 'text-slate-500' },
} as const

export const SCORE_THRESHOLDS = {
  cold: 30,
  warm: 60,
  hot: 80,
} as const

export const CHANNEL_LABELS: Record<string, string> = {
  telegram: 'Telegram',
  whatsapp: 'WhatsApp',
  call: 'Llamada',
  email: 'Email',
}

export const AGENT_TYPE_LABELS: Record<string, string> = {
  qualifier: 'Calificador',
  scheduler: 'Agendador',
  follow_up: 'Seguimiento',
}
