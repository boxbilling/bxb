import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Users,
  FileText,
  RefreshCw,
  Layers,
  LayoutDashboard,
  Gauge,
  ToggleLeft,
  Activity,
  CircleDollarSign,
  ArrowLeftRight,
  FileMinus,
  CreditCard,
  Wallet,
  Percent,
  Puzzle,
  Calculator,
  Radio,
  Bell,
  AlertTriangle,
  Send,
  FileDown,
  Plug,
  ScrollText,
  Settings,
  Key,
  Building2,
} from 'lucide-react'
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandSeparator,
} from '@/components/ui/command'
import { searchApi, type SearchResult } from '@/lib/api'

const PAGES = [
  { name: 'Dashboard', href: '/admin', icon: LayoutDashboard },
  { name: 'Customers', href: '/admin/customers', icon: Users },
  { name: 'Billing Entities', href: '/admin/billing-entities', icon: Building2 },
  { name: 'Billable Metrics', href: '/admin/metrics', icon: Gauge },
  { name: 'Plans', href: '/admin/plans', icon: Layers },
  { name: 'Features', href: '/admin/features', icon: ToggleLeft },
  { name: 'Subscriptions', href: '/admin/subscriptions', icon: RefreshCw },
  { name: 'Events', href: '/admin/events', icon: Activity },
  { name: 'Invoices', href: '/admin/invoices', icon: FileText },
  { name: 'Fees', href: '/admin/fees', icon: CircleDollarSign },
  { name: 'Payments', href: '/admin/payments', icon: ArrowLeftRight },
  { name: 'Credit Notes', href: '/admin/credit-notes', icon: FileMinus },
  { name: 'Payment Methods', href: '/admin/payment-methods', icon: CreditCard },
  { name: 'Wallets', href: '/admin/wallets', icon: Wallet },
  { name: 'Coupons', href: '/admin/coupons', icon: Percent },
  { name: 'Add-ons', href: '/admin/add-ons', icon: Puzzle },
  { name: 'Taxes', href: '/admin/taxes', icon: Calculator },
  { name: 'Webhooks', href: '/admin/webhooks', icon: Radio },
  { name: 'Dunning Campaigns', href: '/admin/dunning-campaigns', icon: Bell },
  { name: 'Usage Alerts', href: '/admin/usage-alerts', icon: AlertTriangle },
  { name: 'Payment Requests', href: '/admin/payment-requests', icon: Send },
  { name: 'Data Exports', href: '/admin/data-exports', icon: FileDown },
  { name: 'Integrations', href: '/admin/integrations', icon: Plug },
  { name: 'Audit Logs', href: '/admin/audit-logs', icon: ScrollText },
  { name: 'Settings', href: '/admin/settings', icon: Settings },
  { name: 'API Keys', href: '/admin/api-keys', icon: Key },
]

const TYPE_ICONS: Record<string, React.ElementType> = {
  customer: Users,
  invoice: FileText,
  subscription: RefreshCw,
  plan: Layers,
}

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setOpen((prev) => !prev)
      }
    }
    document.addEventListener('keydown', down)
    return () => document.removeEventListener('keydown', down)
  }, [])

  const { data: searchResults } = useQuery({
    queryKey: ['global-search', query],
    queryFn: () => searchApi.search(query, 5),
    enabled: query.length >= 2,
    staleTime: 30_000,
  })

  const handleSelect = useCallback(
    (url: string) => {
      setOpen(false)
      setQuery('')
      navigate(url)
    },
    [navigate]
  )

  const filteredPages = query
    ? PAGES.filter((p) => p.name.toLowerCase().includes(query.toLowerCase()))
    : PAGES

  return (
    <CommandDialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v)
        if (!v) setQuery('')
      }}
      title="Search"
      description="Search for pages, customers, invoices, and more"
    >
      <CommandInput
        placeholder="Search pages, customers, invoices..."
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        {searchResults && searchResults.length > 0 && (
          <>
            <CommandGroup heading="Results">
              {searchResults.map((result: SearchResult) => {
                const Icon = TYPE_ICONS[result.type] || FileText
                return (
                  <CommandItem
                    key={`${result.type}-${result.id}`}
                    value={`${result.title} ${result.subtitle ?? ''}`}
                    onSelect={() => handleSelect(result.url)}
                  >
                    <Icon className="mr-2 h-4 w-4 text-muted-foreground" />
                    <div className="flex flex-col">
                      <span>{result.title}</span>
                      {result.subtitle && (
                        <span className="text-xs text-muted-foreground">{result.subtitle}</span>
                      )}
                    </div>
                  </CommandItem>
                )
              })}
            </CommandGroup>
            <CommandSeparator />
          </>
        )}

        <CommandGroup heading="Pages">
          {filteredPages.map((page) => (
            <CommandItem
              key={page.href}
              value={page.name}
              onSelect={() => handleSelect(page.href)}
            >
              <page.icon className="mr-2 h-4 w-4 text-muted-foreground" />
              {page.name}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  )
}
