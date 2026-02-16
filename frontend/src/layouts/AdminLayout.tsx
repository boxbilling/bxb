import { Outlet } from 'react-router-dom'
import { Search } from 'lucide-react'
import { useState, useMemo } from 'react'
import { Button } from '@/components/ui/button'
import NotificationBell from '@/components/NotificationBell'
import { CommandPalette } from '@/components/CommandPalette'
import HeaderBreadcrumb, { BreadcrumbProvider, MobilePageTitle } from '@/components/HeaderBreadcrumb'
import Sidebar, { MobileSidebar, navigationGroups, settingsNavItems } from '@/components/Sidebar'

export default function AdminLayout() {
  const [collapsed, setCollapsed] = useState(false)

  const routeLabels = useMemo(() => {
    const labels: Record<string, string> = {}
    for (const group of navigationGroups) {
      for (const item of group.items) {
        labels[item.href] = item.name
      }
    }
    for (const item of settingsNavItems) {
      if (item.type !== 'separator') {
        labels[item.href] = item.name
      }
    }
    return labels
  }, [])

  return (
    <BreadcrumbProvider routeLabels={routeLabels}>
      <div className="flex h-screen bg-background">
        <div className="hidden md:flex">
          <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
        </div>

        <div className="flex flex-1 flex-col overflow-hidden">
          <header className="flex h-14 items-center border-b px-4 md:px-6 gap-4">
            <MobileSidebar />
            <div className="flex-1 min-w-0 md:hidden">
              <MobilePageTitle />
            </div>
            <div className="flex-1 hidden md:block">
              <HeaderBreadcrumb />
            </div>
            <Button
              variant="outline"
              size="sm"
              className="hidden md:flex items-center gap-2 text-muted-foreground"
              onClick={() => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))}
            >
              <Search className="h-3.5 w-3.5" />
              <span className="text-xs">Search...</span>
              <kbd className="pointer-events-none ml-2 inline-flex h-5 select-none items-center gap-0.5 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
                <span className="text-xs">&#8984;</span>K
              </kbd>
            </Button>
            <NotificationBell />
          </header>

          <main className="flex-1 overflow-y-auto p-4 md:p-6">
            <Outlet />
          </main>
        </div>

        <CommandPalette />
      </div>
    </BreadcrumbProvider>
  )
}
