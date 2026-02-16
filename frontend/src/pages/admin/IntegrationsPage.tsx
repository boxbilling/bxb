import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { format } from 'date-fns'
import {
  Plus,
  MoreHorizontal,
  Pencil,
  Trash2,
  Plug,
  Zap,
  AlertCircle,
  CheckCircle,
  Clock,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
import PageHeader from '@/components/PageHeader'
import { integrationsApi, ApiError } from '@/lib/api'
import type { Integration, IntegrationCreate, IntegrationUpdate } from '@/types/billing'

function IntegrationFormDialog({
  open,
  onOpenChange,
  integration,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  integration?: Integration | null
  onSubmit: (data: IntegrationCreate | IntegrationUpdate) => void
  isLoading: boolean
}) {
  const [formData, setFormData] = useState<{
    integration_type: string
    provider_type: string
    status: string
    settings: string
  }>({
    integration_type: integration?.integration_type ?? '',
    provider_type: integration?.provider_type ?? '',
    status: integration?.status ?? 'active',
    settings: integration ? JSON.stringify(integration.settings, null, 2) : '{}',
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    let parsedSettings: Record<string, unknown>
    try {
      parsedSettings = JSON.parse(formData.settings)
    } catch {
      toast.error('Invalid JSON in settings field')
      return
    }

    if (integration) {
      const data: IntegrationUpdate = {
        status: formData.status,
        settings: parsedSettings,
      }
      onSubmit(data)
    } else {
      const data: IntegrationCreate = {
        integration_type: formData.integration_type,
        provider_type: formData.provider_type,
        status: formData.status,
        settings: parsedSettings,
      }
      onSubmit(data)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {integration ? 'Edit Integration' : 'Add Integration'}
            </DialogTitle>
            <DialogDescription>
              {integration
                ? 'Update integration settings'
                : 'Connect a new external service'}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="integration_type">Integration Type *</Label>
                <Input
                  id="integration_type"
                  value={formData.integration_type}
                  onChange={(e) =>
                    setFormData({ ...formData, integration_type: e.target.value })
                  }
                  placeholder="accounting"
                  required
                  disabled={!!integration}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="provider_type">Provider Type *</Label>
                <Input
                  id="provider_type"
                  value={formData.provider_type}
                  onChange={(e) =>
                    setFormData({ ...formData, provider_type: e.target.value })
                  }
                  placeholder="quickbooks"
                  required
                  disabled={!!integration}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Status</Label>
              <Select
                value={formData.status}
                onValueChange={(value) =>
                  setFormData({ ...formData, status: value })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="settings">Settings (JSON)</Label>
              <textarea
                id="settings"
                className="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                value={formData.settings}
                onChange={(e) =>
                  setFormData({ ...formData, settings: e.target.value })
                }
              />
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
              {isLoading ? 'Saving...' : integration ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function IntegrationsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [formOpen, setFormOpen] = useState(false)
  const [editingIntegration, setEditingIntegration] = useState<Integration | null>(null)
  const [deleteIntegration, setDeleteIntegration] = useState<Integration | null>(null)

  const { data: integrations, isLoading, error } = useQuery({
    queryKey: ['integrations'],
    queryFn: () => integrationsApi.list(),
  })

  const createMutation = useMutation({
    mutationFn: (data: IntegrationCreate) => integrationsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations'] })
      setFormOpen(false)
      toast.success('Integration created successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to create integration'
      toast.error(message)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: IntegrationUpdate }) =>
      integrationsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations'] })
      setEditingIntegration(null)
      setFormOpen(false)
      toast.success('Integration updated successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to update integration'
      toast.error(message)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => integrationsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations'] })
      setDeleteIntegration(null)
      toast.success('Integration deleted successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to delete integration'
      toast.error(message)
    },
  })

  const testConnectionMutation = useMutation({
    mutationFn: (id: string) => integrationsApi.testConnection(id),
    onSuccess: (result) => {
      if (result.success) {
        toast.success('Connection test passed')
      } else {
        toast.error(result.error || 'Connection test failed')
      }
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Connection test failed'
      toast.error(message)
    },
  })

  const handleSubmit = (data: IntegrationCreate | IntegrationUpdate) => {
    if (editingIntegration) {
      updateMutation.mutate({ id: editingIntegration.id, data })
    } else {
      createMutation.mutate(data as IntegrationCreate)
    }
  }

  const handleEdit = (integration: Integration) => {
    setEditingIntegration(integration)
    setFormOpen(true)
  }

  const handleCloseForm = (open: boolean) => {
    if (!open) {
      setEditingIntegration(null)
    }
    setFormOpen(open)
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">
          Failed to load integrations. Please try again.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Integrations"
        description="Connect external services to your billing platform"
        actions={
          <Button onClick={() => setFormOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add Integration
          </Button>
        }
      />

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-6 w-32" />
                <Skeleton className="h-4 w-48" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-24" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : !integrations || integrations.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Plug className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold">No integrations configured</h3>
            <p className="text-muted-foreground text-center max-w-sm mt-1">
              Connect your first external service
            </p>
            <Button onClick={() => setFormOpen(true)} className="mt-4">
              <Plus className="mr-2 h-4 w-4" />
              Add Integration
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {integrations.map((integration) => (
            <Card key={integration.id} className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => navigate(`/admin/integrations/${integration.id}`)}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle>{integration.integration_type}</CardTitle>
                    <CardDescription>{integration.provider_type}</CardDescription>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={(e) => e.stopPropagation()}>
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                      <DropdownMenuItem onClick={() => handleEdit(integration)}>
                        <Pencil className="mr-2 h-4 w-4" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() =>
                          testConnectionMutation.mutate(integration.id)
                        }
                      >
                        <Zap className="mr-2 h-4 w-4" />
                        Test Connection
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => setDeleteIntegration(integration)}
                        className="text-destructive"
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center gap-2">
                  <Badge
                    variant={
                      integration.status === 'active'
                        ? 'default'
                        : integration.status === 'error'
                          ? 'destructive'
                          : 'secondary'
                    }
                    className={
                      integration.status === 'active'
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300'
                        : undefined
                    }
                  >
                    {integration.status === 'active' && (
                      <CheckCircle className="mr-1 h-3 w-3" />
                    )}
                    {integration.status}
                  </Badge>
                </div>

                <div className="flex items-center gap-1 text-sm text-muted-foreground">
                  <Clock className="h-4 w-4" />
                  {integration.last_sync_at
                    ? format(new Date(integration.last_sync_at), 'PPp')
                    : 'Never synced'}
                </div>

                <div className="text-sm text-muted-foreground">
                  {Object.keys(integration.settings).length} settings configured
                </div>

                {integration.error_details && (
                  <div className="flex items-start gap-1 text-sm text-destructive">
                    <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                    <span className="truncate">
                      {JSON.stringify(integration.error_details)}
                    </span>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <IntegrationFormDialog
        open={formOpen}
        onOpenChange={handleCloseForm}
        integration={editingIntegration}
        onSubmit={handleSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      <AlertDialog
        open={!!deleteIntegration}
        onOpenChange={(open) => !open && setDeleteIntegration(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Integration</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete the {deleteIntegration?.integration_type}{' '}
              integration ({deleteIntegration?.provider_type})?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                deleteIntegration && deleteMutation.mutate(deleteIntegration.id)
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
