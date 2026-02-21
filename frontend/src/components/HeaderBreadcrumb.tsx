import { Link, useLocation } from 'react-router-dom'
import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'

type RouteLabels = Record<string, string>

const BreadcrumbContext = createContext<RouteLabels>({})

export type BreadcrumbCrumb = { label: string | React.ReactNode; href?: string }

type PageBreadcrumbState = {
  crumbs: BreadcrumbCrumb[]
  setCrumbs: (crumbs: BreadcrumbCrumb[]) => void
}

const PageBreadcrumbContext = createContext<PageBreadcrumbState>({
  crumbs: [],
  setCrumbs: () => {},
})

export function PageBreadcrumbProvider({ children }: { children: React.ReactNode }) {
  const [crumbs, setCrumbs] = useState<BreadcrumbCrumb[]>([])
  return (
    <PageBreadcrumbContext.Provider value={{ crumbs, setCrumbs }}>
      {children}
    </PageBreadcrumbContext.Provider>
  )
}

export function useSetBreadcrumbs(crumbs: BreadcrumbCrumb[]) {
  const { setCrumbs } = useContext(PageBreadcrumbContext)
  useEffect(() => {
    setCrumbs(crumbs)
    return () => setCrumbs([])
  }, [setCrumbs, ...crumbs.map((c) => (typeof c.label === 'string' ? c.label : '')), ...crumbs.map((c) => c.href ?? '')])
}

export function BreadcrumbProvider({
  routeLabels,
  children,
}: {
  routeLabels: RouteLabels
  children: React.ReactNode
}) {
  return (
    <BreadcrumbContext.Provider value={routeLabels}>
      {children}
    </BreadcrumbContext.Provider>
  )
}

export function MobilePageTitle() {
  const routeLabels = useContext(BreadcrumbContext)
  const { crumbs: pageCrumbs } = useContext(PageBreadcrumbContext)
  const location = useLocation()

  const label = useMemo(() => {
    if (pageCrumbs.length > 0) {
      const lastCrumb = pageCrumbs[pageCrumbs.length - 1]
      const firstCrumb = pageCrumbs[0]
      if (pageCrumbs.length === 1) {
        return typeof firstCrumb.label === 'string' ? firstCrumb.label : null
      }
      const parentLabel = typeof firstCrumb.label === 'string' ? firstCrumb.label : ''
      const childLabel = typeof lastCrumb.label === 'string' ? lastCrumb.label : ''
      return `${parentLabel} — ${childLabel}`
    }

    const path = location.pathname
    if (path === '/admin') return null

    const segments = path.replace(/^\/admin\/?/, '').split('/')
    const parentPath = '/admin/' + segments[0]
    const parentLabel = routeLabels[parentPath]
    if (!parentLabel) return null

    if (segments.length > 1) {
      const sub = segments.slice(1).join('/')
      const subLabel = sub === 'new' ? 'New' : sub === 'edit' ? 'Edit' : 'Detail'
      return `${parentLabel} — ${subLabel}`
    }
    return parentLabel
  }, [location.pathname, routeLabels, pageCrumbs])

  if (!label) return null

  return (
    <span className="text-sm font-medium truncate text-foreground">
      {label}
    </span>
  )
}

export default function HeaderBreadcrumb() {
  const routeLabels = useContext(BreadcrumbContext)
  const { crumbs: pageCrumbs } = useContext(PageBreadcrumbContext)
  const location = useLocation()

  const crumbs = useMemo((): BreadcrumbCrumb[] => {
    if (pageCrumbs.length > 0) return pageCrumbs

    const path = location.pathname
    if (path === '/admin') return []

    const segments = path.replace(/^\/admin\/?/, '').split('/')
    const result: BreadcrumbCrumb[] = []

    const parentPath = '/admin/' + segments[0]
    const parentLabel = routeLabels[parentPath]
    if (parentLabel) {
      if (segments.length > 1) {
        result.push({ label: parentLabel, href: parentPath })
        const sub = segments.slice(1).join('/')
        const subLabel = sub === 'new' ? 'New' : sub === 'edit' ? 'Edit' : 'Detail'
        result.push({ label: subLabel })
      } else {
        result.push({ label: parentLabel })
      }
    }

    return result
  }, [location.pathname, routeLabels, pageCrumbs])

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
