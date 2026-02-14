import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Copy } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
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

const DEFAULT_FORM: OrganizationCreate = {
  name: '',
  default_currency: 'USD',
  timezone: 'UTC',
  invoice_grace_period: 0,
  net_payment_term: 30,
}

export default function OrgSwitcher({ collapsed }: { collapsed: boolean }) {
  const { data: org, isLoading } = useOrganization()
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [apiKeyDialog, setApiKeyDialog] = useState<string | null>(null)
  const [form, setForm] = useState<OrganizationCreate>({ ...DEFAULT_FORM })

  const createMutation = useMutation({
    mutationFn: (data: OrganizationCreate) => organizationsApi.create(data),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['organization'] })
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
