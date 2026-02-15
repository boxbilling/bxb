import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, Building2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { billingEntitiesApi, ApiError } from '@/lib/api'
import type { BillingEntity, BillingEntityCreate, BillingEntityUpdate } from '@/types/billing'

const CURRENCIES = [
  'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CHF', 'CNY', 'INR', 'BRL',
  'MXN', 'KRW', 'SGD', 'HKD', 'NOK', 'SEK', 'DKK', 'NZD', 'ZAR', 'AED',
]

const TIMEZONES = [
  'UTC', 'US/Eastern', 'US/Central', 'US/Mountain', 'US/Pacific',
  'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Europe/Madrid',
  'Asia/Tokyo', 'Asia/Shanghai', 'Asia/Singapore', 'Asia/Kolkata',
  'Australia/Sydney', 'America/Sao_Paulo', 'America/Toronto',
  'Pacific/Auckland', 'Africa/Johannesburg',
]

const LOCALES = [
  { value: 'en', label: 'English' },
  { value: 'fr', label: 'French' },
  { value: 'de', label: 'German' },
  { value: 'es', label: 'Spanish' },
  { value: 'it', label: 'Italian' },
  { value: 'pt', label: 'Portuguese' },
  { value: 'nl', label: 'Dutch' },
  { value: 'ja', label: 'Japanese' },
  { value: 'zh', label: 'Chinese' },
  { value: 'ko', label: 'Korean' },
]

const COUNTRIES = [
  'US', 'CA', 'GB', 'DE', 'FR', 'ES', 'IT', 'NL', 'BE', 'AT', 'CH',
  'AU', 'NZ', 'JP', 'CN', 'KR', 'SG', 'IN', 'BR', 'MX', 'ZA', 'AE',
  'SE', 'NO', 'DK', 'FI', 'IE', 'PT', 'PL', 'CZ',
]

interface EntityFormState {
  code: string
  name: string
  legal_name: string
  address_line1: string
  address_line2: string
  city: string
  state: string
  country: string
  zip_code: string
  tax_id: string
  email: string
  currency: string
  timezone: string
  document_locale: string
  invoice_prefix: string
  next_invoice_number: number
  is_default: boolean
}

const defaultFormState: EntityFormState = {
  code: '',
  name: '',
  legal_name: '',
  address_line1: '',
  address_line2: '',
  city: '',
  state: '',
  country: '',
  zip_code: '',
  tax_id: '',
  email: '',
  currency: 'USD',
  timezone: 'UTC',
  document_locale: 'en',
  invoice_prefix: '',
  next_invoice_number: 1,
  is_default: false,
}

function EntityFormDialog({
  open,
  onOpenChange,
  entity,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  entity?: BillingEntity
  onSubmit: (data: EntityFormState) => void
  isLoading: boolean
}) {
  const [form, setForm] = useState<EntityFormState>(
    entity
      ? {
          code: entity.code,
          name: entity.name,
          legal_name: entity.legal_name || '',
          address_line1: entity.address_line1 || '',
          address_line2: entity.address_line2 || '',
          city: entity.city || '',
          state: entity.state || '',
          country: entity.country || '',
          zip_code: entity.zip_code || '',
          tax_id: entity.tax_id || '',
          email: entity.email || '',
          currency: entity.currency,
          timezone: entity.timezone,
          document_locale: entity.document_locale,
          invoice_prefix: entity.invoice_prefix || '',
          next_invoice_number: entity.next_invoice_number,
          is_default: entity.is_default,
        }
      : defaultFormState
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(form)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{entity ? 'Edit Billing Entity' : 'Create Billing Entity'}</DialogTitle>
          <DialogDescription>
            {entity ? 'Update the billing entity details.' : 'Add a new billing entity for multi-entity billing.'}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="code">Code *</Label>
                <Input
                  id="code"
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  required
                  disabled={!!entity}
                  placeholder="billing-entity-1"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="name">Name *</Label>
                <Input
                  id="name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  required
                  placeholder="My Entity"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="legal_name">Legal Name</Label>
              <Input
                id="legal_name"
                value={form.legal_name}
                onChange={(e) => setForm({ ...form, legal_name: e.target.value })}
                placeholder="Legal Company Name, Inc."
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="address_line1">Address Line 1</Label>
              <Input
                id="address_line1"
                value={form.address_line1}
                onChange={(e) => setForm({ ...form, address_line1: e.target.value })}
                placeholder="123 Main St"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="address_line2">Address Line 2</Label>
              <Input
                id="address_line2"
                value={form.address_line2}
                onChange={(e) => setForm({ ...form, address_line2: e.target.value })}
                placeholder="Suite 100"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="city">City</Label>
                <Input
                  id="city"
                  value={form.city}
                  onChange={(e) => setForm({ ...form, city: e.target.value })}
                  placeholder="San Francisco"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="state">State</Label>
                <Input
                  id="state"
                  value={form.state}
                  onChange={(e) => setForm({ ...form, state: e.target.value })}
                  placeholder="CA"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="country">Country</Label>
                <Select
                  value={form.country}
                  onValueChange={(value) => setForm({ ...form, country: value })}
                >
                  <SelectTrigger id="country">
                    <SelectValue placeholder="Select country" />
                  </SelectTrigger>
                  <SelectContent>
                    {COUNTRIES.map((c) => (
                      <SelectItem key={c} value={c}>{c}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="zip_code">Zip Code</Label>
                <Input
                  id="zip_code"
                  value={form.zip_code}
                  onChange={(e) => setForm({ ...form, zip_code: e.target.value })}
                  placeholder="94105"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="tax_id">Tax ID</Label>
                <Input
                  id="tax_id"
                  value={form.tax_id}
                  onChange={(e) => setForm({ ...form, tax_id: e.target.value })}
                  placeholder="XX-XXXXXXX"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  placeholder="billing@company.com"
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="currency">Currency</Label>
                <Select
                  value={form.currency}
                  onValueChange={(value) => setForm({ ...form, currency: value })}
                >
                  <SelectTrigger id="currency">
                    <SelectValue placeholder="Select currency" />
                  </SelectTrigger>
                  <SelectContent>
                    {CURRENCIES.map((c) => (
                      <SelectItem key={c} value={c}>{c}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="timezone">Timezone</Label>
                <Select
                  value={form.timezone}
                  onValueChange={(value) => setForm({ ...form, timezone: value })}
                >
                  <SelectTrigger id="timezone">
                    <SelectValue placeholder="Select timezone" />
                  </SelectTrigger>
                  <SelectContent>
                    {TIMEZONES.map((tz) => (
                      <SelectItem key={tz} value={tz}>{tz}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="document_locale">Document Locale</Label>
                <Select
                  value={form.document_locale}
                  onValueChange={(value) => setForm({ ...form, document_locale: value })}
                >
                  <SelectTrigger id="document_locale">
                    <SelectValue placeholder="Select locale" />
                  </SelectTrigger>
                  <SelectContent>
                    {LOCALES.map((l) => (
                      <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="invoice_prefix">Invoice Prefix</Label>
                <Input
                  id="invoice_prefix"
                  value={form.invoice_prefix}
                  onChange={(e) => setForm({ ...form, invoice_prefix: e.target.value })}
                  placeholder="INV-"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="next_invoice_number">Next Invoice Number</Label>
                <Input
                  id="next_invoice_number"
                  type="number"
                  min={1}
                  value={form.next_invoice_number}
                  onChange={(e) => setForm({ ...form, next_invoice_number: parseInt(e.target.value) || 1 })}
                />
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <Switch
                id="is_default"
                checked={form.is_default}
                onCheckedChange={(checked) => setForm({ ...form, is_default: checked })}
              />
              <Label htmlFor="is_default">Default Entity</Label>
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading || !form.code || !form.name}>
              {isLoading ? (entity ? 'Saving...' : 'Creating...') : (entity ? 'Save Changes' : 'Create Entity')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function BillingEntitiesPage() {
  const queryClient = useQueryClient()
  const [formOpen, setFormOpen] = useState(false)
  const [editEntity, setEditEntity] = useState<BillingEntity | undefined>()
  const [deleteEntity, setDeleteEntity] = useState<BillingEntity | undefined>()

  const { data: entities, isLoading } = useQuery({
    queryKey: ['billing-entities'],
    queryFn: () => billingEntitiesApi.list(),
  })

  const createMutation = useMutation({
    mutationFn: (data: BillingEntityCreate) => billingEntitiesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billing-entities'] })
      setFormOpen(false)
      toast.success('Billing entity created successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to create billing entity'
      toast.error(message)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ code, data }: { code: string; data: BillingEntityUpdate }) =>
      billingEntitiesApi.update(code, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billing-entities'] })
      setEditEntity(undefined)
      toast.success('Billing entity updated successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to update billing entity'
      toast.error(message)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (code: string) => billingEntitiesApi.delete(code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billing-entities'] })
      setDeleteEntity(undefined)
      toast.success('Billing entity deleted successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to delete billing entity'
      toast.error(message)
    },
  })

  const handleCreate = (form: EntityFormState) => {
    const data: BillingEntityCreate = {
      code: form.code,
      name: form.name,
      legal_name: form.legal_name || null,
      address_line1: form.address_line1 || null,
      address_line2: form.address_line2 || null,
      city: form.city || null,
      state: form.state || null,
      country: form.country || null,
      zip_code: form.zip_code || null,
      tax_id: form.tax_id || null,
      email: form.email || null,
      currency: form.currency,
      timezone: form.timezone,
      document_locale: form.document_locale,
      invoice_prefix: form.invoice_prefix || null,
      next_invoice_number: form.next_invoice_number,
      is_default: form.is_default,
    }
    createMutation.mutate(data)
  }

  const handleUpdate = (form: EntityFormState) => {
    if (!editEntity) return
    const data: BillingEntityUpdate = {
      name: form.name,
      legal_name: form.legal_name || null,
      address_line1: form.address_line1 || null,
      address_line2: form.address_line2 || null,
      city: form.city || null,
      state: form.state || null,
      country: form.country || null,
      zip_code: form.zip_code || null,
      tax_id: form.tax_id || null,
      email: form.email || null,
      currency: form.currency,
      timezone: form.timezone,
      document_locale: form.document_locale,
      invoice_prefix: form.invoice_prefix || null,
      next_invoice_number: form.next_invoice_number,
      is_default: form.is_default,
    }
    updateMutation.mutate({ code: editEntity.code, data })
  }

  const formatAddress = (entity: BillingEntity) => {
    const parts = [entity.address_line1, entity.city, entity.state, entity.country].filter(Boolean)
    return parts.length > 0 ? parts.join(', ') : null
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Billing Entities</h1>
          <p className="text-muted-foreground">Manage billing entities for multi-entity billing.</p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Entity
        </Button>
      </div>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[...Array(3)].map((_, i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-5 w-40" />
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent className="space-y-2">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-4 w-28" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : !entities || entities.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Building2 className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-muted-foreground">No billing entities found</p>
            <Button variant="outline" className="mt-4" onClick={() => setFormOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create your first entity
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {entities.map((entity) => (
            <Card key={entity.id}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <CardTitle className="text-base">{entity.name}</CardTitle>
                    {entity.legal_name && (
                      <p className="text-sm text-muted-foreground">{entity.legal_name}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    {entity.is_default && (
                      <Badge variant="secondary">Default</Badge>
                    )}
                    <Badge variant="outline">{entity.code}</Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span>{entity.currency}</span>
                  <span>&middot;</span>
                  <span>{entity.timezone}</span>
                </div>

                {formatAddress(entity) && (
                  <p className="text-sm text-muted-foreground">{formatAddress(entity)}</p>
                )}

                {(entity.invoice_prefix || entity.next_invoice_number) && (
                  <p className="text-sm text-muted-foreground">
                    Invoice: {entity.invoice_prefix || ''}{entity.next_invoice_number}
                  </p>
                )}

                <div className="flex items-center gap-2 pt-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setEditEntity(entity)}
                  >
                    <Pencil className="mr-1 h-3.5 w-3.5" />
                    Edit
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={() => setDeleteEntity(entity)}
                  >
                    <Trash2 className="mr-1 h-3.5 w-3.5" />
                    Delete
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create Dialog */}
      <EntityFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={handleCreate}
        isLoading={createMutation.isPending}
      />

      {/* Edit Dialog */}
      <EntityFormDialog
        open={!!editEntity}
        onOpenChange={(open) => !open && setEditEntity(undefined)}
        entity={editEntity}
        onSubmit={handleUpdate}
        isLoading={updateMutation.isPending}
      />

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteEntity} onOpenChange={(open) => !open && setDeleteEntity(undefined)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Billing Entity</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{deleteEntity?.name}&quot;? This action cannot be undone.
              Entities with associated invoices cannot be deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => deleteEntity && deleteMutation.mutate(deleteEntity.code)}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
