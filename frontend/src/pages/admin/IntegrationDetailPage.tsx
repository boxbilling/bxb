import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { toast } from 'sonner'
import {
  ArrowLeft,
  CheckCircle,
  AlertCircle,
  Clock,
  Zap,
  Users,
  ArrowRightLeft,
  History,
  AlertTriangle,
  Settings,
  Loader2,
  Trash2,
  Pencil,
  Plug,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useSetBreadcrumbs } from '@/components/HeaderBreadcrumb'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
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
import { integrationsApi, ApiError } from '@/lib/api'
import type { Integration, IntegrationUpdate } from '@/lib/api'
import type { IntegrationCustomerResponse, IntegrationMappingResponse, IntegrationSyncHistoryResponse } from '@/lib/api'

// Provider-specific settings field definitions
const PROVIDER_SETTINGS_FIELDS: Record<string, { key: string; label: string; type: 'text' | 'password'; placeholder: string }[]> = {
  stripe: [
    { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'sk_live_...' },
    { key: 'webhook_secret', label: 'Webhook Secret', type: 'password', placeholder: 'whsec_...' },
  ],
  gocardless: [
    { key: 'access_token', label: 'Access Token', type: 'password', placeholder: 'Enter access token' },
    { key: 'environment', label: 'Environment', type: 'text', placeholder: 'sandbox or live' },
  ],
  adyen: [
    { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'Enter API key' },
    { key: 'merchant_account', label: 'Merchant Account', type: 'text', placeholder: 'YourMerchantAccount' },
    { key: 'environment', label: 'Environment', type: 'text', placeholder: 'test or live' },
  ],
  netsuite: [
    { key: 'account_id', label: 'Account ID', type: 'text', placeholder: 'TSTDRV123456' },
    { key: 'consumer_key', label: 'Consumer Key', type: 'password', placeholder: 'Enter consumer key' },
    { key: 'consumer_secret', label: 'Consumer Secret', type: 'password', placeholder: 'Enter consumer secret' },
    { key: 'token', label: 'Token ID', type: 'password', placeholder: 'Enter token' },
    { key: 'token_secret', label: 'Token Secret', type: 'password', placeholder: 'Enter token secret' },
  ],
  xero: [
    { key: 'tenant_id', label: 'Tenant ID', type: 'text', placeholder: 'Enter tenant ID' },
    { key: 'client_id', label: 'Client ID', type: 'text', placeholder: 'Enter client ID' },
    { key: 'client_secret', label: 'Client Secret', type: 'password', placeholder: 'Enter client secret' },
  ],
  hubspot: [
    { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'Enter HubSpot API key' },
    { key: 'portal_id', label: 'Portal ID', type: 'text', placeholder: '12345678' },
  ],
  salesforce: [
    { key: 'client_id', label: 'Client ID', type: 'text', placeholder: 'Enter client ID' },
    { key: 'client_secret', label: 'Client Secret', type: 'password', placeholder: 'Enter client secret' },
    { key: 'instance_url', label: 'Instance URL', type: 'text', placeholder: 'https://yourorg.salesforce.com' },
  ],
  anrok: [
    { key: 'api_key', label: 'API Key', type: 'password', placeholder: 'Enter Anrok API key' },
  ],
  avalara: [
    { key: 'account_id', label: 'Account ID', type: 'text', placeholder: 'Enter account ID' },
    { key: 'license_key', label: 'License Key', type: 'password', placeholder: 'Enter license key' },
    { key: 'environment', label: 'Environment', type: 'text', placeholder: 'sandbox or production' },
  ],
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'active')
    return (
      <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300">
        <CheckCircle className="mr-1 h-3 w-3" />
        Active
      </Badge>
    )
  if (status === 'error')
    return (
      <Badge variant="destructive">
        <AlertCircle className="mr-1 h-3 w-3" />
        Error
      </Badge>
    )
  return <Badge variant="secondary">Inactive</Badge>
}

function SyncStatusBadge({ status }: { status: string }) {
  switch (status) {
    case 'success':
      return <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300">Success</Badge>
    case 'error':
      return <Badge variant="destructive">Error</Badge>
    case 'running':
      return (
        <Badge variant="outline" className="text-blue-600 border-blue-300">
          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          Running
        </Badge>
      )
    default:
      return <Badge variant="secondary">{status}</Badge>
  }
}

function SyncStatusIndicator({ integration }: { integration: Integration }) {
  const isActive = integration.status === 'active'
  const hasError = integration.status === 'error'
  const lastSync = integration.last_sync_at
    ? format(new Date(integration.last_sync_at), 'PPp')
    : 'Never'

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">Sync Status</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2">
          <div
            className={`h-3 w-3 rounded-full ${
              hasError
                ? 'bg-red-500'
                : isActive
                  ? 'bg-green-500 animate-pulse'
                  : 'bg-gray-400'
            }`}
          />
          <span className="text-sm font-medium">
            {hasError ? 'Sync Error' : isActive ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        <div className="text-sm text-muted-foreground">
          <Clock className="inline h-3 w-3 mr-1" />
          Last sync: {lastSync}
        </div>
      </CardContent>
    </Card>
  )
}

function ProviderSettingsForm({
  integration,
  onSave,
  isSaving,
}: {
  integration: Integration
  onSave: (data: IntegrationUpdate) => void
  isSaving: boolean
}) {
  const providerFields = PROVIDER_SETTINGS_FIELDS[integration.provider_type]
  const [settings, setSettings] = useState<Record<string, string>>(
    Object.fromEntries(
      Object.entries(integration.settings).map(([k, v]) => [k, String(v ?? '')])
    )
  )
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({})
  const [integrationStatus, setIntegrationStatus] = useState(integration.status)

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault()
    const cleaned: Record<string, string> = {}
    for (const [key, val] of Object.entries(settings)) {
      if (val.trim()) cleaned[key] = val.trim()
    }
    onSave({ settings: cleaned, status: integrationStatus })
  }

  if (!providerFields) {
    // Fallback to JSON editor for unknown providers
    const [jsonText, setJsonText] = useState(JSON.stringify(integration.settings, null, 2))

    const handleJsonSave = (e: React.FormEvent) => {
      e.preventDefault()
      try {
        const parsed = JSON.parse(jsonText)
        onSave({ settings: parsed, status: integrationStatus })
      } catch {
        toast.error('Invalid JSON in settings')
      }
    }

    return (
      <form onSubmit={handleJsonSave} className="space-y-4">
        <div className="space-y-2">
          <Label>Status</Label>
          <Select value={integrationStatus} onValueChange={setIntegrationStatus}>
            <SelectTrigger className="w-full md:w-[200px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="inactive">Inactive</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Settings (JSON)</Label>
          <textarea
            className="flex min-h-[160px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
          />
        </div>
        <Button type="submit" disabled={isSaving}>
          {isSaving ? 'Saving...' : 'Save Settings'}
        </Button>
      </form>
    )
  }

  return (
    <form onSubmit={handleSave} className="space-y-4">
      <div className="space-y-2">
        <Label>Status</Label>
        <Select value={integrationStatus} onValueChange={setIntegrationStatus}>
          <SelectTrigger className="w-full md:w-[200px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="inactive">Inactive</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {providerFields.map((field) => (
          <div key={field.key} className="space-y-2">
            <Label htmlFor={`setting-${field.key}`}>{field.label}</Label>
            <div className="flex gap-2">
              <Input
                id={`setting-${field.key}`}
                type={field.type === 'password' && !showSecrets[field.key] ? 'password' : 'text'}
                value={settings[field.key] ?? ''}
                onChange={(e) => setSettings({ ...settings, [field.key]: e.target.value })}
                placeholder={field.placeholder}
              />
              {field.type === 'password' && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowSecrets({ ...showSecrets, [field.key]: !showSecrets[field.key] })}
                >
                  {showSecrets[field.key] ? 'Hide' : 'Show'}
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>

      <Button type="submit" disabled={isSaving}>
        {isSaving ? 'Saving...' : 'Save Settings'}
      </Button>
    </form>
  )
}

export default function IntegrationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [syncHistoryFilter, setSyncHistoryFilter] = useState<{ status?: string; resource_type?: string }>({})

  const { data: integration, isLoading, error } = useQuery({
    queryKey: ['integration', id],
    queryFn: () => integrationsApi.get(id!),
    enabled: !!id,
  })

  const { data: customers } = useQuery({
    queryKey: ['integration-customers', id],
    queryFn: () => integrationsApi.listCustomers(id!),
    enabled: !!id,
  })

  const { data: mappings } = useQuery({
    queryKey: ['integration-mappings', id],
    queryFn: () => integrationsApi.listMappings(id!),
    enabled: !!id,
  })

  const { data: syncHistory } = useQuery({
    queryKey: ['integration-sync-history', id, syncHistoryFilter],
    queryFn: () => integrationsApi.listSyncHistory(id!, syncHistoryFilter),
    enabled: !!id,
  })

  const updateMutation = useMutation({
    mutationFn: (data: IntegrationUpdate) => integrationsApi.update(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integration', id] })
      toast.success('Integration updated successfully')
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : 'Failed to update integration')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => integrationsApi.delete(id!),
    onSuccess: () => {
      toast.success('Integration deleted')
      navigate('/admin/integrations')
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : 'Failed to delete integration')
    },
  })

  const testConnectionMutation = useMutation({
    mutationFn: () => integrationsApi.testConnection(id!),
    onSuccess: (result) => {
      if (result.success) {
        toast.success('Connection test passed')
      } else {
        toast.error(result.error || 'Connection test failed')
      }
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : 'Connection test failed')
    },
  })

  useSetBreadcrumbs([
    { label: 'Integrations', href: '/admin/integrations' },
    { label: integration?.provider_type ?? 'Integration' },
  ])

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Integration not found or failed to load.</p>
      </div>
    )
  }

  if (isLoading || !integration) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-6 w-64" />
        <div className="grid gap-4 grid-cols-2 md:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-16" />
              </CardContent>
            </Card>
          ))}
        </div>
        <Skeleton className="h-[400px] w-full" />
      </div>
    )
  }

  const errorEntries = syncHistory?.filter((s) => s.status === 'error') ?? []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-4">
          <Link to="/admin/integrations">
            <Button variant="ghost" size="icon" className="self-start">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-bold tracking-tight capitalize">{integration.provider_type}</h2>
              <StatusBadge status={integration.status} />
            </div>
            <p className="text-muted-foreground capitalize">{integration.integration_type} Integration</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => testConnectionMutation.mutate()}
            disabled={testConnectionMutation.isPending}
            className="w-full md:w-auto"
          >
            {testConnectionMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Zap className="mr-2 h-4 w-4" />
            )}
            Test Connection
          </Button>
          <Button
            variant="outline"
            className="text-destructive w-full md:w-auto"
            onClick={() => setDeleteOpen(true)}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 grid-cols-2 md:grid-cols-4">
        <SyncStatusIndicator integration={integration} />
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Customer Mappings</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{customers?.length ?? 0}</div>
            <p className="text-xs text-muted-foreground">linked customers</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Field Mappings</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{mappings?.length ?? 0}</div>
            <p className="text-xs text-muted-foreground">resource mappings</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Recent Errors</CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${errorEntries.length > 0 ? 'text-destructive' : ''}`}>
              {errorEntries.length}
            </div>
            <p className="text-xs text-muted-foreground">sync errors</p>
          </CardContent>
        </Card>
      </div>

      {/* Error banner if integration is in error state */}
      {integration.status === 'error' && integration.error_details && (
        <Card className="border-destructive">
          <CardContent className="flex items-start gap-3 py-4">
            <AlertTriangle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-destructive">Integration Error</p>
              <pre className="text-sm text-muted-foreground mt-1 whitespace-pre-wrap font-mono">
                {JSON.stringify(integration.error_details, null, 2)}
              </pre>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tabs */}
      <Tabs defaultValue="settings">
        <div className="overflow-x-auto">
          <TabsList>
            <TabsTrigger value="settings">
              <Settings className="mr-2 h-4 w-4" />
              Settings
            </TabsTrigger>
            <TabsTrigger value="customers">
              <Users className="mr-2 h-4 w-4" />
              Customer Mappings
            </TabsTrigger>
            <TabsTrigger value="mappings">
              <ArrowRightLeft className="mr-2 h-4 w-4" />
              Field Mappings
            </TabsTrigger>
            <TabsTrigger value="sync-history">
              <History className="mr-2 h-4 w-4" />
              Sync History
            </TabsTrigger>
            <TabsTrigger value="errors">
              <AlertCircle className="mr-2 h-4 w-4" />
              Error Log
            </TabsTrigger>
          </TabsList>
        </div>

        {/* Settings Tab */}
        <TabsContent value="settings" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Provider Settings</CardTitle>
              <CardDescription>
                Configure connection settings for {integration.provider_type}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ProviderSettingsForm
                integration={integration}
                onSave={(data) => updateMutation.mutate(data)}
                isSaving={updateMutation.isPending}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Integration Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">ID</span>
                <span className="font-mono">{integration.id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Type</span>
                <span className="capitalize">{integration.integration_type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Provider</span>
                <span className="capitalize">{integration.provider_type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Created</span>
                <span>{format(new Date(integration.created_at), 'PPp')}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Updated</span>
                <span>{format(new Date(integration.updated_at), 'PPp')}</span>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Customer Mappings Tab */}
        <TabsContent value="customers">
          <Card>
            <CardHeader>
              <CardTitle>Customer Mappings</CardTitle>
              <CardDescription>
                Customers linked to their external {integration.provider_type} counterparts
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!customers || customers.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Users className="h-12 w-12 mb-4" />
                  <p>No customer mappings configured</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Customer ID</TableHead>
                        <TableHead>External Customer ID</TableHead>
                        <TableHead className="hidden md:table-cell">Settings</TableHead>
                        <TableHead className="hidden md:table-cell">Created</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {customers.map((cm) => (
                        <TableRow key={cm.id}>
                          <TableCell className="font-mono text-xs">{cm.customer_id}</TableCell>
                          <TableCell className="font-mono text-xs">{cm.external_customer_id}</TableCell>
                          <TableCell className="hidden md:table-cell">
                            {cm.settings
                              ? Object.keys(cm.settings).length + ' keys'
                              : '-'}
                          </TableCell>
                          <TableCell className="hidden md:table-cell">{format(new Date(cm.created_at), 'PP')}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Field Mappings Tab */}
        <TabsContent value="mappings">
          <Card>
            <CardHeader>
              <CardTitle>Field Mappings</CardTitle>
              <CardDescription>
                Resource mappings between bxb and {integration.provider_type}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!mappings || mappings.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <ArrowRightLeft className="h-12 w-12 mb-4" />
                  <p>No field mappings configured</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Resource Type</TableHead>
                        <TableHead>Resource ID</TableHead>
                        <TableHead>External ID</TableHead>
                        <TableHead className="hidden md:table-cell">Last Synced</TableHead>
                        <TableHead className="hidden md:table-cell">Created</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {mappings.map((m) => (
                        <TableRow key={m.id}>
                          <TableCell>
                            <Badge variant="outline" className="capitalize">{m.mappable_type}</Badge>
                          </TableCell>
                          <TableCell className="font-mono text-xs">{m.mappable_id}</TableCell>
                          <TableCell className="font-mono text-xs">{m.external_id}</TableCell>
                          <TableCell className="hidden md:table-cell">
                            {m.last_synced_at
                              ? format(new Date(m.last_synced_at), 'PPp')
                              : 'Never'}
                          </TableCell>
                          <TableCell className="hidden md:table-cell">{format(new Date(m.created_at), 'PP')}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Sync History Tab */}
        <TabsContent value="sync-history" className="space-y-4">
          <div className="flex flex-col gap-4 md:flex-row md:items-center">
            <Select
              value={syncHistoryFilter.status ?? 'all'}
              onValueChange={(v) =>
                setSyncHistoryFilter({ ...syncHistoryFilter, status: v === 'all' ? undefined : v })
              }
            >
              <SelectTrigger className="w-full md:w-[160px]">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="success">Success</SelectItem>
                <SelectItem value="error">Error</SelectItem>
                <SelectItem value="running">Running</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={syncHistoryFilter.resource_type ?? 'all'}
              onValueChange={(v) =>
                setSyncHistoryFilter({ ...syncHistoryFilter, resource_type: v === 'all' ? undefined : v })
              }
            >
              <SelectTrigger className="w-full md:w-[180px]">
                <SelectValue placeholder="Filter by resource" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All resources</SelectItem>
                <SelectItem value="customer">Customer</SelectItem>
                <SelectItem value="invoice">Invoice</SelectItem>
                <SelectItem value="payment">Payment</SelectItem>
                <SelectItem value="subscription">Subscription</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Card>
            <CardContent className="pt-6">
              {!syncHistory || syncHistory.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <History className="h-12 w-12 mb-4" />
                  <p>No sync history</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Action</TableHead>
                        <TableHead>Resource</TableHead>
                        <TableHead className="hidden md:table-cell">External ID</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Started</TableHead>
                        <TableHead className="hidden md:table-cell">Error</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {syncHistory.map((entry) => (
                        <TableRow key={entry.id}>
                          <TableCell className="capitalize">{entry.action}</TableCell>
                          <TableCell>
                            <Badge variant="outline" className="capitalize">{entry.resource_type}</Badge>
                          </TableCell>
                          <TableCell className="hidden md:table-cell font-mono text-xs">{entry.external_id ?? '-'}</TableCell>
                          <TableCell>
                            <SyncStatusBadge status={entry.status} />
                          </TableCell>
                          <TableCell>{format(new Date(entry.started_at), 'PPp')}</TableCell>
                          <TableCell className="hidden md:table-cell max-w-[200px] truncate text-destructive text-xs">
                            {entry.error_message ?? '-'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Error Log Tab */}
        <TabsContent value="errors">
          <Card>
            <CardHeader>
              <CardTitle>Error Log</CardTitle>
              <CardDescription>
                Recent sync errors and failure details
              </CardDescription>
            </CardHeader>
            <CardContent>
              {errorEntries.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <CheckCircle className="h-12 w-12 mb-4 text-green-500" />
                  <p>No errors recorded</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {errorEntries.map((entry) => (
                    <Card key={entry.id} className="border-destructive/50">
                      <CardContent className="py-3">
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-2">
                            <AlertCircle className="h-4 w-4 text-destructive mt-0.5 shrink-0" />
                            <div>
                              <p className="text-sm font-medium">
                                {entry.action} - {entry.resource_type}
                              </p>
                              <p className="text-sm text-destructive mt-1">{entry.error_message}</p>
                              {entry.details && (
                                <pre className="text-xs text-muted-foreground mt-2 font-mono whitespace-pre-wrap">
                                  {JSON.stringify(entry.details, null, 2)}
                                </pre>
                              )}
                            </div>
                          </div>
                          <span className="text-xs text-muted-foreground whitespace-nowrap ml-4">
                            {format(new Date(entry.started_at), 'PPp')}
                          </span>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Integration</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete the {integration.integration_type} integration
              ({integration.provider_type})? This will remove all customer mappings, field
              mappings, and sync history.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMutation.mutate()}
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
