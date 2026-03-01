import { useState, useEffect } from 'react'
import { Loader2, Info } from 'lucide-react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/shared/components/ui/dialog'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import { Textarea } from '@/shared/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import { CHANNEL_LABELS, AGENT_TYPE_LABELS } from '@/shared/lib/constants'
import { getErrorMessage } from '@/shared/types/api'
import { templatesService, type Template } from '../services/templates.service'

const VARIABLES_HINT = '{{name}}, {{phone}}, {{budget}}, {{location}}, {{property_type}}'

interface TemplateEditorDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  template?: Template | null
  onSuccess: (t: Template) => void
}

export function TemplateEditorDialog({
  open,
  onOpenChange,
  template,
  onSuccess,
}: TemplateEditorDialogProps) {
  const [name, setName] = useState('')
  const [content, setContent] = useState('')
  const [channel, setChannel] = useState('telegram')
  const [agentType, setAgentType] = useState('qualifier')
  const [isLoading, setIsLoading] = useState(false)
  const isEditing = !!template

  useEffect(() => {
    if (template) {
      setName(template.name)
      setContent(template.content)
      setChannel(template.channel)
      setAgentType(template.agent_type)
    } else {
      setName('')
      setContent('')
      setChannel('telegram')
      setAgentType('qualifier')
    }
  }, [template, open])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    try {
      const data = { name, content, channel, agent_type: agentType }
      const result = isEditing
        ? await templatesService.update(template.id, data)
        : await templatesService.create(data)
      toast.success(isEditing ? 'Template actualizado' : 'Template creado')
      onSuccess(result)
      onOpenChange(false)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Editar Template' : 'Nuevo Template'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label>Nombre</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Ej: Bienvenida inicial" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Canal</Label>
              <Select value={channel} onValueChange={setChannel}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(CHANNEL_LABELS).map(([k, v]) => (
                    <SelectItem key={k} value={k}>{v}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Tipo de agente</Label>
              <Select value={agentType} onValueChange={setAgentType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(AGENT_TYPE_LABELS).map(([k, v]) => (
                    <SelectItem key={k} value={k}>{v}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label>Contenido</Label>
            <Textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              required
              rows={6}
              placeholder="Hola {{name}}, gracias por contactarnos..."
            />
            <div className="flex items-start gap-1.5 text-xs text-muted-foreground">
              <Info className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              <span>Variables disponibles: {VARIABLES_HINT}</span>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" type="button" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEditing ? 'Guardar' : 'Crear'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
