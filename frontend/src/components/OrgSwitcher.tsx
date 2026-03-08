import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'
import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { Organization } from '@/lib/api'
import { useOrganization } from '@/hooks/use-organization'

function getInitials(name?: string) {
  if (!name) return '?'
  return name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

function OrgAvatar({ org, className }: { org?: Organization | null; className?: string }) {
  return (
    <Avatar className={cn('h-6 w-6 shrink-0', className)}>
      {org?.logo_url && <AvatarImage src={org.logo_url} alt={org.name} />}
      <AvatarFallback className="text-[9px] font-semibold">
        {getInitials(org?.name)}
      </AvatarFallback>
    </Avatar>
  )
}

export default function OrgSwitcher({ collapsed }: { collapsed: boolean }) {
  const { data: currentOrg, isLoading } = useOrganization()

  if (isLoading) {
    return (
      <div className={cn('flex h-full items-center gap-2.5 px-3', collapsed && 'justify-center')}>
        <Skeleton className="h-6 w-6 rounded-full shrink-0" />
        {!collapsed && <Skeleton className="h-4 w-24" />}
      </div>
    )
  }

  if (collapsed) {
    return (
      <div className="flex h-full items-center justify-center px-3">
        <Tooltip>
          <TooltipTrigger asChild>
            <div><OrgAvatar org={currentOrg} /></div>
          </TooltipTrigger>
          <TooltipContent side="right">{currentOrg?.name ?? 'Organization'}</TooltipContent>
        </Tooltip>
      </div>
    )
  }

  return (
    <div className="flex h-full w-full items-center gap-2.5 px-3">
      <OrgAvatar org={currentOrg} />
      <span className="flex-1 text-sm font-semibold truncate text-foreground">
        {currentOrg?.name ?? 'Organization'}
      </span>
    </div>
  )
}
