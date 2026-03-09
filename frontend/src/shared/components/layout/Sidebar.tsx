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
  { path: '/conversations', label: 'Conversaciones', icon: Inbox },
  { path: '/campaigns', label: 'Campañas', icon: Megaphone, roles: ['admin', 'superadmin'] },
  { path: '/appointments', label: 'Citas', icon: Calendar },
  // { path: '/templates', label: 'Templates', icon: FileText, roles: ['admin', 'superadmin'] },
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
          <NavLink
            key={item.path}
            to={item.path}
            title={collapsed ? item.label : undefined}
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
          <div className="flex items-center gap-3 bg-[#EBF2FF] rounded-lg px-3 py-2.5 mx-1">
            <div className="relative shrink-0">
              <div className="w-[7px] h-[7px] bg-[#1A56DB] rounded-full" />
              <div className="absolute inset-0 w-[7px] h-[7px] bg-[#1A56DB] rounded-full animate-ping opacity-40" />
            </div>
            <div className="flex flex-col gap-0.5 min-w-0 flex-1">
              <span className="text-[#1A56DB] text-[11px] font-semibold leading-tight">
                Sofía · activa
              </span>
              <span className="text-[#4B72B8] text-[10px] leading-tight truncate">
                Analizando leads
              </span>
            </div>
            <Cpu size={12} className="text-[#1A56DB]/60 shrink-0" />
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
