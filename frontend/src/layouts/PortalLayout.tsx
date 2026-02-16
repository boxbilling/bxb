import { Outlet, NavLink, useSearchParams, useLocation } from 'react-router-dom'
import { useState, useEffect, useMemo, createContext, useContext } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  FileText,
  BarChart3,
  ArrowLeftRight,
  ArrowUpDown,
  Wallet,
  LayoutDashboard,
  ShieldX,
  UserCog,
  CreditCard,
  Package,
  Tag,
  MoreHorizontal,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { portalApi } from '@/lib/api'
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { useIsMobile } from '@/hooks/use-mobile'
import type { PortalBranding } from '@/types/billing'

const PortalTokenContext = createContext<string>('')
const PortalBrandingContext = createContext<PortalBranding | null>(null)

export function usePortalToken() {
  return useContext(PortalTokenContext)
}

export function usePortalBranding() {
  return useContext(PortalBrandingContext)
}

const portalNavItems = [
  { name: 'Overview', href: '/portal', icon: LayoutDashboard },
  { name: 'Subscriptions', href: '/portal/subscriptions', icon: ArrowUpDown },
  { name: 'Invoices', href: '/portal/invoices', icon: FileText },
  { name: 'Usage', href: '/portal/usage', icon: BarChart3 },
  { name: 'Payments', href: '/portal/payments', icon: ArrowLeftRight },
  { name: 'Wallet', href: '/portal/wallet', icon: Wallet },
  { name: 'Payment Methods', href: '/portal/payment-methods', icon: CreditCard },
  { name: 'Add-ons', href: '/portal/add-ons', icon: Package },
  { name: 'Coupons', href: '/portal/coupons', icon: Tag },
  { name: 'Profile', href: '/portal/profile', icon: UserCog },
]

// Primary nav items shown in the bottom tab bar on mobile (max 5 slots, 4 + More)
const mobileBottomNavItems = portalNavItems.slice(0, 4)
const mobileOverflowItems = portalNavItems.slice(4)

function PortalNavLinks({ onClick }: { onClick?: () => void }) {
  const location = useLocation()

  return (
    <>
      {portalNavItems.map((item) => {
        const isActive =
          item.href === '/portal'
            ? location.pathname === '/portal'
            : location.pathname.startsWith(item.href)

        return (
          <NavLink
            key={item.href}
            to={item.href}
            onClick={onClick}
            className={cn(
              'flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
            )}
          >
            <item.icon className="h-4 w-4" />
            <span>{item.name}</span>
          </NavLink>
        )
      })}
    </>
  )
}

function MobileBottomNav() {
  const location = useLocation()
  const [moreOpen, setMoreOpen] = useState(false)

  const isOverflowActive = mobileOverflowItems.some((item) =>
    item.href === '/portal'
      ? location.pathname === '/portal'
      : location.pathname.startsWith(item.href)
  )

  return (
    <nav className="md:hidden border-t bg-background">
      <div className="flex items-stretch justify-around">
        {mobileBottomNavItems.map((item) => {
          const isActive =
            item.href === '/portal'
              ? location.pathname === '/portal'
              : location.pathname.startsWith(item.href)

          return (
            <NavLink
              key={item.href}
              to={item.href}
              className={cn(
                'flex flex-1 flex-col items-center justify-center gap-0.5 py-2 min-h-[56px] text-[10px] font-medium transition-colors',
                isActive
                  ? 'text-primary'
                  : 'text-muted-foreground'
              )}
            >
              <item.icon className="h-5 w-5" />
              <span className="truncate max-w-[64px]">{item.name}</span>
            </NavLink>
          )
        })}
        {/* More button */}
        <Sheet open={moreOpen} onOpenChange={setMoreOpen}>
          <SheetTrigger asChild>
            <button
              className={cn(
                'flex flex-1 flex-col items-center justify-center gap-0.5 py-2 min-h-[56px] text-[10px] font-medium transition-colors',
                isOverflowActive
                  ? 'text-primary'
                  : 'text-muted-foreground'
              )}
            >
              <MoreHorizontal className="h-5 w-5" />
              <span>More</span>
            </button>
          </SheetTrigger>
          <SheetContent side="bottom" className="rounded-t-xl pb-safe">
            <SheetTitle className="px-4 pt-2">More</SheetTitle>
            <nav className="grid grid-cols-3 gap-2 px-4 pb-4 pt-2">
              {mobileOverflowItems.map((item) => {
                const isActive =
                  item.href === '/portal'
                    ? location.pathname === '/portal'
                    : location.pathname.startsWith(item.href)

                return (
                  <NavLink
                    key={item.href}
                    to={item.href}
                    onClick={() => setMoreOpen(false)}
                    className={cn(
                      'flex flex-col items-center gap-1.5 rounded-lg p-3 min-h-[72px] text-xs font-medium transition-colors',
                      isActive
                        ? 'bg-primary/10 text-primary'
                        : 'text-muted-foreground hover:bg-accent'
                    )}
                  >
                    <item.icon className="h-6 w-6" />
                    <span className="text-center leading-tight">{item.name}</span>
                  </NavLink>
                )
              })}
            </nav>
          </SheetContent>
        </Sheet>
      </div>
    </nav>
  )
}

function AccessDeniedPage() {
  return (
    <div className="flex h-screen items-center justify-center bg-background px-4">
      <div className="text-center space-y-4">
        <ShieldX className="h-16 w-16 mx-auto text-muted-foreground" />
        <h1 className="text-2xl font-bold">Access Denied</h1>
        <p className="text-muted-foreground max-w-sm">
          This portal link is invalid or has expired. Please request a new link
          from your account administrator.
        </p>
      </div>
    </div>
  )
}

export default function PortalLayout() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [authorized, setAuthorized] = useState<boolean | null>(null)
  const isMobile = useIsMobile()

  const { data: customer, error } = useQuery({
    queryKey: ['portal-customer', token],
    queryFn: () => portalApi.getCustomer(token),
    enabled: !!token,
    retry: false,
  })

  const { data: branding } = useQuery({
    queryKey: ['portal-branding', token],
    queryFn: () => portalApi.getBranding(token),
    enabled: !!token,
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    if (!token) {
      setAuthorized(false)
      return
    }
    if (error) {
      setAuthorized(false)
      return
    }
    if (customer) {
      setAuthorized(true)
    }
  }, [token, customer, error])

  const accentStyle = useMemo(() => {
    if (!branding?.accent_color) return undefined
    return { '--portal-accent': branding.accent_color } as React.CSSProperties
  }, [branding?.accent_color])

  if (!token || authorized === false) {
    return <AccessDeniedPage />
  }

  if (authorized === null) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    )
  }

  return (
    <PortalTokenContext.Provider value={token}>
      <PortalBrandingContext.Provider value={branding ?? null}>
        <div className="flex h-screen flex-col bg-background" style={accentStyle}>
          {/* Top navigation bar */}
          <header
            className="border-b"
            style={branding?.accent_color ? { backgroundColor: branding.accent_color + '0d' } : undefined}
          >
            <div className="flex h-14 items-center justify-between px-4 md:px-6">
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                  {branding?.logo_url ? (
                    <img
                      src={branding.logo_url}
                      alt={`${branding.name} logo`}
                      className="h-7 w-7 rounded object-contain"
                    />
                  ) : null}
                  <span className="text-base md:text-lg font-semibold truncate max-w-[180px] md:max-w-none">
                    {branding?.name ?? 'Customer Portal'}
                  </span>
                </div>
                <nav className="hidden md:flex items-center gap-1">
                  <PortalNavLinks />
                </nav>
              </div>
              <div className="flex items-center gap-2">
                <span className="hidden md:inline text-sm text-muted-foreground">
                  {customer?.name}
                </span>
              </div>
            </div>
          </header>

          <main className={cn(
            'flex-1 overflow-y-auto p-4 md:p-6',
            isMobile && 'pb-4'
          )}>
            <Outlet />
          </main>

          {/* Mobile bottom navigation bar */}
          <MobileBottomNav />
        </div>
      </PortalBrandingContext.Provider>
    </PortalTokenContext.Provider>
  )
}
