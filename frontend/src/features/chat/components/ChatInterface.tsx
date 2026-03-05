import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, RefreshCw, Loader2 } from 'lucide-react'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Badge } from '@/shared/components/ui/badge'
import { Progress } from '@/shared/components/ui/progress'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/shared/components/ui/tabs'
import { ScoreBadge } from '@/shared/components/common/ScoreBadge'
import { StatusBadge } from '@/shared/components/common/StatusBadge'
import { PipelineStageBadge } from '@/shared/components/common/PipelineStageBadge'
import {
  sendTestMessage,
  fetchLeadDebugData,
  emptyCapturedData,
  type CapturedData,
  type DebugInfo,
} from '../services/chat-test.service'

interface Message {
  type: 'user' | 'bot'
  text: string
}

const IMPORTANT_FIELDS: (keyof CapturedData)[] = [
  'name', 'phone', 'email', 'budget', 'location', 'monthly_income', 'dicom_status',
]

function FieldRow({
  label,
  value,
  format,
}: {
  label: string
  value: string | number | null
  format?: (v: string | number) => string
}) {
  const captured = value !== null && value !== undefined && value !== ''
  const displayValue = captured
    ? (format ? format(value!) : String(value))
    : 'Pendiente'
  return (
    <div className="flex items-start justify-between p-2 bg-accent/50 rounded-lg border border-border/50">
      <span className="text-muted-foreground text-sm font-medium shrink-0 mr-2">{label}</span>
      <span className={`text-right text-sm ${captured ? 'text-primary font-medium' : 'text-muted-foreground'}`}>
        {captured ? '✓' : '·'} {displayValue}
      </span>
    </div>
  )
}

function DicomBadge({ status }: { status: CapturedData['dicom_status'] }) {
  if (!status) return <span className="text-muted-foreground text-sm">· Pendiente</span>
  if (status === 'clean') return <Badge variant="outline" className="text-green-600 border-green-300">Limpio</Badge>
  if (status === 'has_debt') return <Badge variant="outline" className="text-red-600 border-red-300">Con Deuda</Badge>
  return <Badge variant="outline">Desconocido</Badge>
}

export function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [leadId, setLeadId] = useState<number | null>(null)
  const [leadScore, setLeadScore] = useState(0)
  const [leadStatus, setLeadStatus] = useState('cold')
  const [capturedData, setCapturedData] = useState<CapturedData>(emptyCapturedData)
  const [debugInfo, setDebugInfo] = useState<DebugInfo | null>(null)
  const [activeTab, setActiveTab] = useState('datos')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const refreshCaptured = async (id: number) => {
    try {
      const { capturedData: data } = await fetchLeadDebugData(id)
      setCapturedData(data)
    } catch {
      // non-critical
    }
  }

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    const text = inputMessage.trim()
    if (!text || loading) return

    setInputMessage('')
    setMessages(prev => [...prev, { type: 'user', text }])
    setLoading(true)

    try {
      const res = await sendTestMessage(text, leadId)
      const newLeadId = leadId ?? res.lead_id

      if (!leadId && res.lead_id) {
        setLeadId(res.lead_id)
        window.dispatchEvent(new CustomEvent('leadCreated'))
      }

      if (res.lead_score !== undefined) setLeadScore(res.lead_score)
      if (res.lead_status) setLeadStatus(res.lead_status)
      if (res.debug_info) setDebugInfo(res.debug_info)

      setMessages(prev => [...prev, { type: 'bot', text: res.response }])

      setTimeout(() => refreshCaptured(newLeadId), 800)
    } catch {
      setMessages(prev => [
        ...prev,
        { type: 'bot', text: 'Lo siento, hubo un error procesando tu mensaje. Por favor intenta de nuevo.' },
      ])
    } finally {
      setLoading(false)
    }
  }

  const capturedCount = IMPORTANT_FIELDS.filter(f => {
    const v = capturedData[f]
    return v !== null && v !== undefined && v !== ''
  }).length
  const capturePercent = Math.round((capturedCount / IMPORTANT_FIELDS.length) * 100)

  const promptContextItems = [
    { label: 'Nombre', value: capturedData.name },
    { label: 'Teléfono', value: capturedData.phone },
    { label: 'Email', value: capturedData.email },
    { label: 'Presupuesto', value: capturedData.budget },
    { label: 'Ubicación', value: capturedData.location },
    { label: 'Timeline', value: capturedData.timeline },
    { label: 'Tipo de Propiedad', value: capturedData.property_type },
    { label: 'Habitaciones', value: capturedData.rooms },
    {
      label: 'Salario',
      value: capturedData.monthly_income
        ? `$${Number(capturedData.monthly_income).toLocaleString('es-CL')}`
        : null,
    },
    {
      label: 'DICOM',
      value:
        capturedData.dicom_status === 'clean'
          ? 'Limpio'
          : capturedData.dicom_status === 'has_debt'
          ? 'Con Deuda'
          : capturedData.dicom_status === 'unknown'
          ? 'Desconocido'
          : null,
    },
  ]

  const lastAnalysis = debugInfo?.last_analysis

  return (
    <div className="flex h-full bg-background rounded-xl border border-border overflow-hidden">
      {/* Chat column */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-primary text-primary-foreground px-4 py-3 flex-shrink-0">
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5" />
            <span className="font-semibold">Chat de Prueba — Sofía</span>
          </div>
          {leadId && (
            <div className="mt-2 flex items-center gap-2 flex-wrap">
              <Badge variant="secondary" className="text-xs">#{leadId}</Badge>
              <ScoreBadge score={leadScore} />
              <StatusBadge status={leadStatus as 'cold' | 'warm' | 'hot' | 'converted' | 'lost'} />
            </div>
          )}
        </header>

        <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-muted/30">
          {messages.length === 0 && (
            <div className="text-center text-muted-foreground mt-12 space-y-1">
              <Bot className="w-8 h-8 mx-auto opacity-40" />
              <p className="text-sm">Escribe un mensaje para comenzar la conversación.</p>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx} className={`flex items-end gap-2 ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.type === 'bot' && (
                <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mb-0.5">
                  <Bot className="w-4 h-4 text-primary" />
                </div>
              )}
              <div
                className={`max-w-xs lg:max-w-md px-4 py-2.5 text-sm ${
                  msg.type === 'user'
                    ? 'bg-primary text-primary-foreground rounded-2xl rounded-tr-sm'
                    : 'bg-card border border-border rounded-2xl rounded-tl-sm text-foreground'
                }`}
              >
                {msg.text}
              </div>
              {msg.type === 'user' && (
                <div className="w-7 h-7 rounded-full bg-muted flex items-center justify-center shrink-0 mb-0.5">
                  <User className="w-4 h-4 text-muted-foreground" />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex items-end gap-2 justify-start">
              <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-primary" />
              </div>
              <div className="bg-card border border-border rounded-2xl rounded-tl-sm px-4 py-3">
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <form onSubmit={sendMessage} className="p-3 border-t border-border bg-card flex gap-2 flex-shrink-0">
          <Input
            value={inputMessage}
            onChange={e => setInputMessage(e.target.value)}
            placeholder="Escribe tu mensaje..."
            className="bg-background"
            disabled={loading}
          />
          <Button type="submit" size="icon" disabled={loading || !inputMessage.trim()}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </Button>
        </form>
      </div>

      {/* Debug panel */}
      <div className="w-96 border-l border-border bg-card flex flex-col shrink-0">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between shrink-0">
          <span className="font-semibold text-sm text-foreground">Panel de Debug</span>
          {leadId && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => refreshCaptured(leadId)}
              title="Refrescar"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </Button>
          )}
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col overflow-hidden">
          <TabsList className="mx-3 mt-3 shrink-0">
            <TabsTrigger value="datos" className="flex-1 text-xs">Datos</TabsTrigger>
            <TabsTrigger value="contexto" className="flex-1 text-xs">Contexto IA</TabsTrigger>
            <TabsTrigger value="analisis" className="flex-1 text-xs">Análisis</TabsTrigger>
          </TabsList>

          {/* TAB: Datos capturados */}
          <TabsContent value="datos" className="flex-1 overflow-y-auto px-3 pb-3 mt-3 space-y-4">
            {!leadId ? (
              <div className="text-center text-muted-foreground py-10 text-sm">
                Inicia una conversación para capturar datos
              </div>
            ) : (
              <>
                <section>
                  <h5 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Datos Básicos</h5>
                  <div className="space-y-1.5">
                    <FieldRow label="Nombre" value={capturedData.name} />
                    <FieldRow label="Teléfono" value={capturedData.phone} />
                    <FieldRow label="Email" value={capturedData.email} />
                  </div>
                </section>

                <section>
                  <h5 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Datos Financieros</h5>
                  <div className="space-y-1.5">
                    <FieldRow
                      label="Renta Mensual"
                      value={capturedData.monthly_income}
                      format={v => `$${Number(v).toLocaleString('es-CL')}`}
                    />
                    <div className="flex items-center justify-between p-2 bg-accent/50 rounded-lg border border-border/50">
                      <span className="text-muted-foreground text-sm font-medium">DICOM</span>
                      <DicomBadge status={capturedData.dicom_status} />
                    </div>
                    {capturedData.morosidad_amount && (
                      <div className="flex items-center justify-between p-2 bg-destructive/5 rounded-lg border border-destructive/20">
                        <span className="text-muted-foreground text-sm font-medium">Monto Mora</span>
                        <span className="text-destructive text-sm font-medium">
                          ${Number(capturedData.morosidad_amount).toLocaleString('es-CL')}
                        </span>
                      </div>
                    )}
                  </div>
                </section>

                <section>
                  <h5 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Inmueble</h5>
                  <div className="space-y-1.5">
                    <FieldRow label="Presupuesto" value={capturedData.budget} />
                    <FieldRow label="Ubicación" value={capturedData.location} />
                    <FieldRow label="Timeline" value={capturedData.timeline} />
                    <FieldRow label="Tipo" value={capturedData.property_type} />
                    <FieldRow label="Habitaciones" value={capturedData.rooms} />
                  </div>
                </section>

                <section>
                  <h5 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Progreso de Captura</h5>
                  <div className="bg-accent/50 rounded-lg border border-border/50 p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground">{capturedCount} de {IMPORTANT_FIELDS.length} campos</span>
                      <span className="text-xs font-semibold text-primary">{capturePercent}%</span>
                    </div>
                    <Progress value={capturePercent} className="h-1.5" />
                    <p className="text-xs text-muted-foreground">Nombre · Teléfono · Email · Presupuesto · Ubicación · Renta · DICOM</p>
                  </div>
                </section>
              </>
            )}
          </TabsContent>

          {/* TAB: Contexto IA */}
          <TabsContent value="contexto" className="flex-1 overflow-y-auto px-3 pb-3 mt-3 space-y-4">
            {!debugInfo && !leadId ? (
              <div className="text-center text-muted-foreground py-10 text-sm">
                Envía un mensaje para ver el contexto del agente
              </div>
            ) : (
              <>
                <section className="space-y-2">
                  <h5 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Estado</h5>
                  <div className="flex flex-wrap gap-2">
                    {debugInfo?.conversation_state && (
                      <Badge variant="outline" className="text-xs font-mono">
                        {debugInfo.conversation_state}
                      </Badge>
                    )}
                    {debugInfo?.pipeline_stage && (
                      <PipelineStageBadge stage={debugInfo.pipeline_stage} size="sm" />
                    )}
                    {debugInfo?.human_mode && (
                      <Badge variant="destructive" className="text-xs">Modo Humano</Badge>
                    )}
                  </div>
                </section>

                {debugInfo?.conversation_summary && (
                  <section>
                    <h5 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Resumen</h5>
                    <div className="bg-accent/50 rounded-lg border border-border/50 p-3 text-sm text-foreground leading-relaxed">
                      {debugInfo.conversation_summary}
                    </div>
                  </section>
                )}

                {debugInfo?.key_points && debugInfo.key_points.length > 0 && (
                  <section>
                    <h5 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Key Points</h5>
                    <ul className="space-y-1">
                      {debugInfo.key_points.map((kp, i) => (
                        <li key={i} className="text-sm text-foreground flex gap-2">
                          <span className="text-primary shrink-0">•</span>
                          <span>{kp}</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}

                <section>
                  <h5 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Contexto del Prompt</h5>
                  <div className="space-y-1">
                    {promptContextItems.map(({ label, value }) => (
                      <div key={label} className="flex items-center justify-between text-xs py-1 border-b border-border/40 last:border-0">
                        <span className="text-muted-foreground">{label}</span>
                        {value ? (
                          <span className="text-primary font-medium">✅ {String(value)}</span>
                        ) : (
                          <span className="text-muted-foreground/60">⚠️ pendiente</span>
                        )}
                      </div>
                    ))}
                  </div>
                </section>
              </>
            )}
          </TabsContent>

          {/* TAB: Último Análisis */}
          <TabsContent value="analisis" className="flex-1 overflow-y-auto px-3 pb-3 mt-3 space-y-4">
            {!lastAnalysis ? (
              <div className="text-center text-muted-foreground py-10 text-sm">
                No hay análisis disponible aún
              </div>
            ) : (
              <>
                <section className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground font-medium">Calificación</span>
                    {lastAnalysis.qualified === 'yes' && (
                      <Badge className="bg-green-100 text-green-700 border-green-300">Calificado</Badge>
                    )}
                    {lastAnalysis.qualified === 'no' && (
                      <Badge className="bg-red-100 text-red-700 border-red-300">No calificado</Badge>
                    )}
                    {lastAnalysis.qualified === 'maybe' && (
                      <Badge className="bg-yellow-100 text-yellow-700 border-yellow-300">Potencial</Badge>
                    )}
                    {!lastAnalysis.qualified && <span className="text-xs text-muted-foreground">—</span>}
                  </div>

                  {lastAnalysis.interest_level !== undefined && (
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground font-medium">Nivel de Interés</span>
                        <span className="text-xs font-semibold text-primary">{lastAnalysis.interest_level}/10</span>
                      </div>
                      <Progress value={(lastAnalysis.interest_level / 10) * 100} className="h-2" />
                    </div>
                  )}

                  {lastAnalysis.score_delta !== undefined && (
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground font-medium">Cambio de Score</span>
                      <span className={`text-sm font-bold ${lastAnalysis.score_delta >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {lastAnalysis.score_delta >= 0 ? '+' : ''}{lastAnalysis.score_delta}
                      </span>
                    </div>
                  )}

                  {lastAnalysis.timeline && (
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground font-medium">Timeline</span>
                      <Badge variant="outline" className="text-xs">{lastAnalysis.timeline}</Badge>
                    </div>
                  )}

                  {lastAnalysis.dicom_status && (
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground font-medium">DICOM</span>
                      <DicomBadge status={lastAnalysis.dicom_status} />
                    </div>
                  )}
                </section>

                {lastAnalysis.key_points && lastAnalysis.key_points.length > 0 && (
                  <section>
                    <h5 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Key Points del Análisis</h5>
                    <ul className="space-y-1">
                      {lastAnalysis.key_points.map((kp, i) => (
                        <li key={i} className="text-sm text-foreground flex gap-2">
                          <span className="text-primary shrink-0">•</span>
                          <span>{kp}</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
              </>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
