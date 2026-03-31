import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Menu } from 'lucide-react'
import { Sidebar } from './Sidebar'

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar — hidden on mobile unless mobileOpen */}
      <div
        className={`
          fixed inset-y-0 left-0 z-40 transition-transform duration-200
          lg:static lg:translate-x-0 lg:z-auto
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <Sidebar
          collapsed={collapsed}
          onToggle={() => setCollapsed((v) => !v)}
          onMobileClose={() => setMobileOpen(false)}
        />
      </div>

      <main className="flex-1 overflow-y-auto min-w-0">
        {/* Mobile top bar */}
        <div className="sticky top-0 z-20 flex items-center gap-3 px-4 py-3 bg-background border-b border-border lg:hidden">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-1.5 rounded-lg text-muted-foreground hover:bg-accent transition-colors"
            aria-label="Abrir menú"
          >
            <Menu size={20} />
          </button>
          <span className="text-sm font-semibold text-foreground">Captame.cl</span>
        </div>

        <div className="h-full">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
