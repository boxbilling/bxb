import { NavLink, useLocation } from 'react-router-dom'
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
  Building,
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
  Book,
  Signature,
  Moon,
  Sun,
  Menu,
  AlertTriangle,
  TrendingUp,
  Rocket,
} from 'lucide-react'
import { useState, useEffect } from 'react'
import { useTheme } from '@/hooks/use-theme.ts'
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

export const navigationGroups = [
  {
    label: 'Overview',
    items: [
      { name: 'Dashboard', href: '/admin', icon: LayoutDashboard },
      { name: 'Get Started', href: '/admin/onboarding', icon: Rocket },
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
      { name: 'Payment Requests', href: '/admin/payment-requests', icon: Send },
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
    ],
  },
  {
    label: 'Operations',
    items: [
      { name: 'Events', href: '/admin/events', icon: Activity },
      { name: 'Dunning', href: '/admin/dunning-campaigns', icon: Bell },
      { name: 'Usage Alerts', href: '/admin/usage-alerts', icon: AlertTriangle },
    ],
  },
]

type NavItemDef =
  | { type?: 'link'; name: string; href: string; icon: React.ElementType; target?: '_blank' }
  | { type: 'separator' }

export const settingsNavItems: NavItemDef[] = [
  { name: 'Docs', href: 'https://go.boxbilling.com/docs', icon: Book, target: '_blank' },
  { name: 'License', href: 'https://go.boxbilling.com/license', icon: Signature, target: '_blank' },
  { type: 'separator' },
  { name: 'Webhooks', href: '/admin/webhooks', icon: Radio },
  { name: 'Integrations', href: '/admin/integrations', icon: Plug },
  { name: 'Data Exports', href: '/admin/data-exports', icon: FileDown },
  { name: 'Audit Logs', href: '/admin/audit-logs', icon: ScrollText },
  { name: 'API Keys', href: '/admin/api-keys', icon: Key },
  { type: 'separator' },
  { name: 'Taxes', href: '/admin/taxes', icon: Calculator },
  { name: 'Billing Entities', href: '/admin/billing-entities', icon: Building2 },
  { name: 'Organization', href: '/admin/settings', icon: Building },
  { type: 'separator' },
]

type NavLinkItem = { name: string; href: string; icon: React.ElementType; target?: '_blank' }

function NavItem({
  item,
  collapsed,
}: {
  item: NavLinkItem
  collapsed: boolean
}) {
  const location = useLocation()
  const isActive =
    item.href === '/admin'
      ? location.pathname === '/admin'
      : location.pathname.startsWith(item.href)

  const className = cn(
    'flex items-center gap-2.5 rounded-md px-2.5 py-3 md:py-1.5 text-[13px] font-medium transition-colors',
    isActive
      ? 'bg-sidebar-accent text-sidebar-accent-foreground'
      : 'text-sidebar-foreground hover:bg-accent hover:text-accent-foreground'
  )

  const content = item.target ? (
    <a href={item.href} target={item.target} rel="noopener noreferrer" className={className}>
      <item.icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span>{item.name}</span>}
    </a>
  ) : (
    <NavLink to={item.href} className={className}>
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

function SettingsSection({ collapsed }: { collapsed: boolean }) {
  const { theme, toggle } = useTheme()
  const location = useLocation()
  const [expanded, setExpanded] = useState(false)

  const settingsLinkItems = settingsNavItems.filter((item): item is NavLinkItem => item.type !== 'separator')
  const isSettingsActive = settingsLinkItems.some(
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
          {settingsNavItems.map((item, i) =>
            item.type === 'separator' ? (
              <Separator key={`sep-${i}`} className="my-1" />
            ) : item.target ? (
              <DropdownMenuItem key={item.href} asChild>
                <a href={item.href} target={item.target} rel="noopener noreferrer" className="flex items-center gap-2">
                  <item.icon className="h-4 w-4" />
                  {item.name}
                </a>
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem key={item.href} asChild>
                <NavLink to={item.href} className="flex items-center gap-2">
                  <item.icon className="h-4 w-4" />
                  {item.name}
                </NavLink>
              </DropdownMenuItem>
            )
          )}
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
      {expanded && (
        <div className="mb-0.5 space-y-1 md:space-y-0.5">
          {settingsNavItems.map((item, i) =>
            item.type === 'separator' ? (
              <Separator key={`sep-${i}`} className="my-2" />
            ) : (
              <NavItem key={item.href} item={item} collapsed={false} />
            )
          )}
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
      {toggleButton}
    </div>
  )
}

export default function Sidebar({
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

export function MobileSidebar() {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="md:hidden h-11 w-11 min-h-[44px] min-w-[44px]">
          <Menu className="h-5 w-5" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-56 p-0">
        <Sidebar collapsed={false} onToggle={() => {}} />
      </SheetContent>
    </Sheet>
  )
}
