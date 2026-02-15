import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
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
  Send,
  FileDown,
  ScrollText,
  Settings,
  Key,
  Moon,
  Sun,
  Menu,
} from 'lucide-react'
import { useState, useEffect } from 'react'
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
import OrgSwitcher from '@/components/OrgSwitcher'

const navigationGroups = [
  {
    label: null,
    items: [
      { name: 'Dashboard', href: '/admin', icon: LayoutDashboard },
      { name: 'Customers', href: '/admin/customers', icon: Users },
      { name: 'Billing Entities', href: '/admin/billing-entities', icon: Building2 },
    ],
  },
  {
    label: 'Products',
    items: [
      { name: 'Billable Metrics', href: '/admin/metrics', icon: Gauge },
      { name: 'Plans', href: '/admin/plans', icon: Layers },
    ],
  },
  {
    label: 'Billing',
    items: [
      { name: 'Subscriptions', href: '/admin/subscriptions', icon: RefreshCw },
      { name: 'Events', href: '/admin/events', icon: Activity },
      { name: 'Invoices', href: '/admin/invoices', icon: FileText },
      { name: 'Fees', href: '/admin/fees', icon: CircleDollarSign },
      { name: 'Payments', href: '/admin/payments', icon: ArrowLeftRight },
      { name: 'Credit Notes', href: '/admin/credit-notes', icon: FileMinus },
      { name: 'Payment Methods', href: '/admin/payment-methods', icon: CreditCard },
    ],
  },
  {
    label: 'Financial',
    items: [
      { name: 'Wallets', href: '/admin/wallets', icon: Wallet },
      { name: 'Coupons', href: '/admin/coupons', icon: Percent },
      { name: 'Add-ons', href: '/admin/add-ons', icon: Puzzle },
      { name: 'Taxes', href: '/admin/taxes', icon: Calculator },
    ],
  },
  {
    label: 'Operations',
    items: [
      { name: 'Webhooks', href: '/admin/webhooks', icon: Radio },
      { name: 'Dunning', href: '/admin/dunning-campaigns', icon: Bell },
      { name: 'Payment Requests', href: '/admin/payment-requests', icon: Send },
      { name: 'Data Exports', href: '/admin/data-exports', icon: FileDown },
      { name: 'Integrations', href: '/admin/integrations', icon: Plug },
      { name: 'Audit Logs', href: '/admin/audit-logs', icon: ScrollText },
    ],
  },
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
        'flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors',
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

      <nav className="flex-1 overflow-y-auto space-y-0.5 px-2 pb-2 pt-1">
        <TooltipProvider delayDuration={0}>
          {navigationGroups.map((group, groupIndex) => (
            <div key={groupIndex}>
              {group.label && !collapsed && (
                <p className="px-2.5 pt-5 pb-1 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  {group.label}
                </p>
              )}
              {group.label && collapsed && groupIndex > 0 && (
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
          <SettingsMenu collapsed={collapsed} />
        </TooltipProvider>
      </div>
    </div>
  )
}

function MobileSidebar() {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="md:hidden h-8 w-8">
          <Menu className="h-4 w-4" />
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

function SettingsMenu({ collapsed }: { collapsed: boolean }) {
  const { theme, toggle } = useTheme()
  const navigate = useNavigate()
  const location = useLocation()
  const isActive = location.pathname.startsWith('/admin/settings') || location.pathname.startsWith('/admin/api-keys')

  const trigger = (
    <DropdownMenuTrigger asChild>
      <button
        className={cn(
          'flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors',
          isActive
            ? 'bg-sidebar-accent text-sidebar-accent-foreground'
            : 'text-sidebar-foreground hover:bg-accent hover:text-accent-foreground'
        )}
      >
        <Settings className="h-4 w-4 shrink-0" />
        {!collapsed && <span>Settings</span>}
      </button>
    </DropdownMenuTrigger>
  )

  return (
    <DropdownMenu>
      {collapsed ? (
        <Tooltip>
          <TooltipTrigger asChild>{trigger}</TooltipTrigger>
          <TooltipContent side="right">Settings</TooltipContent>
        </Tooltip>
      ) : (
        trigger
      )}
      <DropdownMenuContent side="right" align="end" className="w-48">
        <DropdownMenuItem onClick={() => navigate('/admin/settings')}>
          <Settings className="mr-2 h-4 w-4" />
          Organization
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => navigate('/admin/api-keys')}>
          <Key className="mr-2 h-4 w-4" />
          API Keys
        </DropdownMenuItem>
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

export default function AdminLayout() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex h-screen bg-background">
      <div className="hidden md:flex">
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      </div>

      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-14 items-center border-b px-4 md:px-6">
          <MobileSidebar />
        </header>

        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
