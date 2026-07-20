/**
 * Shared Pipecat mode metadata + call-state badge config.
 * Used by VoiceTestPage and LlamadasPage.
 */
import { Radio, Eye, GitBranch, Lightbulb } from 'lucide-react'
import type { PipecatMode } from '../services/pipecat.service'

export interface PipecatModeInfo {
  value: PipecatMode
  label: string
  description: string
  icon: React.ComponentType<{ className?: string }>
  needsAgentPhone: boolean
}

export const MODES: PipecatModeInfo[] = [
  {
    value: 'autonomous',
    label: 'Autónomo',
    description: 'IA llama al lead y conduce la conversación completa',
    icon: Radio,
    needsAgentPhone: false,
  },
  {
    value: 'copilot',
    label: 'Copilot',
    description: 'Humano llama, IA transcribe y genera notas automáticas',
    icon: Eye,
    needsAgentPhone: true,
  },
  {
    value: 'handoff',
    label: 'Handoff',
    description: 'IA llama; si lead califica, transfiere al humano sin cortar',
    icon: GitBranch,
    needsAgentPhone: true,
  },
  {
    value: 'coaching',
    label: 'Coaching',
    description: 'Humano llama, IA sugiere en tiempo real al agente (el lead no escucha)',
    icon: Lightbulb,
    needsAgentPhone: true,
  },
]

export const STATE_BADGE: Record<
  string,
  { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }
> = {
  idle: { label: 'Sin llamada', variant: 'secondary' },
  starting: { label: 'Iniciando…', variant: 'outline' },
  ringing: { label: 'Llamando…', variant: 'outline' },
  active: { label: 'En curso', variant: 'default' },
  ending: { label: 'Finalizando…', variant: 'outline' },
  ended: { label: 'Finalizada', variant: 'secondary' },
  error: { label: 'Error', variant: 'destructive' },
}
