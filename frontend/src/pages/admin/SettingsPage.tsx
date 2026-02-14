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
} from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'

import { organizationsApi, webhookEndpointsApi, ApiError } from '@/lib/api'
import type {
  OrganizationUpdate,
  ApiKeyCreate,
  ApiKeyCreateResponse,
  ApiKey,
  WebhookEndpoint,
  WebhookEndpointCreate,
  WebhookEndpointUpdate,
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
      </Tabs>
    </div>
  )
}
