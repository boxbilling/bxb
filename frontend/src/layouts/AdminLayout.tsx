import { Outlet, NavLink, Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Users,
  Gauge,
  Layers,
  RefreshCw,
  Activity,
  FileText,
  FileMinus,
  Calculator,
  CircleDollarSign,
  ArrowLeftRight,
  CreditCard,
  Wallet,
  Percent,
  Puzzle,
  Building2,
  Bell,
  Plug,
  Radio,
  ToggleLeft,
  Send,
  FileDown,
  ScrollText,
  Settings,
  Key,
  Moon,
  Sun,
  Menu,
  AlertTriangle,
  Search,
  TrendingUp,
} from 'lucide-react'
import { useState, useEffect, useMemo } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import OrgSwitcher from '@/components/OrgSwitcher'
import NotificationBell from '@/components/NotificationBell'
import { CommandPalette } from '@/components/CommandPalette'

const navigationGroups = [
  {
    label: 'Overview',
    items: [
      { name: 'Dashboard', href: '/admin', icon: LayoutDashboard },
      { name: 'Revenue Analytics', href: '/admin/revenue-analytics', icon: TrendingUp },
    ],
  },
  {
    label: 'Customers',
    items: [
      { name: 'Customers', href: '/admin/customers', icon: Users },
      { name: 'Subscriptions', href: '/admin/subscriptions', icon: RefreshCw },
      { name: 'Wallets', href: '/admin/wallets', icon: Wallet },
      { name: 'Payment Methods', href: '/admin/payment-methods', icon: CreditCard },
    ],
  },
  {
    label: 'Catalog',
    items: [
      { name: 'Plans', href: '/admin/plans', icon: Layers },
      { name: 'Billable Metrics', href: '/admin/metrics', icon: Gauge },
      { name: 'Features', href: '/admin/features', icon: ToggleLeft },
      { name: 'Add-ons', href: '/admin/add-ons', icon: Puzzle },
      { name: 'Coupons', href: '/admin/coupons', icon: Percent },
    ],
  },
  {
    label: 'Billing',
    items: [
      { name: 'Invoices', href: '/admin/invoices', icon: FileText },
      { name: 'Payments', href: '/admin/payments', icon: ArrowLeftRight },
      { name: 'Fees', href: '/admin/fees', icon: CircleDollarSign },
      { name: 'Credit Notes', href: '/admin/credit-notes', icon: FileMinus },
      { name: 'Taxes', href: '/admin/taxes', icon: Calculator },
    ],
  },
  {
    label: 'Operations',
    items: [
      { name: 'Events', href: '/admin/events', icon: Activity },
      { name: 'Webhooks', href: '/admin/webhooks', icon: Radio },
      { name: 'Dunning', href: '/admin/dunning-campaigns', icon: Bell },
      { name: 'Usage Alerts', href: '/admin/usage-alerts', icon: AlertTriangle },
      { name: 'Integrations', href: '/admin/integrations', icon: Plug },
    ],
  },
]

const settingsNavItems = [
  { name: 'Organization', href: '/admin/settings', icon: Settings },
  { name: 'Billing Entities', href: '/admin/billing-entities', icon: Building2 },
  { name: 'API Keys', href: '/admin/api-keys', icon: Key },
  { name: 'Data Exports', href: '/admin/data-exports', icon: FileDown },
  { name: 'Audit Logs', href: '/admin/audit-logs', icon: ScrollText },
  { name: 'Payment Requests', href: '/admin/payment-requests', icon: Send },
]

function NavItem({
  item,
  collapsed,
}: {
  item: { name: string; href: string; icon: React.ElementType }
  collapsed: boolean
}) {
  const location = useLocation()
  const isActive =
    item.href === '/admin'
      ? location.pathname === '/admin'
      : location.pathname.startsWith(item.href)

  const content = (
    <NavLink
      to={item.href}
      className={cn(
        'flex items-center gap-2.5 rounded-md px-2.5 py-3 md:py-1.5 text-[13px] font-medium transition-colors',
        isActive
          ? 'bg-sidebar-accent text-sidebar-accent-foreground'
          : 'text-sidebar-foreground hover:bg-accent hover:text-accent-foreground'
      )}
    >
      <item.icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span>{item.name}</span>}
    </NavLink>
  )

  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>{content}</TooltipTrigger>
        <TooltipContent side="right">{item.name}</TooltipContent>
      </Tooltip>
    )
  }

  return content
}

function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean
  onToggle: () => void
}) {
  return (
    <div
      className={cn(
        'relative flex h-full flex-col border-r bg-sidebar transition-all duration-200',
        collapsed ? 'w-14' : 'w-56'
      )}
    >
      {/* Drag edge to toggle */}
      <div
        className="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-primary/20 active:bg-primary/30 transition-colors z-10"
        onClick={onToggle}
        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      />

      <div className="h-14 shrink-0 border-b">
        <TooltipProvider delayDuration={0}>
          <OrgSwitcher collapsed={collapsed} />
        </TooltipProvider>
      </div>

      <nav className="flex-1 overflow-y-auto space-y-1 md:space-y-0.5 px-2 pb-2 pt-1">
        <TooltipProvider delayDuration={0}>
          {navigationGroups.map((group, groupIndex) => (
            <div key={groupIndex}>
              {group.label && !collapsed && (
                <p className={cn(
                  'px-2.5 pb-1 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider',
                  groupIndex === 0 ? 'pt-2' : 'pt-5'
                )}>
                  {group.label}
                </p>
              )}
              {collapsed && groupIndex > 0 && (
                <Separator className="my-2" />
              )}
              {group.items.map((item) => (
                <NavItem key={item.href} item={item} collapsed={collapsed} />
              ))}
            </div>
          ))}
        </TooltipProvider>
      </nav>

      <div className="px-2 pb-2 border-t pt-2">
        <TooltipProvider delayDuration={0}>
          <SettingsSection collapsed={collapsed} />
        </TooltipProvider>
      </div>
    </div>
  )
}

function MobileSidebar() {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="md:hidden h-11 w-11">
          <Menu className="h-5 w-5" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-56 p-0">
        <Sidebar collapsed={false} onToggle={() => {}} />
      </SheetContent>
    </Sheet>
  )
}

function useTheme() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light')

  useEffect(() => {
    const isDark = document.documentElement.classList.contains('dark')
    setTheme(isDark ? 'dark' : 'light')
  }, [])

  const toggle = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(newTheme)
    document.documentElement.classList.toggle('dark')
  }

  return { theme, toggle }
}

function SettingsSection({ collapsed }: { collapsed: boolean }) {
  const { theme, toggle } = useTheme()
  const location = useLocation()
  const [expanded, setExpanded] = useState(false)

  const isSettingsActive = settingsNavItems.some(
    (item) => item.href === location.pathname || location.pathname.startsWith(item.href + '/')
  )

  // Auto-expand when a settings route is active
  useEffect(() => {
    if (isSettingsActive) setExpanded(true)
  }, [isSettingsActive])

  const toggleButton = (
    <button
      onClick={() => setExpanded(!expanded)}
      className={cn(
        'flex w-full items-center gap-2.5 rounded-md px-2.5 py-3 md:py-1.5 text-[13px] font-medium transition-colors',
        isSettingsActive
          ? 'bg-sidebar-accent text-sidebar-accent-foreground'
          : 'text-sidebar-foreground hover:bg-accent hover:text-accent-foreground'
      )}
    >
      <Settings className="h-4 w-4 shrink-0" />
      {!collapsed && (
        <>
          <span className="flex-1 text-left">Settings</span>
          <svg
            className={cn('h-3 w-3 transition-transform', expanded && 'rotate-180')}
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </>
      )}
    </button>
  )

  if (collapsed) {
    return (
      <DropdownMenu>
        <Tooltip>
          <TooltipTrigger asChild>
            <DropdownMenuTrigger asChild>{toggleButton}</DropdownMenuTrigger>
          </TooltipTrigger>
          <TooltipContent side="right">Settings</TooltipContent>
        </Tooltip>
        <DropdownMenuContent side="right" align="end" className="w-48">
          {settingsNavItems.map((item) => (
            <DropdownMenuItem key={item.href} asChild>
              <NavLink to={item.href} className="flex items-center gap-2">
                <item.icon className="h-4 w-4" />
                {item.name}
              </NavLink>
            </DropdownMenuItem>
          ))}
          <DropdownMenuItem onClick={(e) => { e.preventDefault(); toggle() }}>
            {theme === 'light' ? (
              <Moon className="mr-2 h-4 w-4" />
            ) : (
              <Sun className="mr-2 h-4 w-4" />
            )}
            {theme === 'light' ? 'Dark mode' : 'Light mode'}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    )
  }

  return (
    <div>
      {toggleButton}
      {expanded && (
        <div className="mt-0.5 space-y-1 md:space-y-0.5">
          {settingsNavItems.map((item) => (
            <NavItem key={item.href} item={item} collapsed={false} />
          ))}
          <button
            onClick={toggle}
            className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-3 md:py-1.5 text-[13px] font-medium text-sidebar-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
          >
            {theme === 'light' ? (
              <Moon className="h-4 w-4 shrink-0" />
            ) : (
              <Sun className="h-4 w-4 shrink-0" />
            )}
            <span>{theme === 'light' ? 'Dark mode' : 'Light mode'}</span>
          </button>
        </div>
      )}
    </div>
  )
}

const ROUTE_LABELS: Record<string, string> = {
  '/admin': 'Dashboard',
  '/admin/customers': 'Customers',
  '/admin/billing-entities': 'Billing Entities',
  '/admin/metrics': 'Billable Metrics',
  '/admin/plans': 'Plans',
  '/admin/features': 'Features',
  '/admin/subscriptions': 'Subscriptions',
  '/admin/events': 'Events',
  '/admin/invoices': 'Invoices',
  '/admin/fees': 'Fees',
  '/admin/payments': 'Payments',
  '/admin/credit-notes': 'Credit Notes',
  '/admin/payment-methods': 'Payment Methods',
  '/admin/wallets': 'Wallets',
  '/admin/coupons': 'Coupons',
  '/admin/add-ons': 'Add-ons',
  '/admin/taxes': 'Taxes',
  '/admin/webhooks': 'Webhooks',
  '/admin/dunning-campaigns': 'Dunning Campaigns',
  '/admin/usage-alerts': 'Usage Alerts',
  '/admin/payment-requests': 'Payment Requests',
  '/admin/data-exports': 'Data Exports',
  '/admin/integrations': 'Integrations',
  '/admin/audit-logs': 'Audit Logs',
  '/admin/settings': 'Settings',
  '/admin/api-keys': 'API Keys',
}

function HeaderBreadcrumb() {
  const location = useLocation()
  const crumbs = useMemo(() => {
    const path = location.pathname
    if (path === '/admin') return []

    // Build breadcrumb segments
    const segments = path.replace(/^\/admin\/?/, '').split('/')
    const result: { label: string; href?: string }[] = []

    // Find the parent list page
    const parentPath = '/admin/' + segments[0]
    const parentLabel = ROUTE_LABELS[parentPath]
    if (parentLabel) {
      if (segments.length > 1) {
        result.push({ label: parentLabel, href: parentPath })
        // Detail page — show ID or action
        const sub = segments.slice(1).join('/')
        const subLabel = sub === 'new' ? 'New' : sub === 'edit' ? 'Edit' : 'Detail'
        result.push({ label: subLabel })
      } else {
        result.push({ label: parentLabel })
      }
    }

    return result
  }, [location.pathname])

  if (crumbs.length === 0) return null

  return (
    <Breadcrumb>
      <BreadcrumbList>
        <BreadcrumbItem>
          <BreadcrumbLink asChild>
            <Link to="/admin">Home</Link>
          </BreadcrumbLink>
        </BreadcrumbItem>
        {crumbs.map((crumb, i) => (
          <span key={i} className="contents">
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              {crumb.href ? (
                <BreadcrumbLink asChild>
                  <Link to={crumb.href}>{crumb.label}</Link>
                </BreadcrumbLink>
              ) : (
                <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
              )}
            </BreadcrumbItem>
          </span>
        ))}
      </BreadcrumbList>
    </Breadcrumb>
  )
}

export default function AdminLayout() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex h-screen bg-background">
      <div className="hidden md:flex">
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      </div>

      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-14 items-center border-b px-4 md:px-6 gap-4">
          <MobileSidebar />
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
  )
}
