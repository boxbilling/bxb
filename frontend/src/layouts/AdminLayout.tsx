import { Outlet, NavLink, useLocation } from 'react-router-dom'
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
  Wallet,
  Percent,
  Puzzle,
  Bell,
  Plug,
  Radio,
  Send,
  FileDown,
  Settings,
  Moon,
  Sun,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Copy,
} from 'lucide-react'
import { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { organizationsApi, ApiError } from '@/lib/api'
import type { OrganizationCreate } from '@/types/billing'
import { useOrganization } from '@/hooks/use-organization'

const navigationGroups = [
  {
    label: null,
    items: [
      { name: 'Dashboard', href: '/admin', icon: LayoutDashboard },
      { name: 'Customers', href: '/admin/customers', icon: Users },
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

function OrgHeader({ collapsed }: { collapsed: boolean }) {
  const { data: org, isLoading } = useOrganization()
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [apiKeyDialog, setApiKeyDialog] = useState<string | null>(null)
  const [form, setForm] = useState<OrganizationCreate>({
    name: '',
    default_currency: 'USD',
    timezone: 'UTC',
    invoice_grace_period: 0,
    net_payment_term: 30,
  })

  const createMutation = useMutation({
    mutationFn: (data: OrganizationCreate) => organizationsApi.create(data),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['organization'] })
      setCreateOpen(false)
      setForm({ name: '', default_currency: 'USD', timezone: 'UTC', invoice_grace_period: 0, net_payment_term: 30 })
      setApiKeyDialog(response.api_key.raw_key)
      toast.success('Organization created')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to create organization'
      toast.error(message)
    },
  })

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(form)
  }

  const initials = org?.name
    ? org.name
        .split(' ')
        .map((w) => w[0])
        .join('')
        .slice(0, 2)
        .toUpperCase()
    : '?'

  if (isLoading) {
    return (
      <div className={cn('flex h-14 items-center gap-2.5 px-3', collapsed && 'justify-center')}>
        <Skeleton className="h-7 w-7 rounded-full shrink-0" />
        {!collapsed && <Skeleton className="h-4 w-24" />}
      </div>
    )
  }

  const avatar = (
    <Avatar className="h-7 w-7 shrink-0">
      {org?.logo_url && <AvatarImage src={org.logo_url} alt={org.name} />}
      <AvatarFallback className="text-[10px] font-semibold">
        {initials}
      </AvatarFallback>
    </Avatar>
  )

  return (
    <>
      <div className={cn('flex h-14 items-center px-3', collapsed ? 'justify-center' : 'justify-between')}>
        <div className={cn('flex items-center gap-2.5 min-w-0', collapsed && 'justify-center')}>
          {collapsed ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <div>{avatar}</div>
              </TooltipTrigger>
              <TooltipContent side="right">{org?.name ?? 'Organization'}</TooltipContent>
            </Tooltip>
          ) : (
            <>
              {avatar}
              <span className="text-sm font-semibold truncate text-foreground">
                {org?.name ?? 'Organization'}
              </span>
            </>
          )}
        </div>
        {!collapsed && (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0"
            onClick={() => setCreateOpen(true)}
          >
            <Plus className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Create Organization Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <form onSubmit={handleCreate}>
            <DialogHeader>
              <DialogTitle>Create Organization</DialogTitle>
              <DialogDescription>
                Set up a new organization with its own billing configuration
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="org-create-name">Name</Label>
                <Input
                  id="org-create-name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Acme Corp"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="org-create-currency">Currency</Label>
                  <Select
                    value={form.default_currency}
                    onValueChange={(v) => setForm({ ...form, default_currency: v })}
                  >
                    <SelectTrigger id="org-create-currency">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="USD">USD</SelectItem>
                      <SelectItem value="EUR">EUR</SelectItem>
                      <SelectItem value="GBP">GBP</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="org-create-timezone">Timezone</Label>
                  <Input
                    id="org-create-timezone"
                    value={form.timezone}
                    onChange={(e) => setForm({ ...form, timezone: e.target.value })}
                  />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* API Key Display */}
      <AlertDialog open={!!apiKeyDialog} onOpenChange={(open) => !open && setApiKeyDialog(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Organization Created</AlertDialogTitle>
            <AlertDialogDescription>
              Your initial API key has been generated. This key will only be shown once.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="my-4 rounded-md bg-muted p-4">
            <code className="text-sm font-mono break-all">{apiKeyDialog}</code>
          </div>
          <AlertDialogFooter>
            <AlertDialogAction
              onClick={() => {
                if (apiKeyDialog) {
                  navigator.clipboard.writeText(apiKeyDialog)
                  toast.success('API key copied to clipboard')
                }
                setApiKeyDialog(null)
              }}
            >
              <Copy className="mr-2 h-4 w-4" />
              Copy & Close
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
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
        'flex h-full flex-col border-r bg-sidebar transition-all duration-200',
        collapsed ? 'w-14' : 'w-56'
      )}
    >
      {/* Organization */}
      <TooltipProvider delayDuration={0}>
        <OrgHeader collapsed={collapsed} />
      </TooltipProvider>

      <Separator />

      {/* Navigation */}
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

      {/* Bottom: Settings + Collapse Toggle */}
      <div className="px-2 pb-2 border-t pt-2">
        <TooltipProvider delayDuration={0}>
          <NavItem
            item={{ name: 'Settings', href: '/admin/settings', icon: Settings }}
            collapsed={collapsed}
          />
        </TooltipProvider>
        <div className={cn('flex mt-1', collapsed ? 'justify-center' : 'justify-end')}>
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggle}
            className="h-7 w-7"
          >
            {collapsed ? (
              <PanelLeftOpen className="h-4 w-4" />
            ) : (
              <PanelLeftClose className="h-4 w-4" />
            )}
          </Button>
        </div>
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

function ThemeToggle() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light')

  useEffect(() => {
    const isDark = document.documentElement.classList.contains('dark')
    setTheme(isDark ? 'dark' : 'light')
  }, [])

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(newTheme)
    document.documentElement.classList.toggle('dark')
  }

  return (
    <Button variant="ghost" size="icon" onClick={toggleTheme} className="h-8 w-8">
      {theme === 'light' ? (
        <Moon className="h-4 w-4" />
      ) : (
        <Sun className="h-4 w-4" />
      )}
    </Button>
  )
}

export default function AdminLayout() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex h-screen bg-background">
      {/* Desktop Sidebar */}
      <div className="hidden md:flex">
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      </div>

      {/* Main Content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <header className="flex h-14 items-center justify-between border-b px-4 md:px-6">
          <MobileSidebar />
          <div className="flex items-center gap-2 ml-auto">
            <ThemeToggle />
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
