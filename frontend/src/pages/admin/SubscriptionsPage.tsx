import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, MoreHorizontal, XCircle, ExternalLink } from 'lucide-react'
import { toast } from 'sonner'
import { format } from 'date-fns'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
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
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import type { Subscription, SubscriptionCreate, SubscriptionStatus, Customer, Plan } from '@/types/billing'

// Mock data
const mockCustomers: Customer[] = [
  { id: '1', external_id: 'cust_001', name: 'Acme Corporation', email: 'billing@acme.com', phone: null, address_line1: null, address_line2: null, city: 'San Francisco', state: 'CA', postal_code: '94102', country: 'US', currency: 'USD', timezone: 'America/Los_Angeles', metadata: {}, created_at: '', updated_at: '' },
  { id: '2', external_id: 'cust_002', name: 'TechStart Inc', email: 'accounts@techstart.io', phone: null, address_line1: null, address_line2: null, city: 'New York', state: 'NY', postal_code: '10001', country: 'US', currency: 'USD', timezone: 'America/New_York', metadata: {}, created_at: '', updated_at: '' },
  { id: '3', external_id: 'cust_003', name: 'CloudNine Ltd', email: 'hello@cloudnine.co.uk', phone: null, address_line1: null, address_line2: null, city: 'London', state: null, postal_code: 'SW1A 2AA', country: 'GB', currency: 'GBP', timezone: 'Europe/London', metadata: {}, created_at: '', updated_at: '' },
]

const mockPlans: Plan[] = [
  { id: '1', code: 'starter', name: 'Starter', description: null, amount_cents: 2900, amount_currency: 'USD', interval: 'monthly', pay_in_advance: true, trial_period_days: 14, charges: [], active_subscriptions_count: 45, created_at: '', updated_at: '' },
  { id: '2', code: 'pro', name: 'Professional', description: null, amount_cents: 9900, amount_currency: 'USD', interval: 'monthly', pay_in_advance: true, trial_period_days: null, charges: [], active_subscriptions_count: 128, created_at: '', updated_at: '' },
  { id: '3', code: 'enterprise', name: 'Enterprise', description: null, amount_cents: 49900, amount_currency: 'USD', interval: 'monthly', pay_in_advance: true, trial_period_days: null, charges: [], active_subscriptions_count: 12, created_at: '', updated_at: '' },
]

const mockSubscriptions: Subscription[] = [
  {
    id: '1',
    external_id: 'sub_001',
    customer_id: '1',
    customer: mockCustomers[0],
    plan_id: '2',
    plan: mockPlans[1],
    status: 'active',
    billing_time: 'calendar',
    started_at: '2024-01-15T00:00:00Z',
    ending_at: null,
    canceled_at: null,
    terminated_at: null,
    created_at: '2024-01-15T00:00:00Z',
    updated_at: '2024-01-15T00:00:00Z',
  },
  {
    id: '2',
    external_id: 'sub_002',
    customer_id: '2',
    customer: mockCustomers[1],
    plan_id: '1',
    plan: mockPlans[0],
    status: 'active',
    billing_time: 'anniversary',
    started_at: '2024-02-01T00:00:00Z',
    ending_at: null,
    canceled_at: null,
    terminated_at: null,
    created_at: '2024-02-01T00:00:00Z',
    updated_at: '2024-02-01T00:00:00Z',
  },
  {
    id: '3',
    external_id: 'sub_003',
    customer_id: '3',
    customer: mockCustomers[2],
    plan_id: '3',
    plan: mockPlans[2],
    status: 'canceled',
    billing_time: 'calendar',
    started_at: '2023-06-01T00:00:00Z',
    ending_at: '2024-06-01T00:00:00Z',
    canceled_at: '2024-05-15T00:00:00Z',
    terminated_at: null,
    created_at: '2023-06-01T00:00:00Z',
    updated_at: '2024-05-15T00:00:00Z',
  },
]

function formatCurrency(cents: number, currency: string = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(cents / 100)
}

function StatusBadge({ status }: { status: SubscriptionStatus }) {
  const variants: Record<SubscriptionStatus, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string }> = {
    pending: { variant: 'secondary', label: 'Pending' },
    active: { variant: 'default', label: 'Active' },
    canceled: { variant: 'outline', label: 'Canceled' },
    terminated: { variant: 'destructive', label: 'Terminated' },
  }

  const config = variants[status]
  return <Badge variant={config.variant}>{config.label}</Badge>
}

function SubscriptionFormDialog({
  open,
  onOpenChange,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: SubscriptionCreate) => void
  isLoading: boolean
}) {
  const [formData, setFormData] = useState<SubscriptionCreate>({
    external_id: '',
    customer_id: '',
    plan_id: '',
    billing_time: 'calendar',
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(formData)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create Subscription</DialogTitle>
            <DialogDescription>
              Subscribe a customer to a plan
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="external_id">External ID *</Label>
              <Input
                id="external_id"
                value={formData.external_id}
                onChange={(e) =>
                  setFormData({ ...formData, external_id: e.target.value })
                }
                placeholder="sub_123"
                required
              />
            </div>

            <div className="space-y-2">
              <Label>Customer *</Label>
              <Select
                value={formData.customer_id}
                onValueChange={(value) =>
                  setFormData({ ...formData, customer_id: value })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a customer" />
                </SelectTrigger>
                <SelectContent>
                  {mockCustomers.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Plan *</Label>
              <Select
                value={formData.plan_id}
                onValueChange={(value) =>
                  setFormData({ ...formData, plan_id: value })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a plan" />
                </SelectTrigger>
                <SelectContent>
                  {mockPlans.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name} — {formatCurrency(p.amount_cents, p.amount_currency)}/{p.interval}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Billing Time</Label>
              <Select
                value={formData.billing_time}
                onValueChange={(value: 'calendar' | 'anniversary') =>
                  setFormData({ ...formData, billing_time: value })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="calendar">Calendar (1st of month)</SelectItem>
                  <SelectItem value="anniversary">Anniversary (subscription start date)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? 'Creating...' : 'Create Subscription'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function SubscriptionsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [formOpen, setFormOpen] = useState(false)
  const [terminateSub, setTerminateSub] = useState<Subscription | null>(null)

  // Fetch subscriptions
  const { data, isLoading } = useQuery({
    queryKey: ['subscriptions', { search, statusFilter }],
    queryFn: async () => {
      await new Promise((r) => setTimeout(r, 500))
      let filtered = mockSubscriptions
      if (statusFilter !== 'all') {
        filtered = filtered.filter((s) => s.status === statusFilter)
      }
      if (search) {
        filtered = filtered.filter(
          (s) =>
            s.customer?.name.toLowerCase().includes(search.toLowerCase()) ||
            s.plan?.name.toLowerCase().includes(search.toLowerCase()) ||
            s.external_id.toLowerCase().includes(search.toLowerCase())
        )
      }
      return {
        data: filtered,
        meta: { total: filtered.length, page: 1, per_page: 10, total_pages: 1 },
      }
    },
  })

  // Create mutation
  const createMutation = useMutation({
    mutationFn: async (data: SubscriptionCreate) => {
      await new Promise((r) => setTimeout(r, 500))
      return { ...data, id: String(Date.now()), status: 'active' as const } as Subscription
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      setFormOpen(false)
      toast.success('Subscription created successfully')
    },
    onError: () => {
      toast.error('Failed to create subscription')
    },
  })

  // Terminate mutation
  const terminateMutation = useMutation({
    mutationFn: async (id: string) => {
      await new Promise((r) => setTimeout(r, 500))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      setTerminateSub(null)
      toast.success('Subscription terminated')
    },
    onError: () => {
      toast.error('Failed to terminate subscription')
    },
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Subscriptions</h2>
          <p className="text-muted-foreground">
            Manage customer subscriptions
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Subscription
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search subscriptions..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="canceled">Canceled</SelectItem>
            <SelectItem value="terminated">Terminated</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Customer</TableHead>
              <TableHead>Plan</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Started</TableHead>
              <TableHead>Billing</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [...Array(5)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-40" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-8" /></TableCell>
                </TableRow>
              ))
            ) : data?.data.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="h-24 text-center">
                  No subscriptions found
                </TableCell>
              </TableRow>
            ) : (
              data?.data.map((sub) => (
                <TableRow key={sub.id}>
                  <TableCell>
                    <div>
                      <div className="font-medium">{sub.customer?.name}</div>
                      <code className="text-xs text-muted-foreground">
                        {sub.external_id}
                      </code>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div>
                      <div>{sub.plan?.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {sub.plan && formatCurrency(sub.plan.amount_cents, sub.plan.amount_currency)}/{sub.plan?.interval}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={sub.status} />
                  </TableCell>
                  <TableCell>
                    {format(new Date(sub.started_at), 'MMM d, yyyy')}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {sub.billing_time === 'calendar' ? 'Calendar' : 'Anniversary'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem>
                          <ExternalLink className="mr-2 h-4 w-4" />
                          View Details
                        </DropdownMenuItem>
                        {sub.status === 'active' && (
                          <DropdownMenuItem
                            onClick={() => setTerminateSub(sub)}
                            className="text-destructive"
                          >
                            <XCircle className="mr-2 h-4 w-4" />
                            Terminate
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Create Dialog */}
      <SubscriptionFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={(data) => createMutation.mutate(data)}
        isLoading={createMutation.isPending}
      />

      {/* Terminate Confirmation */}
      <AlertDialog
        open={!!terminateSub}
        onOpenChange={(open) => !open && setTerminateSub(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Terminate Subscription</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to terminate the subscription for "
              {terminateSub?.customer?.name}"? This will end their access
              immediately.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                terminateSub && terminateMutation.mutate(terminateSub.id)
              }
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {terminateMutation.isPending ? 'Terminating...' : 'Terminate'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
