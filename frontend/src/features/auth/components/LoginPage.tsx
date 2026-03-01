import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Building2, Eye, EyeOff, Loader2, TrendingUp, Clock, Users } from 'lucide-react'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import { useLogin } from '../hooks/useLogin'

const stats = [
  {
    icon: TrendingUp,
    value: '3× más conversiones',
    label: 'frente a seguimiento manual',
  },
  {
    icon: Clock,
    value: 'Respuesta en <2 min',
    label: 'la IA responde antes que la competencia',
  },
  {
    icon: Users,
    value: '98% tasa de respuesta',
    label: 'ningún lead sin atender',
  },
]

export function LoginPage() {
  const { login, isLoading } = useLogin()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    login({ email, password })
  }

  return (
    <div className="min-h-screen flex">
      {/* ── Left panel ─────────────────────────────────────────────────────────── */}
      <div className="hidden lg:flex lg:w-5/12 bg-[#0A1628] flex-col justify-between p-12 relative overflow-hidden">
        {/* Decorative blobs */}
        <div className="absolute top-0 right-0 w-72 h-72 rounded-full bg-[#1A56DB]/10 blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-96 h-96 rounded-full bg-[#1A56DB]/5 blur-3xl pointer-events-none" />

        {/* Dot-grid pattern */}
        <svg
          className="absolute inset-0 w-full h-full opacity-[0.035] pointer-events-none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <pattern id="dots" width="40" height="40" patternUnits="userSpaceOnUse">
              <circle cx="1" cy="1" r="1" fill="white" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#dots)" />
        </svg>

        {/* Logo */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="w-9 h-9 bg-[#1A56DB] rounded-lg flex items-center justify-center">
            <Building2 className="h-5 w-5 text-white" />
          </div>
          <span className="text-lg font-semibold text-white tracking-tight">Captame.cl</span>
        </div>

        {/* Headline + stats */}
        <div className="relative z-10">
          <h2 className="text-[2.25rem] font-bold text-white leading-[1.2] mb-3">
            Convierte leads en<br />
            <span className="text-[#93B4F5]">clientes reales.</span>
          </h2>
          <p className="text-[#8B9FBE] text-[15px] leading-relaxed mb-10 max-w-xs">
            El CRM inmobiliario con IA que trabaja 24/7 calificando, respondiendo y agendando visitas por ti.
          </p>

          <div className="space-y-5">
            {stats.map(({ icon: Icon, value, label }) => (
              <div key={value} className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-[#1A56DB]/20 border border-[#1A56DB]/30 flex items-center justify-center shrink-0">
                  <Icon className="h-5 w-5 text-[#93B4F5]" />
                </div>
                <div>
                  <p className="text-white font-semibold text-[15px] leading-tight">{value}</p>
                  <p className="text-[#8B9FBE] text-sm">{label}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <p className="relative z-10 text-[#4B6080] text-xs">
          © 2025 Captame.cl · Todos los derechos reservados
        </p>
      </div>

      {/* ── Right panel — Form ─────────────────────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center p-8 bg-white">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <div className="flex items-center gap-3 mb-8 lg:hidden">
            <div className="w-9 h-9 bg-primary rounded-lg flex items-center justify-center">
              <Building2 className="h-5 w-5 text-white" />
            </div>
            <span className="text-lg font-semibold">Captame.cl</span>
          </div>

          <div className="mb-8">
            <h1 className="text-[1.625rem] font-bold text-[#111827] mb-1 tracking-tight">
              Bienvenido de vuelta
            </h1>
            <p className="text-[#6B7280] text-sm">Ingresa tus credenciales para continuar</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-sm font-medium text-[#374151]">
                Email
              </Label>
              <Input
                id="email"
                type="email"
                placeholder="tu@empresa.cl"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                className="h-11"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-sm font-medium text-[#374151]">
                Contraseña
              </Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  className="h-11 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <Button type="submit" className="w-full h-11 text-sm font-semibold" disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Ingresar
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            ¿No tienes cuenta?{' '}
            <Link to="/register" className="text-primary hover:underline font-medium">
              Registrar inmobiliaria
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
