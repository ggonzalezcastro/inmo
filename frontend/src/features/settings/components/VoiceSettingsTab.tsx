/**
 * VoiceSettingsTab — voice configuration inside SettingsPage.
 *
 * Agent view:  voice profile (voice/tone selector, assistant name, opening message).
 * Admin view:  all of the above + template management + assign template to agents.
 */
import { useState, useEffect } from 'react'
import { Loader2, Save, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import { Textarea } from '@/shared/components/ui/textarea'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/shared/components/ui/select'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/shared/components/ui/dialog'
import { Badge } from '@/shared/components/ui/badge'
import { getErrorMessage } from '@/shared/types/api'
import { voiceService } from '@/features/voice/services/voice.service'
import type { AgentVoiceProfile, AgentVoiceTemplate, VapiVoice, CallMode } from '@/features/voice/types'

// ── Design tokens (match SettingsPage) ────────────────────────────────────────
const blue   = '#1A56DB'
const blueLt = '#EBF2FF'
const border = '#D1D9E6'

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-sm font-bold uppercase tracking-wide mb-3" style={{ color: blue }}>
      {children}
    </h3>
  )
}

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5 sm:flex-row sm:items-start">
      <Label className="sm:w-40 sm:pt-2 text-sm text-[#374151] shrink-0">{label}</Label>
      <div className="flex-1">{children}</div>
    </div>
  )
}

// ── Agent profile section ─────────────────────────────────────────────────────

function AgentProfileSection() {
  const [profile, setProfile] = useState<AgentVoiceProfile | null>(null)
  const [availableVoices, setAvailableVoices] = useState<string[]>([])
  const [availableTones, setAvailableTones] = useState<string[]>([])
  const [voices, setVoices] = useState<VapiVoice[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    selected_voice_id: '',
    selected_tone: '',
    assistant_name: '',
    opening_message: '',
    preferred_call_mode: '' as CallMode | '',
  })

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const p = await voiceService.getMyProfile()
        setProfile(p)
        setForm({
          selected_voice_id: p.selected_voice_id ?? '',
          selected_tone: p.selected_tone ?? '',
          assistant_name: p.assistant_name ?? '',
          opening_message: p.opening_message ?? '',
          preferred_call_mode: (p.preferred_call_mode as CallMode) ?? '',
        })
        const [vRes, tRes] = await Promise.all([
          voiceService.getAvailableVoices(p.template_id),
          voiceService.getAvailableTones(p.template_id),
        ])
        setAvailableVoices(vRes.voice_ids)
        setAvailableTones(tRes.tones)

        // Load VAPI catalog for display names
        try {
          const catalog = await voiceService.getVoiceCatalog()
          setVoices(catalog.voices)
        } catch {
          // catalog fetch failing shouldn't block the form
        }
      } catch {
        // no profile configured yet
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await voiceService.updateMyProfile({
        selected_voice_id: form.selected_voice_id || undefined,
        selected_tone: form.selected_tone || undefined,
        assistant_name: form.assistant_name || undefined,
        opening_message: form.opening_message || undefined,
        preferred_call_mode: form.preferred_call_mode || undefined,
      } as Partial<AgentVoiceProfile>)
      toast.success('Perfil de voz guardado')
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>

  if (!profile) {
    return (
      <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
        Sin perfil de voz configurado. Pide a tu administrador que te asigne una plantilla.
      </div>
    )
  }

  const voiceLabel = (id: string) => voices.find((v) => v.id === id)?.name ?? id

  return (
    <div className="space-y-4">
      <FieldRow label="Voz">
        {availableVoices.length > 0 ? (
          <Select
            value={form.selected_voice_id}
            onValueChange={(v) => setForm((f) => ({ ...f, selected_voice_id: v }))}
          >
            <SelectTrigger><SelectValue placeholder="Seleccionar voz…" /></SelectTrigger>
            <SelectContent>
              {availableVoices.map((id) => (
                <SelectItem key={id} value={id}>{voiceLabel(id)}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <p className="text-sm text-muted-foreground pt-2">Sin voces disponibles en la plantilla</p>
        )}
      </FieldRow>

      <FieldRow label="Tono">
        {availableTones.length > 0 ? (
          <Select
            value={form.selected_tone}
            onValueChange={(v) => setForm((f) => ({ ...f, selected_tone: v }))}
          >
            <SelectTrigger><SelectValue placeholder="Seleccionar tono…" /></SelectTrigger>
            <SelectContent>
              {availableTones.map((t) => (
                <SelectItem key={t} value={t} className="capitalize">{t}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <p className="text-sm text-muted-foreground pt-2">Sin tonos disponibles</p>
        )}
      </FieldRow>

      <FieldRow label="Nombre del asistente">
        <Input
          value={form.assistant_name}
          onChange={(e) => setForm((f) => ({ ...f, assistant_name: e.target.value }))}
          placeholder="Ej: Sofía"
          maxLength={100}
        />
      </FieldRow>

      <FieldRow label="Mensaje de apertura">
        <Textarea
          value={form.opening_message}
          onChange={(e) => setForm((f) => ({ ...f, opening_message: e.target.value }))}
          placeholder="Hola, te llamo de…"
          rows={3}
        />
      </FieldRow>

      <FieldRow label="Modo preferido">
        <Select
          value={form.preferred_call_mode}
          onValueChange={(v) => setForm((f) => ({ ...f, preferred_call_mode: v as CallMode }))}
        >
          <SelectTrigger><SelectValue placeholder="Usar plantilla por defecto" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="">Plantilla por defecto</SelectItem>
            <SelectItem value="transcriptor">Transcriptor</SelectItem>
            <SelectItem value="ai_agent">Agente IA</SelectItem>
          </SelectContent>
        </Select>
      </FieldRow>

      <div className="flex justify-end pt-2">
        <Button onClick={handleSave} disabled={saving} style={{ background: blue }}>
          {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
          Guardar
        </Button>
      </div>
    </div>
  )
}

// ── Template management (admin only) ─────────────────────────────────────────

function blankTemplate(): Partial<AgentVoiceTemplate> {
  return {
    name: '',
    business_prompt: '',
    niche_instructions: '',
    language: 'es',
    max_duration_seconds: 600,
    max_silence_seconds: 30,
    recording_policy: 'enabled',
    available_voice_ids: [],
    available_tones: [],
    default_call_mode: 'transcriptor',
    is_active: true,
  }
}

function TemplateDialog({
  open,
  template,
  onClose,
  onSaved,
}: {
  open: boolean
  template: Partial<AgentVoiceTemplate> | null
  onClose: () => void
  onSaved: (t: AgentVoiceTemplate) => void
}) {
  const isEdit = !!template?.id
  const [form, setForm] = useState<Partial<AgentVoiceTemplate>>(template ?? blankTemplate())
  const [saving, setSaving] = useState(false)
  const [voicesInput, setVoicesInput] = useState((template?.available_voice_ids ?? []).join(', '))
  const [tonesInput, setTonesInput] = useState((template?.available_tones ?? []).join(', '))

  useEffect(() => {
    if (open) {
      setForm(template ?? blankTemplate())
      setVoicesInput((template?.available_voice_ids ?? []).join(', '))
      setTonesInput((template?.available_tones ?? []).join(', '))
    }
  }, [open, template])

  const handleSave = async () => {
    if (!form.name?.trim()) { toast.error('El nombre es obligatorio'); return }
    setSaving(true)
    try {
      const payload = {
        ...form,
        available_voice_ids: voicesInput.split(',').map((s) => s.trim()).filter(Boolean),
        available_tones: tonesInput.split(',').map((s) => s.trim()).filter(Boolean),
      }
      const saved = isEdit
        ? await voiceService.updateTemplate(template!.id!, payload)
        : await voiceService.createTemplate(payload)
      toast.success(isEdit ? 'Plantilla actualizada' : 'Plantilla creada')
      onSaved(saved)
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Editar plantilla' : 'Nueva plantilla'}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <Label>Nombre *</Label>
            <Input value={form.name ?? ''} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          </div>
          <div>
            <Label>Prompt base del negocio</Label>
            <Textarea
              value={form.business_prompt ?? ''}
              onChange={(e) => setForm((f) => ({ ...f, business_prompt: e.target.value }))}
              rows={4}
              placeholder="Eres un asesor inmobiliario de…"
            />
          </div>
          <div>
            <Label>Instrucciones de nicho</Label>
            <Textarea
              value={form.niche_instructions ?? ''}
              onChange={(e) => setForm((f) => ({ ...f, niche_instructions: e.target.value }))}
              rows={2}
              placeholder="Enfocado en departamentos en Santiago centro…"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Duración máx (seg)</Label>
              <Input
                type="number"
                value={form.max_duration_seconds ?? 600}
                onChange={(e) => setForm((f) => ({ ...f, max_duration_seconds: Number(e.target.value) }))}
              />
            </div>
            <div>
              <Label>Silencio máx (seg)</Label>
              <Input
                type="number"
                value={form.max_silence_seconds ?? 30}
                onChange={(e) => setForm((f) => ({ ...f, max_silence_seconds: Number(e.target.value) }))}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Modo por defecto</Label>
              <Select
                value={form.default_call_mode ?? 'transcriptor'}
                onValueChange={(v) => setForm((f) => ({ ...f, default_call_mode: v as CallMode }))}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="transcriptor">Transcriptor</SelectItem>
                  <SelectItem value="ai_agent">Agente IA</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Grabación</Label>
              <Select
                value={form.recording_policy ?? 'enabled'}
                onValueChange={(v) => setForm((f) => ({ ...f, recording_policy: v as AgentVoiceTemplate['recording_policy'] }))}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="enabled">Habilitada</SelectItem>
                  <SelectItem value="optional">Opcional</SelectItem>
                  <SelectItem value="disabled">Deshabilitada</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <Label>IDs de voz disponibles <span className="text-muted-foreground font-normal">(separados por coma)</span></Label>
            <Input
              value={voicesInput}
              onChange={(e) => setVoicesInput(e.target.value)}
              placeholder="es-MX-DaliaNeural, es-ES-ElviraNeural"
            />
          </div>
          <div>
            <Label>Tonos disponibles <span className="text-muted-foreground font-normal">(separados por coma)</span></Label>
            <Input
              value={tonesInput}
              onChange={(e) => setTonesInput(e.target.value)}
              placeholder="formal, amigable, directo"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button onClick={handleSave} disabled={saving} style={{ background: blue }}>
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            {isEdit ? 'Guardar cambios' : 'Crear plantilla'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function TemplateManagement() {
  const [templates, setTemplates] = useState<AgentVoiceTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<Partial<AgentVoiceTemplate> | null>(null)

  useEffect(() => {
    voiceService.listTemplates()
      .then(setTemplates)
      .catch(() => toast.error('Error cargando plantillas'))
      .finally(() => setLoading(false))
  }, [])

  const handleSaved = (t: AgentVoiceTemplate) => {
    setTemplates((prev) => {
      const idx = prev.findIndex((x) => x.id === t.id)
      if (idx >= 0) { const n = [...prev]; n[idx] = t; return n }
      return [...prev, t]
    })
    setDialogOpen(false)
  }

  const handleDelete = async (t: AgentVoiceTemplate) => {
    if (!confirm(`¿Eliminar plantilla "${t.name}"?`)) return
    try {
      await voiceService.deleteTemplate(t.id)
      setTemplates((prev) => prev.filter((x) => x.id !== t.id))
      toast.success('Plantilla eliminada')
    } catch (err) {
      toast.error(getErrorMessage(err))
    }
  }

  if (loading) return <div className="flex justify-center py-6"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <SectionLabel>Plantillas de voz</SectionLabel>
        <Button
          size="sm"
          onClick={() => { setEditing(null); setDialogOpen(true) }}
          style={{ background: blue }}
        >
          <Plus className="mr-1 h-3.5 w-3.5" /> Nueva
        </Button>
      </div>

      {templates.length === 0 ? (
        <div
          className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground"
          style={{ borderColor: border }}
        >
          Sin plantillas. Crea una para asignar a agentes.
        </div>
      ) : (
        <div className="space-y-2">
          {templates.map((t) => (
            <div
              key={t.id}
              className="flex items-center justify-between rounded-lg border p-3"
              style={{ borderColor: border, background: blueLt }}
            >
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">{t.name}</p>
                <div className="flex gap-1 mt-0.5 flex-wrap">
                  <Badge variant="outline" className="text-xs py-0">{t.default_call_mode}</Badge>
                  <Badge variant="outline" className="text-xs py-0">{t.language}</Badge>
                  {!t.is_active && <Badge variant="destructive" className="text-xs py-0">Inactiva</Badge>}
                </div>
              </div>
              <div className="flex gap-1 shrink-0 ml-2">
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-7 w-7"
                  onClick={() => { setEditing(t); setDialogOpen(true) }}
                >
                  <Save className="h-3.5 w-3.5" />
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-7 w-7 text-destructive hover:text-destructive"
                  onClick={() => handleDelete(t)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <TemplateDialog
        open={dialogOpen}
        template={editing}
        onClose={() => setDialogOpen(false)}
        onSaved={handleSaved}
      />
    </div>
  )
}

// ── Main export ────────────────────────────────────────────────────────────────

interface VoiceSettingsTabProps {
  isAdmin: boolean
}

export function VoiceSettingsTab({ isAdmin }: VoiceSettingsTabProps) {
  return (
    <div className="space-y-10">
      <div>
        <SectionLabel>Mi perfil de voz</SectionLabel>
        <p className="text-sm text-[#6B7280] mb-5">
          Personaliza la voz, tono y mensaje de apertura para tus llamadas.
        </p>
        <AgentProfileSection />
      </div>

      {isAdmin && (
        <div>
          <p className="text-sm text-[#6B7280] mb-5">
            Define las opciones de voz y tono que los agentes pueden elegir.
          </p>
          <TemplateManagement />
        </div>
      )}
    </div>
  )
}
