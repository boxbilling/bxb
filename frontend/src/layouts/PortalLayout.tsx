import { Outlet, NavLink, useSearchParams, useLocation } from 'react-router-dom'
import { useState, useEffect, createContext, useContext } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  FileText,
  BarChart3,
  ArrowLeftRight,
  Wallet,
  LayoutDashboard,
  ShieldX,
  Menu,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { portalApi } from '@/lib/api'
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'

const PortalTokenContext = createContext<string>('')

export function usePortalToken() {
  return useContext(PortalTokenContext)
}

const portalNavItems = [
  { name: 'Overview', href: '/portal', icon: LayoutDashboard },
  { name: 'Invoices', href: '/portal/invoices', icon: FileText },
  { name: 'Usage', href: '/portal/usage', icon: BarChart3 },
  { name: 'Payments', href: '/portal/payments', icon: ArrowLeftRight },
  { name: 'Wallet', href: '/portal/wallet', icon: Wallet },
]

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

function AccessDeniedPage() {
  return (
    <div className="flex h-screen items-center justify-center bg-background">
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

  const { data: customer, error } = useQuery({
    queryKey: ['portal-customer', token],
    queryFn: () => portalApi.getCustomer(token),
    enabled: !!token,
    retry: false,
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
      <div className="flex h-screen flex-col bg-background">
        {/* Top navigation bar */}
        <header className="border-b bg-background">
          <div className="flex h-14 items-center justify-between px-4 md:px-6">
            <div className="flex items-center gap-6">
              <span className="text-lg font-semibold">Customer Portal</span>
              <nav className="hidden md:flex items-center gap-1">
                <PortalNavLinks />
              </nav>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                {customer?.name}
              </span>
              {/* Mobile menu */}
              <Sheet>
                <SheetTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="md:hidden h-8 w-8"
                  >
                    <Menu className="h-4 w-4" />
                  </Button>
                </SheetTrigger>
                <SheetContent side="left" className="w-56 p-4">
                  <nav className="flex flex-col gap-1 mt-8">
                    <PortalNavLinks />
                  </nav>
                </SheetContent>
              </Sheet>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </PortalTokenContext.Provider>
  )
}
