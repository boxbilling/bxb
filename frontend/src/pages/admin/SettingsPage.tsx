import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Key,
  Bell,
  Building,
  Plus,
  MoreHorizontal,
  Pencil,
  Trash2,
  Eye,
  Copy,
  RotateCw,
  Globe,
  Megaphone,
  Plug,
  CheckCircle,
  XCircle,
} from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'

import {
  organizationsApi,
  webhookEndpointsApi,
  dunningCampaignsApi,
  integrationsApi,
  ApiError,
} from '@/lib/api'
import type {
  OrganizationUpdate,
  ApiKeyCreate,
  ApiKeyCreateResponse,
  ApiKey,
  WebhookEndpoint,
  WebhookEndpointCreate,
  WebhookEndpointUpdate,
  DunningCampaign,
  DunningCampaignCreate,
  DunningCampaignUpdate,
  DunningCampaignThresholdCreate,
  Integration,
  IntegrationCreate,
  IntegrationUpdate,
} from '@/types/billing'

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
import { Textarea } from '@/components/ui/textarea'

// ─── Tab 1: Organization ───────────────────────────────────────────────────────

function OrganizationTab() {
  const queryClient = useQueryClient()

  const { data: org, isLoading } = useQuery({
    queryKey: ['organization'],
    queryFn: () => organizationsApi.getCurrent(),
  })

  const [formData, setFormData] = useState<OrganizationUpdate>({})
  const [initialized, setInitialized] = useState(false)

  if (org && !initialized) {
    setFormData({
      name: org.name,
      default_currency: org.default_currency,
      timezone: org.timezone,
      invoice_grace_period: org.invoice_grace_period,
      net_payment_term: org.net_payment_term,
      document_number_prefix: org.document_number_prefix,
      hmac_key: org.hmac_key,
      logo_url: org.logo_url,
      email: org.email,
      legal_name: org.legal_name,
      address_line1: org.address_line1,
      address_line2: org.address_line2,
      city: org.city,
      state: org.state,
      zipcode: org.zipcode,
      country: org.country,
    })
    setInitialized(true)
  }

  const updateMutation = useMutation({
    mutationFn: (data: OrganizationUpdate) =>
      organizationsApi.updateCurrent(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['organization'] })
      toast.success('Organization settings updated')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to update organization'
      toast.error(message)
    },
  })

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault()
    updateMutation.mutate(formData)
  }

  const updateField = (field: keyof OrganizationUpdate, value: string | number | null) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-5 w-32" />
            </CardHeader>
            <CardContent className="space-y-4">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  return (
    <form onSubmit={handleSave} className="space-y-6">
      {/* General */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">General</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="org-name">Name</Label>
            <Input
              id="org-name"
              value={formData.name ?? ''}
              onChange={(e) => updateField('name', e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="currency">Default Currency</Label>
              <Select
                value={formData.default_currency ?? ''}
                onValueChange={(v) => updateField('default_currency', v)}
              >
                <SelectTrigger id="currency">
                  <SelectValue placeholder="Select currency" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="USD">USD</SelectItem>
                  <SelectItem value="EUR">EUR</SelectItem>
                  <SelectItem value="GBP">GBP</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="timezone">Timezone</Label>
              <Input
                id="timezone"
                value={formData.timezone ?? ''}
                onChange={(e) => updateField('timezone', e.target.value)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Billing */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Billing</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="grace-period">Invoice Grace Period (days)</Label>
              <Input
                id="grace-period"
                type="number"
                value={formData.invoice_grace_period ?? 0}
                onChange={(e) =>
                  updateField('invoice_grace_period', parseInt(e.target.value) || 0)
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="net-term">Net Payment Term (days)</Label>
              <Input
                id="net-term"
                type="number"
                value={formData.net_payment_term ?? 0}
                onChange={(e) =>
                  updateField('net_payment_term', parseInt(e.target.value) || 0)
                }
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="doc-prefix">Document Number Prefix</Label>
              <Input
                id="doc-prefix"
                value={formData.document_number_prefix ?? ''}
                onChange={(e) =>
                  updateField('document_number_prefix', e.target.value || null)
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="hmac-key">HMAC Key</Label>
              <Input
                id="hmac-key"
                value={formData.hmac_key ?? ''}
                onChange={(e) =>
                  updateField('hmac_key', e.target.value || null)
                }
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Branding */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Branding</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="logo-url">Logo URL</Label>
            <Input
              id="logo-url"
              value={formData.logo_url ?? ''}
              onChange={(e) =>
                updateField('logo_url', e.target.value || null)
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="org-email">Email</Label>
            <Input
              id="org-email"
              type="email"
              value={formData.email ?? ''}
              onChange={(e) =>
                updateField('email', e.target.value || null)
              }
            />
          </div>
        </CardContent>
      </Card>

      {/* Legal Address */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Legal Address</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="legal-name">Legal Name</Label>
            <Input
              id="legal-name"
              value={formData.legal_name ?? ''}
              onChange={(e) =>
                updateField('legal_name', e.target.value || null)
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="address1">Address Line 1</Label>
            <Input
              id="address1"
              value={formData.address_line1 ?? ''}
              onChange={(e) =>
                updateField('address_line1', e.target.value || null)
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="address2">Address Line 2</Label>
            <Input
              id="address2"
              value={formData.address_line2 ?? ''}
              onChange={(e) =>
                updateField('address_line2', e.target.value || null)
              }
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="city">City</Label>
              <Input
                id="city"
                value={formData.city ?? ''}
                onChange={(e) =>
                  updateField('city', e.target.value || null)
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="state">State</Label>
              <Input
                id="state"
                value={formData.state ?? ''}
                onChange={(e) =>
                  updateField('state', e.target.value || null)
                }
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="zipcode">Zipcode</Label>
              <Input
                id="zipcode"
                value={formData.zipcode ?? ''}
                onChange={(e) =>
                  updateField('zipcode', e.target.value || null)
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="country">Country</Label>
              <Input
                id="country"
                value={formData.country ?? ''}
                onChange={(e) =>
                  updateField('country', e.target.value || null)
                }
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Button type="submit" disabled={updateMutation.isPending}>
        {updateMutation.isPending ? 'Saving...' : 'Save Organization Settings'}
      </Button>
    </form>
  )
}

// ─── Tab 2: API Keys ───────────────────────────────────────────────────────────

function ApiKeysTab() {
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [rawKeyDialog, setRawKeyDialog] = useState<string | null>(null)
  const [revokeKey, setRevokeKey] = useState<ApiKey | null>(null)
  const [createForm, setCreateForm] = useState<ApiKeyCreate>({})

  const { data: apiKeys = [], isLoading } = useQuery({
    queryKey: ['api-keys'],
    queryFn: () => organizationsApi.listApiKeys(),
  })

  const createMutation = useMutation({
    mutationFn: (data: ApiKeyCreate) => organizationsApi.createApiKey(data),
    onSuccess: (response: ApiKeyCreateResponse) => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
      setCreateOpen(false)
      setCreateForm({})
      setRawKeyDialog(response.raw_key)
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to create API key'
      toast.error(message)
    },
  })

  const revokeMutation = useMutation({
    mutationFn: (id: string) => organizationsApi.revokeApiKey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
      setRevokeKey(null)
      toast.success('API key revoked')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to revoke API key'
      toast.error(message)
    },
  })

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(createForm)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium">API Keys</h3>
          <p className="text-sm text-muted-foreground">
            Manage API keys for accessing the billing API
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create API Key
        </Button>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Key Prefix</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Last Used</TableHead>
              <TableHead>Expires</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-8" /></TableCell>
                </TableRow>
              ))
            ) : apiKeys.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={6}
                  className="h-24 text-center text-muted-foreground"
                >
                  <Key className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                  No API keys
                </TableCell>
              </TableRow>
            ) : (
              apiKeys.map((key) => (
                <TableRow key={key.id}>
                  <TableCell className="font-medium">
                    {key.name || 'Unnamed'}
                  </TableCell>
                  <TableCell>
                    <code className="text-sm font-mono bg-muted px-1.5 py-0.5 rounded">
                      {key.key_prefix}...
                    </code>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={key.status === 'active' ? 'default' : 'secondary'}
                    >
                      {key.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {key.last_used_at
                      ? format(new Date(key.last_used_at), 'MMM d, yyyy')
                      : 'Never'}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {key.expires_at
                      ? format(new Date(key.expires_at), 'MMM d, yyyy')
                      : 'Never'}
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
                          onClick={() => setRevokeKey(key)}
                          className="text-destructive"
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Revoke
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

      {/* Create API Key Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <form onSubmit={handleCreate}>
            <DialogHeader>
              <DialogTitle>Create API Key</DialogTitle>
              <DialogDescription>
                Generate a new API key for accessing the billing API
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="key-name">Name (optional)</Label>
                <Input
                  id="key-name"
                  value={createForm.name ?? ''}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, name: e.target.value || null })
                  }
                  placeholder="e.g. Production Key"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="key-expires">Expires At (optional)</Label>
                <Input
                  id="key-expires"
                  type="date"
                  value={createForm.expires_at ?? ''}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      expires_at: e.target.value || null,
                    })
                  }
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setCreateOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Raw Key Display AlertDialog */}
      <AlertDialog
        open={!!rawKeyDialog}
        onOpenChange={(open) => !open && setRawKeyDialog(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>API Key Created</AlertDialogTitle>
            <AlertDialogDescription>
              This key will only be shown once. Copy it now.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="my-4 rounded-md bg-muted p-4">
            <code className="text-sm font-mono break-all">{rawKeyDialog}</code>
          </div>
          <AlertDialogFooter>
            <AlertDialogAction
              onClick={() => {
                if (rawKeyDialog) {
                  navigator.clipboard.writeText(rawKeyDialog)
                  toast.success('API key copied to clipboard')
                }
                setRawKeyDialog(null)
              }}
            >
              <Copy className="mr-2 h-4 w-4" />
              Copy & Close
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Revoke Confirmation */}
      <AlertDialog
        open={!!revokeKey}
        onOpenChange={(open) => !open && setRevokeKey(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Revoke API Key</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to revoke &quot;{revokeKey?.name || 'Unnamed'}
              &quot;? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                revokeKey && revokeMutation.mutate(revokeKey.id)
              }
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {revokeMutation.isPending ? 'Revoking...' : 'Revoke'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

// ─── Tab 3: Webhooks ───────────────────────────────────────────────────────────

function WebhooksTab() {
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [editEndpoint, setEditEndpoint] = useState<WebhookEndpoint | null>(null)
  const [deleteEndpoint, setDeleteEndpoint] = useState<WebhookEndpoint | null>(null)
  const [deliveriesEndpoint, setDeliveriesEndpoint] = useState<WebhookEndpoint | null>(null)

  const [createForm, setCreateForm] = useState<WebhookEndpointCreate>({
    url: '',
    signature_algo: 'hmac',
  })
  const [editForm, setEditForm] = useState<WebhookEndpointUpdate>({})

  const { data: endpoints = [], isLoading } = useQuery({
    queryKey: ['webhook-endpoints'],
    queryFn: () => webhookEndpointsApi.list(),
  })

  const { data: deliveries = [] } = useQuery({
    queryKey: ['webhook-deliveries', deliveriesEndpoint?.id],
    queryFn: () =>
      webhookEndpointsApi.listWebhooks({
        endpoint_id: deliveriesEndpoint!.id,
      }),
    enabled: !!deliveriesEndpoint,
  })

  const createMutation = useMutation({
    mutationFn: (data: WebhookEndpointCreate) =>
      webhookEndpointsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhook-endpoints'] })
      setCreateOpen(false)
      setCreateForm({ url: '', signature_algo: 'hmac' })
      toast.success('Webhook endpoint created')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to create webhook endpoint'
      toast.error(message)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: WebhookEndpointUpdate }) =>
      webhookEndpointsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhook-endpoints'] })
      setEditEndpoint(null)
      toast.success('Webhook endpoint updated')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to update webhook endpoint'
      toast.error(message)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => webhookEndpointsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhook-endpoints'] })
      setDeleteEndpoint(null)
      toast.success('Webhook endpoint deleted')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to delete webhook endpoint'
      toast.error(message)
    },
  })

  const retryMutation = useMutation({
    mutationFn: (webhookId: string) =>
      webhookEndpointsApi.retryWebhook(webhookId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['webhook-deliveries', deliveriesEndpoint?.id],
      })
      toast.success('Webhook retry initiated')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to retry webhook'
      toast.error(message)
    },
  })

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(createForm)
  }

  const handleEdit = (e: React.FormEvent) => {
    e.preventDefault()
    if (editEndpoint) {
      updateMutation.mutate({ id: editEndpoint.id, data: editForm })
    }
  }

  const openEdit = (endpoint: WebhookEndpoint) => {
    setEditEndpoint(endpoint)
    setEditForm({
      url: endpoint.url,
      signature_algo: endpoint.signature_algo,
      status: endpoint.status,
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium">Webhook Endpoints</h3>
          <p className="text-sm text-muted-foreground">
            Configure webhook endpoints for billing events
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Endpoint
        </Button>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>URL</TableHead>
              <TableHead>Signature Algo</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-48" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-8" /></TableCell>
                </TableRow>
              ))
            ) : endpoints.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={5}
                  className="h-24 text-center text-muted-foreground"
                >
                  <Globe className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                  No webhook endpoints
                </TableCell>
              </TableRow>
            ) : (
              endpoints.map((endpoint) => (
                <TableRow key={endpoint.id}>
                  <TableCell className="max-w-[300px] truncate font-mono text-sm">
                    {endpoint.url}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{endpoint.signature_algo}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        endpoint.status === 'active' ? 'default' : 'secondary'
                      }
                      className={
                        endpoint.status === 'active' ? 'bg-green-600' : ''
                      }
                    >
                      {endpoint.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {format(new Date(endpoint.created_at), 'MMM d, yyyy')}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => openEdit(endpoint)}>
                          <Pencil className="mr-2 h-4 w-4" />
                          Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setDeliveriesEndpoint(endpoint)}
                        >
                          <Eye className="mr-2 h-4 w-4" />
                          View Deliveries
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setDeleteEndpoint(endpoint)}
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

      {/* Create Endpoint Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <form onSubmit={handleCreate}>
            <DialogHeader>
              <DialogTitle>Add Webhook Endpoint</DialogTitle>
              <DialogDescription>
                Configure a new webhook endpoint to receive billing events
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="webhook-url">URL *</Label>
                <Input
                  id="webhook-url"
                  value={createForm.url}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, url: e.target.value })
                  }
                  placeholder="https://your-app.com/webhooks"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="webhook-algo">Signature Algorithm</Label>
                <Select
                  value={createForm.signature_algo}
                  onValueChange={(v) =>
                    setCreateForm({ ...createForm, signature_algo: v })
                  }
                >
                  <SelectTrigger id="webhook-algo">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="hmac">hmac</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setCreateOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Edit Endpoint Dialog */}
      <Dialog
        open={!!editEndpoint}
        onOpenChange={(open) => !open && setEditEndpoint(null)}
      >
        <DialogContent className="sm:max-w-[400px]">
          <form onSubmit={handleEdit}>
            <DialogHeader>
              <DialogTitle>Edit Webhook Endpoint</DialogTitle>
              <DialogDescription>
                Update webhook endpoint settings
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="edit-url">URL</Label>
                <Input
                  id="edit-url"
                  value={editForm.url ?? ''}
                  onChange={(e) =>
                    setEditForm({ ...editForm, url: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-algo">Signature Algorithm</Label>
                <Select
                  value={editForm.signature_algo ?? ''}
                  onValueChange={(v) =>
                    setEditForm({ ...editForm, signature_algo: v })
                  }
                >
                  <SelectTrigger id="edit-algo">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="hmac">hmac</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-status">Status</Label>
                <Select
                  value={editForm.status ?? ''}
                  onValueChange={(v) =>
                    setEditForm({ ...editForm, status: v })
                  }
                >
                  <SelectTrigger id="edit-status">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditEndpoint(null)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? 'Saving...' : 'Save'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteEndpoint}
        onOpenChange={(open) => !open && setDeleteEndpoint(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Webhook Endpoint</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this endpoint? This action cannot
              be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                deleteEndpoint && deleteMutation.mutate(deleteEndpoint.id)
              }
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Deliveries Sheet */}
      <Sheet
        open={!!deliveriesEndpoint}
        onOpenChange={(open) => !open && setDeliveriesEndpoint(null)}
      >
        <SheetContent side="right" className="sm:max-w-xl w-full">
          <SheetHeader>
            <SheetTitle>Webhook Deliveries</SheetTitle>
            <SheetDescription>
              Recent deliveries for this endpoint
            </SheetDescription>
          </SheetHeader>
          <div className="mt-4 overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Object Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>HTTP Status</TableHead>
                  <TableHead>Retries</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {deliveries.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={7}
                      className="h-24 text-center text-muted-foreground"
                    >
                      No deliveries yet
                    </TableCell>
                  </TableRow>
                ) : (
                  deliveries.map((webhook) => (
                    <TableRow key={webhook.id}>
                      <TableCell className="text-sm font-medium">
                        {webhook.webhook_type}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {webhook.object_type ?? '—'}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            webhook.status === 'delivered'
                              ? 'default'
                              : webhook.status === 'failed'
                                ? 'destructive'
                                : 'secondary'
                          }
                        >
                          {webhook.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {webhook.http_status ?? '—'}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {webhook.retries}/{webhook.max_retries}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {format(new Date(webhook.created_at), 'MMM d, HH:mm')}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => retryMutation.mutate(webhook.id)}
                          disabled={retryMutation.isPending}
                        >
                          <RotateCw className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}

// ─── Tab 4: Dunning Campaigns ──────────────────────────────────────────────────

interface ThresholdRow {
  currency: string
  amount_cents: string
}

const emptyThreshold: ThresholdRow = { currency: 'USD', amount_cents: '' }

function DunningCampaignsTab() {
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [editCampaign, setEditCampaign] = useState<DunningCampaign | null>(null)
  const [deleteCampaign, setDeleteCampaign] = useState<DunningCampaign | null>(null)

  const defaultCreate: DunningCampaignCreate = {
    code: '',
    name: '',
    description: null,
    max_attempts: 3,
    days_between_attempts: 3,
    bcc_emails: [],
    status: 'active',
    thresholds: [],
  }

  const [createForm, setCreateForm] = useState<DunningCampaignCreate>(defaultCreate)
  const [editForm, setEditForm] = useState<DunningCampaignUpdate>({})
  const [createThresholds, setCreateThresholds] = useState<ThresholdRow[]>([])
  const [editThresholds, setEditThresholds] = useState<ThresholdRow[]>([])
  const [bccInput, setBccInput] = useState('')
  const [editBccInput, setEditBccInput] = useState('')

  const { data: campaigns = [], isLoading } = useQuery({
    queryKey: ['dunning-campaigns'],
    queryFn: () => dunningCampaignsApi.list(),
  })

  const createMutation = useMutation({
    mutationFn: (data: DunningCampaignCreate) => dunningCampaignsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dunning-campaigns'] })
      setCreateOpen(false)
      setCreateForm(defaultCreate)
      setCreateThresholds([])
      setBccInput('')
      toast.success('Dunning campaign created')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to create campaign'
      toast.error(message)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: DunningCampaignUpdate }) =>
      dunningCampaignsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dunning-campaigns'] })
      setEditCampaign(null)
      toast.success('Dunning campaign updated')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to update campaign'
      toast.error(message)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => dunningCampaignsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dunning-campaigns'] })
      setDeleteCampaign(null)
      toast.success('Dunning campaign deleted')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to delete campaign'
      toast.error(message)
    },
  })

  const buildThresholds = (rows: ThresholdRow[]): DunningCampaignThresholdCreate[] =>
    rows
      .filter((r) => r.amount_cents !== '')
      .map((r) => ({ currency: r.currency, amount_cents: Number(r.amount_cents) }))

  const parseBccEmails = (input: string): string[] =>
    input
      .split(',')
      .map((e) => e.trim())
      .filter(Boolean)

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate({
      ...createForm,
      thresholds: buildThresholds(createThresholds),
      bcc_emails: parseBccEmails(bccInput),
    })
  }

  const handleEdit = (e: React.FormEvent) => {
    e.preventDefault()
    if (editCampaign) {
      updateMutation.mutate({
        id: editCampaign.id,
        data: {
          ...editForm,
          thresholds: buildThresholds(editThresholds),
          bcc_emails: parseBccEmails(editBccInput),
        },
      })
    }
  }

  const openEdit = (campaign: DunningCampaign) => {
    setEditCampaign(campaign)
    setEditForm({
      code: campaign.code,
      name: campaign.name,
      description: campaign.description,
      max_attempts: campaign.max_attempts,
      days_between_attempts: campaign.days_between_attempts,
      status: campaign.status,
    })
    setEditThresholds(
      campaign.thresholds.map((t) => ({
        currency: t.currency,
        amount_cents: String(t.amount_cents),
      }))
    )
    setEditBccInput((campaign.bcc_emails ?? []).join(', '))
  }

  const updateThreshold = (
    rows: ThresholdRow[],
    setRows: (r: ThresholdRow[]) => void,
    index: number,
    field: keyof ThresholdRow,
    value: string
  ) => {
    const updated = [...rows]
    updated[index] = { ...updated[index], [field]: value }
    setRows(updated)
  }

  const removeThreshold = (
    rows: ThresholdRow[],
    setRows: (r: ThresholdRow[]) => void,
    index: number
  ) => {
    setRows(rows.filter((_, i) => i !== index))
  }

  const renderThresholdInputs = (
    rows: ThresholdRow[],
    setRows: (r: ThresholdRow[]) => void
  ) => (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>Thresholds</Label>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setRows([...rows, { ...emptyThreshold }])}
        >
          <Plus className="mr-1 h-3 w-3" />
          Add
        </Button>
      </div>
      {rows.map((row, i) => (
        <div key={i} className="flex items-center gap-2">
          <Select
            value={row.currency}
            onValueChange={(v) => updateThreshold(rows, setRows, i, 'currency', v)}
          >
            <SelectTrigger className="w-24">
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
            placeholder="Amount (cents)"
            value={row.amount_cents}
            onChange={(e) =>
              updateThreshold(rows, setRows, i, 'amount_cents', e.target.value)
            }
            className="flex-1"
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => removeThreshold(rows, setRows, i)}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ))}
      {rows.length === 0 && (
        <p className="text-sm text-muted-foreground">No thresholds configured</p>
      )}
    </div>
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium">Dunning Campaigns</h3>
          <p className="text-sm text-muted-foreground">
            Manage automated payment retry campaigns
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Campaign
        </Button>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Code</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Max Attempts</TableHead>
              <TableHead>Days Between</TableHead>
              <TableHead>Thresholds</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-12" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-12" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-8" /></TableCell>
                </TableRow>
              ))
            ) : campaigns.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={7}
                  className="h-24 text-center text-muted-foreground"
                >
                  <Megaphone className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                  No dunning campaigns
                </TableCell>
              </TableRow>
            ) : (
              campaigns.map((campaign) => (
                <TableRow key={campaign.id}>
                  <TableCell>
                    <code className="text-sm font-mono bg-muted px-1.5 py-0.5 rounded">
                      {campaign.code}
                    </code>
                  </TableCell>
                  <TableCell className="font-medium">{campaign.name}</TableCell>
                  <TableCell className="text-sm">{campaign.max_attempts}</TableCell>
                  <TableCell className="text-sm">{campaign.days_between_attempts}d</TableCell>
                  <TableCell className="text-sm">
                    {campaign.thresholds.length === 0 ? (
                      <span className="text-muted-foreground">None</span>
                    ) : (
                      campaign.thresholds.map((t, i) => (
                        <Badge key={i} variant="outline" className="mr-1">
                          {t.currency} {Number(t.amount_cents).toLocaleString()}c
                        </Badge>
                      ))
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={campaign.status === 'active' ? 'default' : 'secondary'}
                      className={campaign.status === 'active' ? 'bg-green-600' : ''}
                    >
                      {campaign.status}
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
                        <DropdownMenuItem onClick={() => openEdit(campaign)}>
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

      {/* Create Campaign Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-[500px] max-h-[90vh] overflow-y-auto">
          <form onSubmit={handleCreate}>
            <DialogHeader>
              <DialogTitle>Create Dunning Campaign</DialogTitle>
              <DialogDescription>
                Set up automated payment retry logic for failed invoices
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="dc-code">Code *</Label>
                  <Input
                    id="dc-code"
                    value={createForm.code}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, code: e.target.value })
                    }
                    placeholder="e.g. standard-retry"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="dc-name">Name *</Label>
                  <Input
                    id="dc-name"
                    value={createForm.name}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, name: e.target.value })
                    }
                    placeholder="e.g. Standard Retry"
                    required
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="dc-desc">Description</Label>
                <Textarea
                  id="dc-desc"
                  value={createForm.description ?? ''}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      description: e.target.value || null,
                    })
                  }
                  placeholder="Describe this campaign..."
                  rows={2}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="dc-max">Max Attempts</Label>
                  <Input
                    id="dc-max"
                    type="number"
                    min={1}
                    value={createForm.max_attempts}
                    onChange={(e) =>
                      setCreateForm({
                        ...createForm,
                        max_attempts: parseInt(e.target.value) || 3,
                      })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="dc-days">Days Between Attempts</Label>
                  <Input
                    id="dc-days"
                    type="number"
                    min={1}
                    value={createForm.days_between_attempts}
                    onChange={(e) =>
                      setCreateForm({
                        ...createForm,
                        days_between_attempts: parseInt(e.target.value) || 3,
                      })
                    }
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="dc-status">Status</Label>
                <Select
                  value={createForm.status}
                  onValueChange={(v) =>
                    setCreateForm({ ...createForm, status: v })
                  }
                >
                  <SelectTrigger id="dc-status">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="dc-bcc">BCC Emails (comma separated)</Label>
                <Input
                  id="dc-bcc"
                  value={bccInput}
                  onChange={(e) => setBccInput(e.target.value)}
                  placeholder="admin@example.com, billing@example.com"
                />
              </div>
              {renderThresholdInputs(createThresholds, setCreateThresholds)}
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setCreateOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Edit Campaign Dialog */}
      <Dialog
        open={!!editCampaign}
        onOpenChange={(open) => !open && setEditCampaign(null)}
      >
        <DialogContent className="sm:max-w-[500px] max-h-[90vh] overflow-y-auto">
          <form onSubmit={handleEdit}>
            <DialogHeader>
              <DialogTitle>Edit Dunning Campaign</DialogTitle>
              <DialogDescription>
                Update campaign settings and thresholds
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="edit-dc-code">Code</Label>
                  <Input
                    id="edit-dc-code"
                    value={editForm.code ?? ''}
                    onChange={(e) =>
                      setEditForm({ ...editForm, code: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit-dc-name">Name</Label>
                  <Input
                    id="edit-dc-name"
                    value={editForm.name ?? ''}
                    onChange={(e) =>
                      setEditForm({ ...editForm, name: e.target.value })
                    }
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-dc-desc">Description</Label>
                <Textarea
                  id="edit-dc-desc"
                  value={editForm.description ?? ''}
                  onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      description: e.target.value || null,
                    })
                  }
                  rows={2}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="edit-dc-max">Max Attempts</Label>
                  <Input
                    id="edit-dc-max"
                    type="number"
                    min={1}
                    value={editForm.max_attempts ?? ''}
                    onChange={(e) =>
                      setEditForm({
                        ...editForm,
                        max_attempts: parseInt(e.target.value) || undefined,
                      })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit-dc-days">Days Between Attempts</Label>
                  <Input
                    id="edit-dc-days"
                    type="number"
                    min={1}
                    value={editForm.days_between_attempts ?? ''}
                    onChange={(e) =>
                      setEditForm({
                        ...editForm,
                        days_between_attempts: parseInt(e.target.value) || undefined,
                      })
                    }
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-dc-status">Status</Label>
                <Select
                  value={editForm.status ?? ''}
                  onValueChange={(v) =>
                    setEditForm({ ...editForm, status: v })
                  }
                >
                  <SelectTrigger id="edit-dc-status">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-dc-bcc">BCC Emails (comma separated)</Label>
                <Input
                  id="edit-dc-bcc"
                  value={editBccInput}
                  onChange={(e) => setEditBccInput(e.target.value)}
                  placeholder="admin@example.com, billing@example.com"
                />
              </div>
              {renderThresholdInputs(editThresholds, setEditThresholds)}
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditCampaign(null)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? 'Saving...' : 'Save'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteCampaign}
        onOpenChange={(open) => !open && setDeleteCampaign(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Dunning Campaign</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{deleteCampaign?.name}&quot;?
              This action cannot be undone.
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

// ─── Tab 5: Integrations ───────────────────────────────────────────────────────

function IntegrationsTab() {
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [editIntegration, setEditIntegration] = useState<Integration | null>(null)
  const [deleteIntegration, setDeleteIntegration] = useState<Integration | null>(null)
  const [testingId, setTestingId] = useState<string | null>(null)

  const defaultCreate: IntegrationCreate = {
    integration_type: 'payment',
    provider_type: '',
    status: 'active',
    settings: {},
  }

  const [createForm, setCreateForm] = useState<IntegrationCreate>(defaultCreate)
  const [editForm, setEditForm] = useState<IntegrationUpdate>({})
  const [createSettingsJson, setCreateSettingsJson] = useState('{}')
  const [editSettingsJson, setEditSettingsJson] = useState('{}')

  const { data: integrations = [], isLoading } = useQuery({
    queryKey: ['integrations-settings'],
    queryFn: () => integrationsApi.list(),
  })

  const createMutation = useMutation({
    mutationFn: (data: IntegrationCreate) => integrationsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations-settings'] })
      setCreateOpen(false)
      setCreateForm(defaultCreate)
      setCreateSettingsJson('{}')
      toast.success('Integration created')
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
      queryClient.invalidateQueries({ queryKey: ['integrations-settings'] })
      setEditIntegration(null)
      toast.success('Integration updated')
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
      queryClient.invalidateQueries({ queryKey: ['integrations-settings'] })
      setDeleteIntegration(null)
      toast.success('Integration deleted')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to delete integration'
      toast.error(message)
    },
  })

  const testMutation = useMutation({
    mutationFn: (id: string) => integrationsApi.testConnection(id),
    onSuccess: (result) => {
      setTestingId(null)
      if (result.success) {
        toast.success('Connection test successful')
      } else {
        toast.error(`Connection test failed: ${result.error || 'Unknown error'}`)
      }
    },
    onError: (error) => {
      setTestingId(null)
      const message =
        error instanceof ApiError ? error.message : 'Failed to test connection'
      toast.error(message)
    },
  })

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    let settings = {}
    try {
      settings = JSON.parse(createSettingsJson)
    } catch {
      toast.error('Invalid JSON in settings')
      return
    }
    createMutation.mutate({ ...createForm, settings })
  }

  const handleEdit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!editIntegration) return
    let settings = undefined
    try {
      settings = JSON.parse(editSettingsJson)
    } catch {
      toast.error('Invalid JSON in settings')
      return
    }
    updateMutation.mutate({
      id: editIntegration.id,
      data: { ...editForm, settings },
    })
  }

  const openEdit = (integration: Integration) => {
    setEditIntegration(integration)
    setEditForm({
      status: integration.status,
    })
    setEditSettingsJson(JSON.stringify(integration.settings, null, 2))
  }

  const handleTest = (id: string) => {
    setTestingId(id)
    testMutation.mutate(id)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium">Integrations</h3>
          <p className="text-sm text-muted-foreground">
            Connect external services for payments, CRM, and more
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Integration
        </Button>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Type</TableHead>
              <TableHead>Provider</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Last Sync</TableHead>
              <TableHead>Error</TableHead>
              <TableHead className="w-[100px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-20" /></TableCell>
                </TableRow>
              ))
            ) : integrations.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={6}
                  className="h-24 text-center text-muted-foreground"
                >
                  <Plug className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                  No integrations configured
                </TableCell>
              </TableRow>
            ) : (
              integrations.map((integration) => (
                <TableRow key={integration.id}>
                  <TableCell>
                    <Badge variant="outline">{integration.integration_type}</Badge>
                  </TableCell>
                  <TableCell className="font-medium">
                    {integration.provider_type}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={integration.status === 'active' ? 'default' : 'secondary'}
                      className={integration.status === 'active' ? 'bg-green-600' : ''}
                    >
                      {integration.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {integration.last_sync_at
                      ? format(new Date(integration.last_sync_at), 'MMM d, HH:mm')
                      : 'Never'}
                  </TableCell>
                  <TableCell>
                    {integration.error_details ? (
                      <XCircle className="h-4 w-4 text-destructive" />
                    ) : (
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleTest(integration.id)}
                        disabled={testingId === integration.id}
                      >
                        {testingId === integration.id ? (
                          <RotateCw className="h-4 w-4 animate-spin" />
                        ) : (
                          'Test'
                        )}
                      </Button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => openEdit(integration)}>
                            <Pencil className="mr-2 h-4 w-4" />
                            Configure
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
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Create Integration Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <form onSubmit={handleCreate}>
            <DialogHeader>
              <DialogTitle>Add Integration</DialogTitle>
              <DialogDescription>
                Connect a new external service
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="int-type">Type *</Label>
                  <Select
                    value={createForm.integration_type}
                    onValueChange={(v) =>
                      setCreateForm({ ...createForm, integration_type: v })
                    }
                  >
                    <SelectTrigger id="int-type">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="payment">Payment</SelectItem>
                      <SelectItem value="crm">CRM</SelectItem>
                      <SelectItem value="accounting">Accounting</SelectItem>
                      <SelectItem value="tax">Tax</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="int-provider">Provider *</Label>
                  <Input
                    id="int-provider"
                    value={createForm.provider_type}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, provider_type: e.target.value })
                    }
                    placeholder="e.g. stripe, salesforce"
                    required
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="int-status">Status</Label>
                <Select
                  value={createForm.status}
                  onValueChange={(v) =>
                    setCreateForm({ ...createForm, status: v })
                  }
                >
                  <SelectTrigger id="int-status">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="int-settings">Settings (JSON)</Label>
                <Textarea
                  id="int-settings"
                  value={createSettingsJson}
                  onChange={(e) => setCreateSettingsJson(e.target.value)}
                  rows={4}
                  className="font-mono text-sm"
                  placeholder='{"api_key": "...", "webhook_secret": "..."}'
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setCreateOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Edit Integration Dialog */}
      <Dialog
        open={!!editIntegration}
        onOpenChange={(open) => !open && setEditIntegration(null)}
      >
        <DialogContent className="sm:max-w-[500px]">
          <form onSubmit={handleEdit}>
            <DialogHeader>
              <DialogTitle>Configure Integration</DialogTitle>
              <DialogDescription>
                Update integration settings for {editIntegration?.provider_type}
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="edit-int-status">Status</Label>
                <Select
                  value={editForm.status ?? ''}
                  onValueChange={(v) =>
                    setEditForm({ ...editForm, status: v })
                  }
                >
                  <SelectTrigger id="edit-int-status">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-int-settings">Settings (JSON)</Label>
                <Textarea
                  id="edit-int-settings"
                  value={editSettingsJson}
                  onChange={(e) => setEditSettingsJson(e.target.value)}
                  rows={6}
                  className="font-mono text-sm"
                />
              </div>
              {editIntegration?.error_details && (
                <Card className="border-destructive">
                  <CardHeader className="py-3">
                    <CardTitle className="text-sm text-destructive">Error Details</CardTitle>
                  </CardHeader>
                  <CardContent className="py-0 pb-3">
                    <pre className="text-xs whitespace-pre-wrap text-muted-foreground">
                      {JSON.stringify(editIntegration.error_details, null, 2)}
                    </pre>
                  </CardContent>
                </Card>
              )}
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditIntegration(null)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? 'Saving...' : 'Save'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteIntegration}
        onOpenChange={(open) => !open && setDeleteIntegration(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Integration</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete the {deleteIntegration?.provider_type}{' '}
              integration? This action cannot be undone.
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

// ─── Main Settings Page ────────────────────────────────────────────────────────

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Settings</h2>
        <p className="text-muted-foreground">
          Configure your billing platform
        </p>
      </div>

      <Tabs defaultValue="organization">
        <TabsList>
          <TabsTrigger value="organization">
            <Building className="mr-2 h-4 w-4" />
            Organization
          </TabsTrigger>
          <TabsTrigger value="api-keys">
            <Key className="mr-2 h-4 w-4" />
            API Keys
          </TabsTrigger>
          <TabsTrigger value="webhooks">
            <Bell className="mr-2 h-4 w-4" />
            Webhooks
          </TabsTrigger>
          <TabsTrigger value="dunning">
            <Megaphone className="mr-2 h-4 w-4" />
            Dunning
          </TabsTrigger>
          <TabsTrigger value="integrations">
            <Plug className="mr-2 h-4 w-4" />
            Integrations
          </TabsTrigger>
        </TabsList>

        <TabsContent value="organization">
          <OrganizationTab />
        </TabsContent>

        <TabsContent value="api-keys">
          <ApiKeysTab />
        </TabsContent>

        <TabsContent value="webhooks">
          <WebhooksTab />
        </TabsContent>

        <TabsContent value="dunning">
          <DunningCampaignsTab />
        </TabsContent>

        <TabsContent value="integrations">
          <IntegrationsTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
