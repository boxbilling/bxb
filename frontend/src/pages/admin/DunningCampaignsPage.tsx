import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  Search,
  MoreHorizontal,
  Pencil,
  Trash2,
  Megaphone,
  Mail,
  AlertTriangle,
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
import { dunningCampaignsApi, ApiError } from '@/lib/api'
import type {
  DunningCampaign,
  DunningCampaignCreate,
  DunningCampaignUpdate,
} from '@/types/billing'

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
            <div className="grid grid-cols-2 gap-4">
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
            <div className="grid grid-cols-2 gap-4">
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
                <div key={index} className="flex items-center gap-2">
                  <Select
                    value={threshold.currency}
                    onValueChange={(value) =>
                      updateThreshold(index, 'currency', value)
                    }
                  >
                    <SelectTrigger className="w-[100px]">
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
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              ))}
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
            <Button
              type="submit"
              disabled={
                isLoading ||
                (!campaign && (!formData.code || !formData.name))
              }
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

export default function DunningCampaignsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [formOpen, setFormOpen] = useState(false)
  const [editingCampaign, setEditingCampaign] =
    useState<DunningCampaign | null>(null)
  const [deleteCampaign, setDeleteCampaign] =
    useState<DunningCampaign | null>(null)

  // Fetch dunning campaigns
  const {
    data: campaigns = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ['dunning-campaigns'],
    queryFn: () => dunningCampaignsApi.list(),
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

  // Stats
  const stats = {
    total: campaigns.length,
    active: campaigns.filter((c) => c.status === 'active').length,
    avgMaxAttempts:
      campaigns.length > 0
        ? campaigns.reduce((sum, c) => sum + c.max_attempts, 0) /
          campaigns.length
        : 0,
    withThresholds: campaigns.filter(
      (c) => c.thresholds && c.thresholds.length > 0
    ).length,
  }

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: DunningCampaignCreate) =>
      dunningCampaignsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dunning-campaigns'] })
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
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">
            Dunning Campaigns
          </h2>
          <p className="text-muted-foreground">
            Manage automated payment collection campaigns
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Campaign
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Campaigns
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Active
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {stats.active}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Avg Max Attempts
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats.avgMaxAttempts.toFixed(1)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              With Thresholds
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {stats.withThresholds}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by code or name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[180px]">
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
              <TableHead>Code</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Max Attempts</TableHead>
              <TableHead>Days Between</TableHead>
              <TableHead>BCC Emails</TableHead>
              <TableHead>Thresholds</TableHead>
              <TableHead>Created</TableHead>
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
                  <TableCell>
                    <Skeleton className="h-5 w-12" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-12" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-16" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-12" />
                  </TableCell>
                  <TableCell>
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
                <TableRow key={campaign.id}>
                  <TableCell>
                    <code className="text-sm bg-muted px-1.5 py-0.5 rounded font-medium">
                      {campaign.code}
                    </code>
                  </TableCell>
                  <TableCell className="font-medium">
                    {campaign.name}
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
                  <TableCell>{campaign.max_attempts}</TableCell>
                  <TableCell>{campaign.days_between_attempts}</TableCell>
                  <TableCell>
                    {campaign.bcc_emails.length > 0 ? (
                      <div className="flex items-center gap-1">
                        <Mail className="h-3.5 w-3.5 text-muted-foreground" />
                        <span>{campaign.bcc_emails.length}</span>
                      </div>
                    ) : (
                      <span className="text-muted-foreground">None</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">
                      {campaign.thresholds?.length ?? 0}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
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
