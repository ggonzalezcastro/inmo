import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
      <main className="flex-1 overflow-y-auto">
        <div className="h-full">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
