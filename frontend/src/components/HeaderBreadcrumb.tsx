import { Link, useLocation } from 'react-router-dom'
import { createContext, useContext, useMemo } from 'react'
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

export default function HeaderBreadcrumb() {
  const routeLabels = useContext(BreadcrumbContext)
  const location = useLocation()

  const crumbs = useMemo(() => {
    const path = location.pathname
    if (path === '/admin') return []

    const segments = path.replace(/^\/admin\/?/, '').split('/')
    const result: { label: string; href?: string }[] = []

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
  }, [location.pathname, routeLabels])

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
