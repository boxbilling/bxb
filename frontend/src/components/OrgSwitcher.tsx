import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Copy, Check, ChevronsUpDown } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
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
import { organizationsApi, ApiError, setActiveOrganizationId } from '@/lib/api'
import type { Organization, OrganizationCreate } from '@/types/billing'
import { useOrganization } from '@/hooks/use-organization'

const DEFAULT_FORM: OrganizationCreate = {
  name: '',
  default_currency: 'USD',
  timezone: 'UTC',
}

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
  const queryClient = useQueryClient()
  const [popoverOpen, setPopoverOpen] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [apiKeyDialog, setApiKeyDialog] = useState<string | null>(null)
  const [form, setForm] = useState<OrganizationCreate>({ ...DEFAULT_FORM })

  const { data: orgs = [] } = useQuery({
    queryKey: ['organizations'],
    queryFn: () => organizationsApi.list(),
    enabled: popoverOpen,
  })

  const createMutation = useMutation({
    mutationFn: (data: OrganizationCreate) => organizationsApi.create(data),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['organization'] })
      queryClient.invalidateQueries({ queryKey: ['organizations'] })
      setCreateOpen(false)
      setForm({ ...DEFAULT_FORM })
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
    <>
      <Popover open={popoverOpen} onOpenChange={setPopoverOpen}>
        <PopoverTrigger asChild>
          <button
            className="flex h-full w-full items-center gap-2.5 px-3 text-left hover:bg-accent/50 transition-colors"
          >
            <OrgAvatar org={currentOrg} />
            <span className="flex-1 text-sm font-semibold truncate text-foreground">
              {currentOrg?.name ?? 'Organization'}
            </span>
            <ChevronsUpDown className="h-4 w-4 shrink-0 text-muted-foreground" />
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-56 p-1" align="start" side="right">
          <div className="px-2 py-1.5">
            <p className="text-xs font-medium text-muted-foreground">Organizations</p>
          </div>
          <div className="max-h-48 overflow-y-auto">
            {orgs.map((org) => (
              <button
                key={org.id}
                className={cn(
                  'flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent transition-colors',
                  org.id === currentOrg?.id && 'bg-accent'
                )}
                onClick={() => {
                  setActiveOrganizationId(org.id)
                  setPopoverOpen(false)
                  queryClient.invalidateQueries()
                }}
              >
                <OrgAvatar org={org} className="h-5 w-5" />
                <span className="flex-1 truncate">{org.name}</span>
                {org.id === currentOrg?.id && (
                  <Check className="h-4 w-4 shrink-0 text-foreground" />
                )}
              </button>
            ))}
          </div>
          <Separator className="my-1" />
          <button
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent transition-colors"
            onClick={() => {
              setPopoverOpen(false)
              setCreateOpen(true)
            }}
          >
            <Plus className="h-4 w-4" />
            <span>Create organization</span>
          </button>
        </PopoverContent>
      </Popover>

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
