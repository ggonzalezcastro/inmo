import { NavLink } from 'react-router-dom'
import {
  type LucideIcon,
  LayoutDashboard,
  Users,
  GitBranch,
  Megaphone,
  Calendar,
  FileText,
  Settings,
  UserCog,
  Building2,
  MessageSquare,
  Inbox,
  DollarSign,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Cpu,
  ShieldCheck,
} from 'lucide-react'
import { cn } from '@/shared/lib/utils'
import { useAuthStore } from '@/features/auth'
import { usePermissions } from '@/shared/hooks/usePermissions'
import { getInitials } from '@/shared/lib/utils'
import { useSofiaActivity, type SofiaStatus } from '@/shared/hooks/useSofiaActivity'

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
  onMobileClose?: () => void
}

interface NavItem {
  path: string
  label: string
  icon: LucideIcon
  roles?: ('admin' | 'agent' | 'superadmin')[]
  excludeRoles?: ('admin' | 'agent' | 'superadmin')[]
  dividerBefore?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/leads', label: 'Leads', icon: Users },
  { path: '/pipeline', label: 'Pipeline', icon: GitBranch, excludeRoles: ['superadmin'] },
  { path: '/conversations', label: 'Conversaciones', icon: Inbox, excludeRoles: ['superadmin'] },
  { path: '/campaigns', label: 'Campañas', icon: Megaphone, roles: ['admin'] },
  { path: '/appointments', label: 'Citas', icon: Calendar, excludeRoles: ['superadmin'] },
  { path: '/chat', label: 'Chat IA', icon: MessageSquare, excludeRoles: ['superadmin'] },
  { path: '/costs', label: 'Costos LLM', icon: DollarSign, roles: ['admin', 'superadmin'] },
  { path: '/settings', label: 'Configuración', icon: Settings, roles: ['admin'] },
  { path: '/users', label: 'Usuarios', icon: UserCog, roles: ['admin', 'superadmin'] },
  { path: '/brokers', label: 'Brokers', icon: Building2, roles: ['superadmin'], dividerBefore: true },
  { path: '/super-admin', label: 'Super Admin', icon: ShieldCheck, roles: ['superadmin'] },
]

const STATUS_COLORS: Record<SofiaStatus, { dot: string; bg: string; text: string; detail: string }> = {
  idle:         { dot: '#1A56DB', bg: '#EBF2FF', text: '#1A56DB', detail: '#4B72B8' },
  receiving:    { dot: '#F59E0B', bg: '#FFFBEB', text: '#92400E', detail: '#B45309' },
  thinking:     { dot: '#8B5CF6', bg: '#F5F3FF', text: '#5B21B6', detail: '#7C3AED' },
  responded:    { dot: '#10B981', bg: '#ECFDF5', text: '#065F46', detail: '#059669' },
  stage_change: { dot: '#3B82F6', bg: '#EFF6FF', text: '#1E40AF', detail: '#2563EB' },
  hot_lead:     { dot: '#EF4444', bg: '#FEF2F2', text: '#991B1B', detail: '#DC2626' },
}

export function Sidebar({ collapsed, onToggle, onMobileClose }: SidebarProps) {
  const { user, clearAuth } = useAuthStore()
  const { role } = usePermissions()
  const sofia = useSofiaActivity()

  const visibleItems = NAV_ITEMS.filter((item) => {
    if (item.excludeRoles && role && item.excludeRoles.includes(role as 'admin' | 'agent' | 'superadmin')) return false
    if (!item.roles) return true
    return role && item.roles.includes(role as 'admin' | 'agent' | 'superadmin')
  })

  return (
    <aside
      className={cn(
        'flex flex-col bg-white border-r border-[#E2EAF4] transition-all duration-200 h-screen sticky top-0 shrink-0',
        collapsed ? 'w-16' : 'w-[220px]'
      )}
    >
      {/* Brand */}
      <div
        className={cn(
          'flex items-center gap-[10px] pt-6 pb-5 border-b border-[#E2EAF4]',
          collapsed ? 'px-[14px] justify-center' : 'px-[18px]'
        )}
      >
        <div className="w-7 h-7 bg-[#1A56DB] rounded-[6px] flex items-center justify-center shrink-0">
          <Building2 size={14} className="text-white" />
        </div>
        {!collapsed && (
          <span className="text-[#111827] text-[15px] font-bold leading-none tracking-tight flex-1">Captame.cl</span>
        )}
        <button
          onClick={onToggle}
          className={cn(
            'p-1 rounded text-[#9CA3AF] hover:text-[#1A56DB] hover:bg-[#EBF2FF] transition-colors',
            collapsed ? 'mx-auto mt-0' : 'ml-auto'
          )}
          aria-label={collapsed ? 'Expandir sidebar' : 'Colapsar sidebar'}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      {/* Navigation */}
      <nav
        className={cn(
          'flex flex-col gap-0.5 mt-4 flex-1 overflow-y-auto',
          collapsed ? 'px-[10px]' : 'px-[10px]'
        )}
      >
        {visibleItems.map((item) => (
          <div key={item.path}>
            {item.dividerBefore && !collapsed && <div className="h-px bg-[#E2EAF4] mx-1 my-2" />}
            {item.dividerBefore && collapsed && <div className="h-px bg-[#E2EAF4] my-2" />}
            <NavLink
              to={item.path}
              title={collapsed ? item.label : undefined}
              onClick={onMobileClose}
              className={({ isActive }) =>
                cn(
                  'flex items-center rounded-lg text-[13px] font-medium transition-all',
                  collapsed ? 'justify-center h-9 w-9 mx-auto' : 'gap-[10px] h-[36px] px-3',
                  isActive
                    ? 'bg-[#EBF2FF] text-[#1A56DB] font-semibold'
                    : 'text-[#6B7280] hover:bg-[#F5F8FF] hover:text-[#374151]'
                )
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon
                    size={15}
                    className={cn(
                      'shrink-0 transition-colors',
                      isActive ? 'text-[#1A56DB]' : 'text-[#9CA3AF]'
                    )}
                  />
                  {!collapsed && <span>{item.label}</span>}
                </>
              )}
            </NavLink>
          </div>
        ))}
      </nav>

      {/* Bottom section */}
      <div
        className={cn(
          'flex flex-col gap-3 pb-6',
          collapsed ? 'px-[10px]' : 'px-3.5'
        )}
      >
        {/* Agent Status — only when expanded */}
        {!collapsed && (() => {
          const c = STATUS_COLORS[sofia.status]
          return (
            <div
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 mx-1 transition-colors duration-500"
              style={{ background: c.bg }}
            >
              {/* Animated dot */}
              <div className="relative shrink-0 w-[7px] h-[7px]">
                <div className="w-[7px] h-[7px] rounded-full" style={{ background: c.dot }} />
                {sofia.status !== 'idle' && (
                  <div
                    className="absolute inset-0 w-[7px] h-[7px] rounded-full animate-ping"
                    style={{ background: c.dot, opacity: 0.45 }}
                  />
                )}
              </div>

              {/* Text */}
              <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                <span className="text-[11px] font-semibold leading-tight transition-colors duration-500" style={{ color: c.text }}>
                  Sofía · {sofia.label}
                </span>
                {sofia.detail ? (
                  <span className="text-[10px] leading-tight truncate transition-colors duration-500" style={{ color: c.detail }}>
                    {sofia.detail}
                  </span>
                ) : sofia.eventCount > 0 ? (
                  <span className="text-[10px] leading-tight" style={{ color: c.detail }}>
                    {sofia.eventCount} {sofia.eventCount === 1 ? 'evento' : 'eventos'} hoy
                  </span>
                ) : (
                  <span className="text-[10px] leading-tight" style={{ color: c.detail }}>
                    esperando actividad
                  </span>
                )}
              </div>

              <Cpu size={12} className="shrink-0 transition-colors duration-500" style={{ color: c.dot, opacity: 0.6 }} />
            </div>
          )
        })()}

        {/* User Profile */}
        <div
          className={cn(
            'flex items-center gap-[10px] pt-3 border-t border-[#E2EAF4]',
            collapsed && 'justify-center'
          )}
        >
          <div className="w-[30px] h-[30px] bg-[#1A56DB] rounded-full flex items-center justify-center shrink-0">
            <span className="text-white text-[11px] font-semibold">
              {user ? getInitials(user.name || user.email) : 'U'}
            </span>
          </div>

          {!collapsed && (
            <>
              <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                <span className="text-[#111827] text-[12px] font-semibold leading-tight truncate">
                  {user?.name || user?.email}
                </span>
                <span className="text-[#9CA3AF] text-[11px] leading-tight capitalize">
                  {user?.role}
                </span>
              </div>
              <button
                onClick={clearAuth}
                title="Cerrar sesión"
                aria-label="Cerrar sesión"
                className="shrink-0 p-1 rounded text-[#9CA3AF] hover:text-red-500 hover:bg-red-50 transition-colors"
              >
                <LogOut size={14} />
              </button>
            </>
          )}

          {collapsed && (
            <button
              onClick={clearAuth}
              title="Cerrar sesión"
              aria-label="Cerrar sesión"
              className="absolute bottom-3 right-0 left-0 mx-auto w-9 h-9 flex items-center justify-center rounded text-[#9CA3AF] hover:text-red-500 hover:bg-red-50 transition-colors hidden"
            />
          )}
        </div>
      </div>
    </aside>
  )
}
