import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  Eye,
  Search,
  MoreHorizontal,
  Pencil,
  Trash2,
  Megaphone,
  Mail,
  AlertTriangle,
  TrendingUp,
  DollarSign,
  CheckCircle,
} from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'

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
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { TablePagination } from '@/components/TablePagination'
import { SortableTableHead, useSortState } from '@/components/SortableTableHead'
import PageHeader from '@/components/PageHeader'
import { dunningCampaignsApi, ApiError } from '@/lib/api'
import { formatCents } from '@/lib/utils'
import type {
  DunningCampaign,
  DunningCampaignCreate,
  DunningCampaignUpdate,
} from '@/lib/api'

// --- Create/Edit Dunning Campaign Dialog ---
function DunningCampaignFormDialog({
  open,
  onOpenChange,
  campaign,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  campaign?: DunningCampaign | null
  onSubmit: (data: DunningCampaignCreate | DunningCampaignUpdate) => void
  isLoading: boolean
}) {
  const [formData, setFormData] = useState<{
    code: string
    name: string
    description: string
    max_attempts: string
    days_between_attempts: string
    bcc_emails: string
    status: string
    thresholds: Array<{ currency: string; amount_cents: string }>
  }>({
    code: campaign?.code ?? '',
    name: campaign?.name ?? '',
    description: campaign?.description ?? '',
    max_attempts: campaign?.max_attempts?.toString() ?? '3',
    days_between_attempts: campaign?.days_between_attempts?.toString() ?? '1',
    bcc_emails: campaign?.bcc_emails?.join(', ') ?? '',
    status: campaign?.status ?? 'active',
    thresholds:
      campaign?.thresholds?.map((t) => ({
        currency: t.currency,
        amount_cents: t.amount_cents.toString(),
      })) ?? [],
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const parsedBccEmails = formData.bcc_emails
      .split(',')
      .map((e) => e.trim())
      .filter(Boolean)
    const parsedThresholds = formData.thresholds.map((t) => ({
      currency: t.currency,
      amount_cents: parseInt(t.amount_cents, 10),
    }))

    if (campaign) {
      const update: DunningCampaignUpdate = {
        name: formData.name || null,
        description: formData.description || null,
        max_attempts: parseInt(formData.max_attempts, 10),
        days_between_attempts: parseInt(formData.days_between_attempts, 10),
        bcc_emails: parsedBccEmails,
        status: formData.status,
        thresholds: parsedThresholds,
      }
      onSubmit(update)
    } else {
      const create: DunningCampaignCreate = {
        code: formData.code,
        name: formData.name,
        max_attempts: parseInt(formData.max_attempts, 10),
        days_between_attempts: parseInt(formData.days_between_attempts, 10),
        bcc_emails: parsedBccEmails,
        status: formData.status,
        thresholds: parsedThresholds,
      }
      if (formData.description) create.description = formData.description
      onSubmit(create)
    }
  }

  const addThreshold = () => {
    setFormData({
      ...formData,
      thresholds: [
        ...formData.thresholds,
        { currency: 'USD', amount_cents: '' },
      ],
    })
  }

  const removeThreshold = (index: number) => {
    setFormData({
      ...formData,
      thresholds: formData.thresholds.filter((_, i) => i !== index),
    })
  }

  const updateThreshold = (
    index: number,
    field: 'currency' | 'amount_cents',
    value: string
  ) => {
    const updated = [...formData.thresholds]
    updated[index] = { ...updated[index], [field]: value }
    setFormData({ ...formData, thresholds: updated })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {campaign ? 'Edit Dunning Campaign' : 'Create Dunning Campaign'}
            </DialogTitle>
            <DialogDescription>
              {campaign
                ? 'Update dunning campaign settings'
                : 'Define a new automated payment collection campaign'}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="code">Code *</Label>
                <Input
                  id="code"
                  value={formData.code}
                  onChange={(e) =>
                    setFormData({ ...formData, code: e.target.value })
                  }
                  placeholder="e.g. retry_standard"
                  disabled={!!campaign}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="name">Name *</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  placeholder="e.g. Standard Retry"
                  required
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                placeholder="Optional description"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="max_attempts">Max Attempts</Label>
                <Input
                  id="max_attempts"
                  type="number"
                  value={formData.max_attempts}
                  onChange={(e) =>
                    setFormData({ ...formData, max_attempts: e.target.value })
                  }
                  min="1"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="days_between_attempts">Days Between</Label>
                <Input
                  id="days_between_attempts"
                  type="number"
                  value={formData.days_between_attempts}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      days_between_attempts: e.target.value,
                    })
                  }
                  min="1"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="bcc_emails">BCC Emails</Label>
              <Input
                id="bcc_emails"
                value={formData.bcc_emails}
                onChange={(e) =>
                  setFormData({ ...formData, bcc_emails: e.target.value })
                }
                placeholder="Comma-separated emails"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="status">Status</Label>
              <Select
                value={formData.status}
                onValueChange={(value) =>
                  setFormData({ ...formData, status: value })
                }
              >
                <SelectTrigger id="status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Thresholds */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>Thresholds</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addThreshold}
                >
                  <Plus className="mr-1 h-3 w-3" />
                  Add Threshold
                </Button>
              </div>
              {formData.thresholds.map((threshold, index) => (
                <div key={index} className="flex flex-col sm:flex-row sm:items-center gap-2">
                  <Select
                    value={threshold.currency}
                    onValueChange={(value) =>
                      updateThreshold(index, 'currency', value)
                    }
                  >
                    <SelectTrigger className="w-full sm:w-[100px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="USD">USD</SelectItem>
                      <SelectItem value="EUR">EUR</SelectItem>
                      <SelectItem value="GBP">GBP</SelectItem>
                    </SelectContent>
                  </Select>
                  <Input
                    type="number"
                    placeholder="Amount in cents"
                    value={threshold.amount_cents}
                    onChange={(e) =>
                      updateThreshold(index, 'amount_cents', e.target.value)
                    }
                    className="flex-1"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => removeThreshold(index)}
                    className="self-end sm:self-auto"
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              ))}
            </div>
          </div>
          <DialogFooter className="flex-col-reverse sm:flex-row">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              className="w-full sm:w-auto"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={
                isLoading ||
                (!campaign && (!formData.code || !formData.name))
              }
              className="w-full sm:w-auto"
            >
              {isLoading
                ? 'Saving...'
                : campaign
                  ? 'Update'
                  : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

const PAGE_SIZE = 20

export default function DunningCampaignsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)
  const { sort, setSort, orderBy } = useSortState()
  const [formOpen, setFormOpen] = useState(false)
  const [editingCampaign, setEditingCampaign] =
    useState<DunningCampaign | null>(null)
  const [deleteCampaign, setDeleteCampaign] =
    useState<DunningCampaign | null>(null)

  // Fetch dunning campaigns
  const {
    data,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['dunning-campaigns', page, pageSize, orderBy],
    queryFn: () => dunningCampaignsApi.listPaginated({ skip: (page - 1) * pageSize, limit: pageSize, order_by: orderBy }),
  })
  const campaigns = data?.data ?? []
  const totalCount = data?.totalCount ?? 0

  // Fetch performance stats
  const { data: perfStats } = useQuery({
    queryKey: ['dunning-campaigns-performance-stats'],
    queryFn: () => dunningCampaignsApi.performanceStats(),
  })

  // Filter campaigns
  const filteredCampaigns = campaigns.filter((c) => {
    const matchesSearch =
      !search ||
      c.code.toLowerCase().includes(search.toLowerCase()) ||
      c.name.toLowerCase().includes(search.toLowerCase())
    const matchesStatus =
      statusFilter === 'all' || c.status === statusFilter
    return matchesSearch && matchesStatus
  })

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: DunningCampaignCreate) =>
      dunningCampaignsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dunning-campaigns'] })
      queryClient.invalidateQueries({ queryKey: ['dunning-campaigns-performance-stats'] })
      setFormOpen(false)
      toast.success('Dunning campaign created successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to create dunning campaign'
      toast.error(message)
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: DunningCampaignUpdate }) =>
      dunningCampaignsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dunning-campaigns'] })
      queryClient.invalidateQueries({ queryKey: ['dunning-campaigns-performance-stats'] })
      setEditingCampaign(null)
      setFormOpen(false)
      toast.success('Dunning campaign updated successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to update dunning campaign'
      toast.error(message)
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => dunningCampaignsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dunning-campaigns'] })
      queryClient.invalidateQueries({ queryKey: ['dunning-campaigns-performance-stats'] })
      setDeleteCampaign(null)
      toast.success('Dunning campaign deleted successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to delete dunning campaign'
      toast.error(message)
    },
  })

  const handleSubmit = (
    data: DunningCampaignCreate | DunningCampaignUpdate
  ) => {
    if (editingCampaign) {
      updateMutation.mutate({
        id: editingCampaign.id,
        data: data as DunningCampaignUpdate,
      })
    } else {
      createMutation.mutate(data as DunningCampaignCreate)
    }
  }

  const handleEdit = (campaign: DunningCampaign) => {
    setEditingCampaign(campaign)
    setFormOpen(true)
  }

  const handleCloseForm = (open: boolean) => {
    if (!open) {
      setEditingCampaign(null)
    }
    setFormOpen(open)
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">
          Failed to load dunning campaigns. Please try again.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title="Dunning Campaigns"
        description="Manage automated payment collection campaigns"
        actions={
          <Button onClick={() => setFormOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Create Campaign
          </Button>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
              <Megaphone className="h-3.5 w-3.5" />
              Active Campaigns
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {perfStats?.active_campaigns ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">
              of {perfStats?.total_campaigns ?? 0} total
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
              <TrendingUp className="h-3.5 w-3.5" />
              Recovery Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${
              (perfStats?.recovery_rate ?? 0) >= 70
                ? 'text-green-600'
                : (perfStats?.recovery_rate ?? 0) >= 40
                  ? 'text-yellow-600'
                  : 'text-red-600'
            }`}>
              {perfStats?.recovery_rate?.toFixed(1) ?? '0.0'}%
            </div>
            <p className="text-xs text-muted-foreground">
              {perfStats?.succeeded_requests ?? 0} of {perfStats?.total_payment_requests ?? 0} requests
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
              <DollarSign className="h-3.5 w-3.5" />
              Total Recovered
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {formatCents(Number(perfStats?.total_recovered_amount_cents ?? 0))}
            </div>
            <p className="text-xs text-muted-foreground">
              from succeeded requests
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
              <CheckCircle className="h-3.5 w-3.5" />
              Request Breakdown
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {perfStats?.total_payment_requests ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">
              {perfStats?.pending_requests ?? 0} pending, {perfStats?.failed_requests ?? 0} failed
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row md:items-center gap-4">
        <div className="relative flex-1 md:max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by code or name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-full md:w-[180px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="inactive">Inactive</SelectItem>
            <SelectItem value="archived">Archived</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <SortableTableHead label="Code" sortKey="code" sort={sort} onSort={setSort} />
              <SortableTableHead label="Name" sortKey="name" sort={sort} onSort={setSort} />
              <SortableTableHead label="Status" sortKey="status" sort={sort} onSort={setSort} />
              <TableHead className="hidden md:table-cell">Max Attempts</TableHead>
              <TableHead className="hidden md:table-cell">Days Between</TableHead>
              <TableHead className="hidden md:table-cell">BCC Emails</TableHead>
              <TableHead className="hidden md:table-cell">Thresholds</TableHead>
              <SortableTableHead label="Created" sortKey="created_at" sort={sort} onSort={setSort} className="hidden md:table-cell" />
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-5 w-24" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-28" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-16" />
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <Skeleton className="h-5 w-12" />
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <Skeleton className="h-5 w-12" />
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <Skeleton className="h-5 w-16" />
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <Skeleton className="h-5 w-12" />
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <Skeleton className="h-5 w-20" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-8 w-8" />
                  </TableCell>
                </TableRow>
              ))
            ) : filteredCampaigns.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={9}
                  className="h-24 text-center text-muted-foreground"
                >
                  <Megaphone className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                  No dunning campaigns found
                </TableCell>
              </TableRow>
            ) : (
              filteredCampaigns.map((campaign) => (
                <TableRow
                  key={campaign.id}
                  className="cursor-pointer hover:bg-muted/50"
                >
                  <TableCell>
                    <Link
                      to={`/admin/dunning-campaigns/${campaign.id}`}
                      className="text-primary hover:underline"
                    >
                      <code className="text-sm bg-muted px-1.5 py-0.5 rounded font-medium">
                        {campaign.code}
                      </code>
                    </Link>
                  </TableCell>
                  <TableCell className="font-medium">
                    <Link
                      to={`/admin/dunning-campaigns/${campaign.id}`}
                      className="hover:underline"
                    >
                      {campaign.name}
                    </Link>
                  </TableCell>
                  <TableCell>
                    {campaign.status === 'active' ? (
                      <Badge className="bg-green-600">Active</Badge>
                    ) : campaign.status === 'inactive' ? (
                      <Badge variant="secondary">Inactive</Badge>
                    ) : (
                      <Badge variant="outline">
                        {campaign.status.charAt(0).toUpperCase() +
                          campaign.status.slice(1)}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">{campaign.max_attempts}</TableCell>
                  <TableCell className="hidden md:table-cell">{campaign.days_between_attempts}</TableCell>
                  <TableCell className="hidden md:table-cell">
                    {campaign.bcc_emails.length > 0 ? (
                      <div className="flex items-center gap-1">
                        <Mail className="h-3.5 w-3.5 text-muted-foreground" />
                        <span>{campaign.bcc_emails.length}</span>
                      </div>
                    ) : (
                      <span className="text-muted-foreground">None</span>
                    )}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <Badge variant="secondary">
                      {campaign.thresholds?.length ?? 0}
                    </Badge>
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-muted-foreground text-sm">
                    {format(new Date(campaign.created_at), 'MMM d, yyyy')}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem asChild>
                          <Link to={`/admin/dunning-campaigns/${campaign.id}`}>
                            <Eye className="mr-2 h-4 w-4" />
                            View Details
                          </Link>
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => handleEdit(campaign)}
                        >
                          <Pencil className="mr-2 h-4 w-4" />
                          Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setDeleteCampaign(campaign)}
                          className="text-destructive"
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        <TablePagination
          page={page}
          pageSize={pageSize}
          totalCount={totalCount}
          onPageChange={setPage}
          onPageSizeChange={(size) => { setPageSize(size); setPage(1) }}
        />
      </div>

      {/* Create/Edit Dialog */}
      <DunningCampaignFormDialog
        open={formOpen}
        onOpenChange={handleCloseForm}
        campaign={editingCampaign}
        onSubmit={handleSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteCampaign}
        onOpenChange={(open) => !open && setDeleteCampaign(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-destructive" />
                Delete Dunning Campaign
              </div>
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{deleteCampaign?.name}&quot;
              ({deleteCampaign?.code})? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                deleteCampaign && deleteMutation.mutate(deleteCampaign.id)
              }
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
