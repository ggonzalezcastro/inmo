import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Building2, Eye, EyeOff, Loader2, TrendingUp, Clock, Users } from 'lucide-react'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import { useLogin } from '../hooks/useLogin'

const STYLES = `
  @keyframes lp-up {
    from { opacity: 0; transform: translateY(18px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes lp-in { from { opacity: 0; } to { opacity: 1; } }

  .lp-panel { animation: lp-in 0.9s ease both; }
  .lp-a1 { animation: lp-up 0.65s cubic-bezier(0.22,1,0.36,1) 0.05s both; }
  .lp-a2 { animation: lp-up 0.65s cubic-bezier(0.22,1,0.36,1) 0.15s both; }
  .lp-a3 { animation: lp-up 0.65s cubic-bezier(0.22,1,0.36,1) 0.22s both; }
  .lp-a4 { animation: lp-up 0.65s cubic-bezier(0.22,1,0.36,1) 0.29s both; }
  .lp-a5 { animation: lp-up 0.65s cubic-bezier(0.22,1,0.36,1) 0.36s both; }
  .lp-a6 { animation: lp-up 0.65s cubic-bezier(0.22,1,0.36,1) 0.43s both; }

  .lp-stat-card {
    display: flex;
    align-items: center;
    gap: 0.875rem;
    padding: 0.875rem 1rem;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    backdrop-filter: blur(8px);
  }

  .lp-stat-icon {
    width: 36px; height: 36px; border-radius: 8px; flex-shrink: 0;
    background: rgba(26,86,219,0.25);
    border: 1px solid rgba(26,86,219,0.35);
    display: flex; align-items: center; justify-content: center;
  }
`

const stats = [
  { icon: TrendingUp, value: '3×',   label: 'más conversiones',    sub: 'vs. seguimiento manual' },
  { icon: Clock,      value: '<2\'',  label: 'tiempo de respuesta', sub: 'la IA responde primero' },
  { icon: Users,      value: '98%',  label: 'tasa de respuesta',   sub: 'ningún lead sin atender' },
]

function LeftPanelBg() {
  return (
    <svg
      aria-hidden
      className="absolute inset-0 w-full h-full pointer-events-none"
      viewBox="0 0 480 800"
      preserveAspectRatio="xMidYMid slice"
      fill="none"
    >
      <defs>
        <pattern id="lp-grid" width="36" height="36" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="0.85" fill="white" fillOpacity="0.06" />
        </pattern>
        <radialGradient id="lp-glow1" cx="20%" cy="75%" r="55%">
          <stop offset="0%" stopColor="#1A56DB" stopOpacity="0.22" />
          <stop offset="100%" stopColor="#1A56DB" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="lp-glow2" cx="85%" cy="18%" r="45%">
          <stop offset="0%" stopColor="#60A5FA" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#60A5FA" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="100%" height="100%" fill="url(#lp-grid)" />
      <rect width="100%" height="100%" fill="url(#lp-glow1)" />
      <rect width="100%" height="100%" fill="url(#lp-glow2)" />
      {/* Thin geometric accent lines */}
      <rect x="20" y="60" width="220" height="155" rx="3" transform="rotate(-8 20 60)"
        stroke="white" strokeWidth="0.5" strokeOpacity="0.07" />
      <rect x="200" y="480" width="300" height="210" rx="3" transform="rotate(-8 200 480)"
        stroke="white" strokeWidth="0.5" strokeOpacity="0.06" />
      <line x1="0" y1="800" x2="480" y2="0" stroke="white" strokeWidth="0.5" strokeOpacity="0.05" />
    </svg>
  )
}

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
    <>
      <style>{STYLES}</style>
      <div className="min-h-screen flex bg-background">

        {/* ── Left panel ─────────────────────────────────────────────── */}
        <div
          className="lp-panel hidden lg:flex lg:w-[48%] flex-col justify-between p-12 relative overflow-hidden"
          style={{ background: '#0A1628' }}
        >
          <LeftPanelBg />

          {/* Logo */}
          <div className="relative z-10 flex items-center gap-2.5">
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
              <Building2 className="h-4 w-4 text-white" />
            </div>
            <span className="text-white font-semibold text-[0.9375rem] tracking-tight">Captame.cl</span>
          </div>

          {/* Headline */}
          <div className="relative z-10">
            <p className="text-[#93B4F5] text-xs font-medium tracking-[0.18em] uppercase mb-5">
              CRM Inmobiliario con IA
            </p>
            <h2 className="text-white font-bold leading-[1.15] mb-4" style={{ fontSize: '2.625rem' }}>
              Convierte leads<br />
              <span className="text-[#93B4F5]">en clientes reales.</span>
            </h2>
            <p className="text-[#5C7499] text-[0.9375rem] leading-relaxed mb-10 max-w-[22rem]">
              Sofía, tu agente de IA, trabaja 24/7 calificando prospectos, respondiendo consultas y agendando visitas.
            </p>

            <div className="flex flex-col gap-3">
              {stats.map(({ icon: Icon, value, label, sub }) => (
                <div key={value} className="lp-stat-card">
                  <div className="lp-stat-icon">
                    <Icon className="h-4 w-4 text-[#93B4F5]" />
                  </div>
                  <div>
                    <p className="text-white font-semibold text-sm leading-tight">
                      <span className="text-[#93B4F5] mr-1.5">{value}</span>{label}
                    </p>
                    <p className="text-[#3E5270] text-xs mt-0.5">{sub}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <p className="relative z-10 text-[#243040] text-[0.7rem]">
            © 2025 Captame.cl · Todos los derechos reservados
          </p>
        </div>

        {/* ── Right panel — Form ──────────────────────────────────────── */}
        <div className="flex-1 flex items-center justify-center p-8 bg-background">
          <div className="w-full max-w-[22rem]">

            {/* Mobile logo */}
            <div className="lp-a1 flex items-center gap-2.5 mb-9 lg:hidden">
              <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                <Building2 className="h-4 w-4 text-white" />
              </div>
              <span className="font-semibold text-foreground">Captame.cl</span>
            </div>

            {/* Heading */}
            <div className="lp-a2 mb-8">
              <h1 className="text-[1.75rem] font-bold text-foreground leading-tight mb-1.5">
                Bienvenido de vuelta
              </h1>
              <p className="text-muted-foreground text-sm">
                Ingresa tus credenciales para continuar
              </p>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="lp-a3 space-y-1.5">
                <Label htmlFor="email" className="text-[0.8125rem] font-medium text-foreground">
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
                  className="h-11 bg-card border-border focus-visible:ring-primary/30"
                />
              </div>

              <div className="lp-a4 space-y-1.5">
                <Label htmlFor="password" className="text-[0.8125rem] font-medium text-foreground">
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
                    className="h-11 pr-10 bg-card border-border focus-visible:ring-primary/30"
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

              <div className="lp-a5 pt-1">
                <Button
                  type="submit"
                  className="w-full h-11 text-sm font-semibold bg-primary hover:bg-primary/90"
                  disabled={isLoading}
                >
                  {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Ingresar
                </Button>
              </div>
            </form>

            <p className="lp-a6 mt-6 text-center text-sm text-muted-foreground">
              ¿No tienes cuenta?{' '}
              <Link to="/register" className="text-primary hover:text-primary/80 font-medium transition-colors">
                Registrar inmobiliaria
              </Link>
            </p>
          </div>
        </div>

      </div>
    </>
  )
}
