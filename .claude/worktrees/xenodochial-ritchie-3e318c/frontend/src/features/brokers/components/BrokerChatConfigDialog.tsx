import { useState, useEffect } from 'react'
import { Loader2, Copy, ExternalLink, CheckCircle2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import { Switch } from '@/shared/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/shared/components/ui/dialog'
import { getErrorMessage } from '@/shared/types/api'
import { chatConfigService, type ChatConfigResponse } from '../services/chatConfig.service'
import type { Broker } from '../services/brokers.service'

interface Props {
  broker: Broker | null
  onClose: () => void
}

function WebhookUrlDisplay({ url }: { url: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="flex items-center gap-2 mt-1">
      <code className="flex-1 text-xs bg-slate-100 border border-slate-200 rounded px-3 py-2 text-slate-600 truncate">
        {url}
      </code>
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 shrink-0"
        onClick={handleCopy}
        title="Copiar URL"
      >
        {copied ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-500" />
        ) : (
          <Copy className="h-4 w-4 text-slate-400" />
        )}
      </Button>
    </div>
  )
}

export function BrokerChatConfigDialog({ broker, onClose }: Props) {
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isRegistering, setIsRegistering] = useState(false)
  const [config, setConfig] = useState<ChatConfigResponse | null>(null)

  // WhatsApp state
  const [waEnabled, setWaEnabled] = useState(false)
  const [waPhoneNumberId, setWaPhoneNumberId] = useState('')
  const [waAccessToken, setWaAccessToken] = useState('')
  const [waAppSecret, setWaAppSecret] = useState('')

  // Telegram state
  const [tgEnabled, setTgEnabled] = useState(false)
  const [tgBotToken, setTgBotToken] = useState('')

  const open = broker !== null

  useEffect(() => {
    if (!broker) return

    setIsLoading(true)
    chatConfigService
      .get(broker.id)
      .then((cfg) => {
        setConfig(cfg)
        setWaEnabled(cfg.enabled_providers.includes('whatsapp'))
        setWaPhoneNumberId(cfg.provider_configs.whatsapp?.phone_number_id ?? '')
        setWaAccessToken(cfg.provider_configs.whatsapp?.access_token ?? '')
        setWaAppSecret(cfg.provider_configs.whatsapp?.app_secret ?? '')
        setTgEnabled(cfg.enabled_providers.includes('telegram'))
        setTgBotToken(cfg.provider_configs.telegram?.bot_token ?? '')
      })
      .catch((err) => toast.error(getErrorMessage(err)))
      .finally(() => setIsLoading(false))
  }, [broker])

  const handleSave = async () => {
    if (!broker) return
    setIsSaving(true)
    try {
      const enabledProviders: string[] = []
      if (waEnabled) enabledProviders.push('whatsapp')
      if (tgEnabled) enabledProviders.push('telegram')

      const updatedConfig = await chatConfigService.update(broker.id, {
        enabled_providers: enabledProviders,
        provider_configs: {
          whatsapp: {
            phone_number_id: waPhoneNumberId || undefined,
            access_token: waAccessToken || undefined,
            app_secret: waAppSecret || undefined,
          },
          telegram: {
            bot_token: tgBotToken || undefined,
          },
        },
      })

      setConfig(updatedConfig)
      // Refresh displayed values from server response (obfuscated)
      setWaPhoneNumberId(updatedConfig.provider_configs.whatsapp?.phone_number_id ?? '')
      setWaAccessToken(updatedConfig.provider_configs.whatsapp?.access_token ?? '')
      setWaAppSecret(updatedConfig.provider_configs.whatsapp?.app_secret ?? '')
      setTgBotToken(updatedConfig.provider_configs.telegram?.bot_token ?? '')

      toast.success('Configuración guardada')
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setIsSaving(false)
    }
  }

  const handleRegisterWebhook = async () => {
    if (!broker) return
    setIsRegistering(true)
    try {
      const result = await chatConfigService.registerWebhook(broker.id)
      toast.success(`Webhook registrado: ${result.webhook_url}`)
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setIsRegistering(false)
    }
  }

  const waWebhookUrl = config?.webhook_configs?.whatsapp?.url ?? ''
  const tgWebhookUrl = config?.webhook_configs?.telegram?.url ?? ''

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg flex flex-col max-h-[90vh]">
        <DialogHeader className="shrink-0">
          <DialogTitle>
            Canales de chat
            {broker && (
              <span className="ml-2 text-sm font-normal text-slate-500">— {broker.name}</span>
            )}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto min-h-0 px-1">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
          </div>
        ) : (
          <Tabs defaultValue="whatsapp" className="w-full">
            <TabsList className="w-full">
              <TabsTrigger value="whatsapp" className="flex-1">
                WhatsApp
                {waEnabled && (
                  <span className="ml-2 h-2 w-2 rounded-full bg-emerald-500 inline-block" />
                )}
              </TabsTrigger>
              <TabsTrigger value="telegram" className="flex-1">
                Telegram
                {tgEnabled && (
                  <span className="ml-2 h-2 w-2 rounded-full bg-emerald-500 inline-block" />
                )}
              </TabsTrigger>
            </TabsList>

            {/* ── WhatsApp Tab ─────────────────────────────────────── */}
            <TabsContent value="whatsapp" className="mt-4 space-y-4">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">Activar WhatsApp</Label>
                <Switch checked={waEnabled} onCheckedChange={setWaEnabled} />
              </div>

              {waEnabled && (
                <>
                  <div className="space-y-1">
                    <Label className="text-xs text-slate-500">Phone Number ID</Label>
                    <Input
                      placeholder="123456789012345"
                      value={waPhoneNumberId}
                      onChange={(e) => setWaPhoneNumberId(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-slate-500">Access Token</Label>
                    <Input
                      type="password"
                      placeholder={waAccessToken === '***' ? '(guardado)' : 'EAAxxxxxxxx...'}
                      value={waAccessToken === '***' ? '' : waAccessToken}
                      onChange={(e) => setWaAccessToken(e.target.value)}
                    />
                    {waAccessToken === '***' && (
                      <p className="text-xs text-slate-400">Token guardado. Escribe un nuevo valor para reemplazarlo.</p>
                    )}
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-slate-500">App Secret (opcional)</Label>
                    <Input
                      type="password"
                      placeholder={waAppSecret === '***' ? '(guardado)' : 'app_secret...'}
                      value={waAppSecret === '***' ? '' : waAppSecret}
                      onChange={(e) => setWaAppSecret(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1 pt-2 border-t border-slate-100">
                    <div className="flex items-center gap-1">
                      <Label className="text-xs text-slate-500">Webhook URL (global)</Label>
                      <a
                        href="https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components"
                        target="_blank"
                        rel="noreferrer"
                        className="text-slate-400 hover:text-slate-600"
                        title="Documentación Meta"
                      >
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                    {waWebhookUrl ? (
                      <WebhookUrlDisplay url={waWebhookUrl} />
                    ) : (
                      <p className="text-xs text-slate-400 mt-1">
                        Guarda la configuración para generar el webhook URL.
                      </p>
                    )}
                  </div>
                </>
              )}
            </TabsContent>

            {/* ── Telegram Tab ─────────────────────────────────────── */}
            <TabsContent value="telegram" className="mt-4 space-y-4">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">Activar Telegram</Label>
                <Switch checked={tgEnabled} onCheckedChange={setTgEnabled} />
              </div>

              {tgEnabled && (
                <>
                  <div className="space-y-1">
                    <Label className="text-xs text-slate-500">Bot Token</Label>
                    <Input
                      type="password"
                      placeholder={tgBotToken === '***' ? '(guardado)' : '7123456789:AAxxxxxx...'}
                      value={tgBotToken === '***' ? '' : tgBotToken}
                      onChange={(e) => setTgBotToken(e.target.value)}
                    />
                    {tgBotToken === '***' && (
                      <p className="text-xs text-slate-400">Token guardado. Escribe un nuevo valor para reemplazarlo.</p>
                    )}
                  </div>
                  <div className="space-y-1 pt-2 border-t border-slate-100">
                    <Label className="text-xs text-slate-500">Webhook URL</Label>
                    {tgWebhookUrl ? (
                      <WebhookUrlDisplay url={tgWebhookUrl} />
                    ) : (
                      <p className="text-xs text-slate-400 mt-1">
                        Guarda la configuración para generar el webhook URL.
                      </p>
                    )}
                  </div>
                  {tgWebhookUrl && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full"
                      onClick={handleRegisterWebhook}
                      disabled={isRegistering || tgBotToken === '***' ? false : !tgBotToken}
                    >
                      {isRegistering ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <CheckCircle2 className="mr-2 h-4 w-4" />
                      )}
                      Registrar Webhook en Telegram
                    </Button>
                  )}
                </>
              )}
            </TabsContent>
          </Tabs>
        )}
        </div>

        <DialogFooter className="shrink-0 pt-2 border-t border-slate-100">
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Cancelar
          </Button>
          <Button onClick={handleSave} disabled={isSaving || isLoading}>
            {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Guardar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
