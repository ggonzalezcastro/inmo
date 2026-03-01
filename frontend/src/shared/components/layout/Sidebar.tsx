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
  DollarSign,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Cpu,
} from 'lucide-react'
import { cn } from '@/shared/lib/utils'
import { useAuthStore } from '@/features/auth'
import { usePermissions } from '@/shared/hooks/usePermissions'
import { getInitials } from '@/shared/lib/utils'

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

interface NavItem {
  path: string
  label: string
  icon: LucideIcon
  roles?: ('admin' | 'agent' | 'superadmin')[]
}

const NAV_ITEMS: NavItem[] = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/leads', label: 'Leads', icon: Users },
  { path: '/pipeline', label: 'Pipeline', icon: GitBranch },
  { path: '/campaigns', label: 'Campañas', icon: Megaphone, roles: ['admin', 'superadmin'] },
  { path: '/appointments', label: 'Citas', icon: Calendar },
  { path: '/templates', label: 'Templates', icon: FileText, roles: ['admin', 'superadmin'] },
  { path: '/chat', label: 'Chat IA', icon: MessageSquare },
  { path: '/costs', label: 'Costos LLM', icon: DollarSign, roles: ['admin', 'superadmin'] },
  { path: '/settings', label: 'Configuración', icon: Settings, roles: ['admin', 'superadmin'] },
  { path: '/users', label: 'Usuarios', icon: UserCog, roles: ['admin', 'superadmin'] },
  { path: '/brokers', label: 'Brokers', icon: Building2, roles: ['superadmin'] },
]

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { user, clearAuth } = useAuthStore()
  const { role } = usePermissions()

  const visibleItems = NAV_ITEMS.filter((item) => {
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
          'flex items-center gap-[10px] pt-7 pb-0',
          collapsed ? 'px-[14px] justify-center' : 'px-[18px]'
        )}
      >
        <div className="w-7 h-7 bg-[#1A56DB] rounded-[6px] flex items-center justify-center shrink-0">
          <Building2 size={14} className="text-white" />
        </div>
        {!collapsed && (
          <span className="text-[#111827] text-base font-bold leading-none flex-1">Captame.cl</span>
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
          'flex flex-col gap-0.5 mt-9 flex-1 overflow-y-auto',
          collapsed ? 'px-[10px]' : 'px-[18px]'
        )}
      >
        {visibleItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            title={collapsed ? item.label : undefined}
            className={({ isActive }) =>
              cn(
                'flex items-center rounded-lg text-[13px] font-medium transition-colors',
                collapsed ? 'justify-center h-9 w-9 mx-auto' : 'gap-[10px] h-[38px] px-3',
                isActive
                  ? 'bg-[#EBF2FF] text-[#1A56DB] font-semibold border border-[#BFCFFF]'
                  : 'text-[#6B7280] hover:bg-[#F5F8FF] hover:text-[#1A56DB] border border-transparent'
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
        {!collapsed && (
          <div className="flex items-center gap-[10px] bg-[#F0F7FF] border border-[#BFCFFF] rounded-[10px] px-3.5 py-2.5">
            <div className="w-[7px] h-[7px] bg-[#1A56DB] rounded-full shrink-0 animate-pulse" />
            <div className="flex flex-col gap-0.5 min-w-0">
              <span className="text-[#1A56DB] text-[12px] font-semibold leading-tight">
                Agente activo
              </span>
              <span className="text-[#6B7280] text-[11px] leading-tight truncate">
                Sofia analizando leads
              </span>
            </div>
            <Cpu size={13} className="text-[#1A56DB] shrink-0 ml-auto" />
          </div>
        )}

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
