import { useState, useEffect } from 'react'
import { Save, Eye, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import { Textarea } from '@/shared/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { LoadingSpinner } from '@/shared/components/common/LoadingSpinner'
import { getErrorMessage } from '@/shared/types/api'
import { settingsService, type BrokerConfig } from '../services/settings.service'

export function SettingsPage() {
  const [config, setConfig] = useState<BrokerConfig | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)
  const [isLoadingPreview, setIsLoadingPreview] = useState(false)

  // Agent form state
  const [agentName, setAgentName] = useState('')
  const [agentIdentity, setAgentIdentity] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        const data = await settingsService.getConfig()
        setConfig(data)
        setAgentName(data.agent_name ?? '')
        setAgentIdentity(data.agent_identity ?? '')
        setSystemPrompt(data.system_prompt ?? '')
      } catch (error) {
        toast.error(getErrorMessage(error))
      } finally {
        setIsLoading(false)
      }
    }
    load()
  }, [])

  const handleSavePrompt = async () => {
    setIsSaving(true)
    try {
      await settingsService.updatePromptConfig({
        agent_name: agentName,
        agent_identity: agentIdentity,
        system_prompt: systemPrompt,
      })
      toast.success('Configuración del agente guardada')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsSaving(false)
    }
  }

  const handleLoadPreview = async () => {
    setIsLoadingPreview(true)
    try {
      const data = await settingsService.getPromptPreview()
      setPreview(data.system_prompt)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoadingPreview(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="p-8 space-y-6 max-w-4xl">
      <PageHeader
        title="Configuración"
        description="Personaliza el agente IA y las reglas del sistema"
      />

      <Tabs defaultValue="agent">
        <TabsList>
          <TabsTrigger value="agent">Agente IA</TabsTrigger>
          <TabsTrigger value="scoring">Scoring</TabsTrigger>
          <TabsTrigger value="preview">Preview Prompt</TabsTrigger>
        </TabsList>

        {/* Agent config tab */}
        <TabsContent value="agent" className="mt-4 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Identidad del Agente</CardTitle>
              <CardDescription>Define cómo se presenta Sofía ante los leads</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Nombre del agente</Label>
                  <Input
                    value={agentName}
                    onChange={(e) => setAgentName(e.target.value)}
                    placeholder="Sofía"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Identidad</Label>
                  <Input
                    value={agentIdentity}
                    onChange={(e) => setAgentIdentity(e.target.value)}
                    placeholder="Asesora inmobiliaria"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>System Prompt personalizado</Label>
                <Textarea
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  rows={10}
                  className="font-mono text-xs"
                  placeholder="Instrucciones específicas para el agente..."
                />
                <p className="text-xs text-muted-foreground">
                  Este prompt se inyecta en el contexto del agente IA junto con las instrucciones base del sistema.
                </p>
              </div>
              <div className="flex justify-end">
                <Button onClick={handleSavePrompt} disabled={isSaving}>
                  {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                  Guardar configuración
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Scoring tab */}
        <TabsContent value="scoring" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Umbrales de Scoring</CardTitle>
              <CardDescription>Define los umbrales de clasificación de leads</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                {(['cold', 'warm', 'hot'] as const).map((level) => {
                  const labels = { cold: 'Frío (hasta)', warm: 'Tibio (hasta)', hot: 'Caliente (desde)' }
                  const thresholds = config?.score_thresholds ?? { cold: 30, warm: 60, hot: 80 }
                  return (
                    <div key={level} className="space-y-2">
                      <Label>{labels[level]}</Label>
                      <Input
                        type="number"
                        min={0}
                        max={100}
                        defaultValue={thresholds[level]}
                        className="text-center"
                      />
                    </div>
                  )
                })}
              </div>
              <p className="text-xs text-muted-foreground">
                Score 0–{config?.score_thresholds?.cold ?? 30}: Frío · {config?.score_thresholds?.cold ?? 30}–{config?.score_thresholds?.warm ?? 60}: Tibio · {config?.score_thresholds?.warm ?? 60}+: Caliente
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Preview tab */}
        <TabsContent value="preview" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Preview del System Prompt</CardTitle>
              <CardDescription>Visualiza el prompt completo compilado que recibe el agente</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button variant="outline" onClick={handleLoadPreview} disabled={isLoadingPreview}>
                {isLoadingPreview ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Eye className="mr-2 h-4 w-4" />
                )}
                Cargar preview
              </Button>
              {preview && (
                <pre className="text-xs bg-muted rounded-lg p-4 overflow-auto max-h-[500px] whitespace-pre-wrap font-mono">
                  {preview}
                </pre>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
