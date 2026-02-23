import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Separator } from '@/components/ui/separator'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { billingEntitiesApi, ApiError } from '@/lib/api'
import type { BillingEntityCreate, BillingEntityUpdate } from '@/lib/api'

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

interface FormState {
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
  invoice_grace_period: number
  net_payment_term: number
  invoice_footer: string
  is_default: boolean
}

const defaultFormState: FormState = {
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
  invoice_grace_period: 0,
  net_payment_term: 30,
  invoice_footer: '',
  is_default: false,
}

export default function BillingEntityFormPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { code } = useParams<{ code: string }>()
  const isEdit = !!code

  const [form, setForm] = useState<FormState>(defaultFormState)
  const [initialized, setInitialized] = useState(false)

  const { data: entity, isLoading: loadingEntity } = useQuery({
    queryKey: ['billing-entity', code],
    queryFn: () => billingEntitiesApi.get(code!),
    enabled: isEdit,
  })

  useEffect(() => {
    if (entity && !initialized) {
      setForm({
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
        invoice_grace_period: entity.invoice_grace_period ?? 0,
        net_payment_term: entity.net_payment_term ?? 30,
        invoice_footer: entity.invoice_footer || '',
        is_default: entity.is_default,
      })
      setInitialized(true)
    }
  }, [entity, initialized])

  const createMutation = useMutation({
    mutationFn: (data: BillingEntityCreate) => billingEntitiesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billing-entities'] })
      toast.success('Billing entity created successfully')
      navigate('/admin/billing-entities')
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
      queryClient.invalidateQueries({ queryKey: ['billing-entity', code] })
      toast.success('Billing entity updated successfully')
      navigate('/admin/billing-entities')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to update billing entity'
      toast.error(message)
    },
  })

  const formToCreateData = (f: FormState): BillingEntityCreate => ({
    code: f.code,
    name: f.name,
    legal_name: f.legal_name || null,
    address_line1: f.address_line1 || null,
    address_line2: f.address_line2 || null,
    city: f.city || null,
    state: f.state || null,
    country: f.country || null,
    zip_code: f.zip_code || null,
    tax_id: f.tax_id || null,
    email: f.email || null,
    currency: f.currency,
    timezone: f.timezone,
    document_locale: f.document_locale,
    invoice_prefix: f.invoice_prefix || null,
    next_invoice_number: f.next_invoice_number,
    invoice_grace_period: f.invoice_grace_period,
    net_payment_term: f.net_payment_term,
    invoice_footer: f.invoice_footer || null,
    is_default: f.is_default,
  })

  const formToUpdateData = (f: FormState): BillingEntityUpdate => ({
    name: f.name,
    legal_name: f.legal_name || null,
    address_line1: f.address_line1 || null,
    address_line2: f.address_line2 || null,
    city: f.city || null,
    state: f.state || null,
    country: f.country || null,
    zip_code: f.zip_code || null,
    tax_id: f.tax_id || null,
    email: f.email || null,
    currency: f.currency,
    timezone: f.timezone,
    document_locale: f.document_locale,
    invoice_prefix: f.invoice_prefix || null,
    next_invoice_number: f.next_invoice_number,
    invoice_grace_period: f.invoice_grace_period,
    net_payment_term: f.net_payment_term,
    invoice_footer: f.invoice_footer || null,
    is_default: f.is_default,
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (isEdit) {
      updateMutation.mutate({ code: code!, data: formToUpdateData(form) })
    } else {
      createMutation.mutate(formToCreateData(form))
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending

  if (isEdit && loadingEntity) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-[600px] w-full" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/admin/billing-entities')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h2 className="text-2xl font-bold tracking-tight">
            {isEdit ? 'Edit Billing Entity' : 'Create Billing Entity'}
          </h2>
          <p className="text-muted-foreground">
            {isEdit ? 'Update the billing entity details.' : 'Add a new billing entity for multi-entity billing.'}
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Basic Information */}
          <Card>
            <CardHeader>
              <CardTitle>Basic Information</CardTitle>
              <CardDescription>The entity identifier and display name.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="code">Code *</Label>
                  <Input
                    id="code"
                    value={form.code}
                    onChange={(e) => setForm({ ...form, code: e.target.value })}
                    required
                    disabled={isEdit}
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

              <Separator />

              <div className="flex items-center space-x-2">
                <Switch
                  id="is_default"
                  checked={form.is_default}
                  onCheckedChange={(checked) => setForm({ ...form, is_default: checked })}
                />
                <Label htmlFor="is_default">Default Entity</Label>
              </div>
            </CardContent>
          </Card>

          {/* Address */}
          <Card>
            <CardHeader>
              <CardTitle>Address</CardTitle>
              <CardDescription>Physical address of this billing entity.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
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

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
            </CardContent>
          </Card>

          {/* Locale & Currency Settings */}
          <Card>
            <CardHeader>
              <CardTitle>Locale &amp; Currency</CardTitle>
              <CardDescription>Regional and currency settings for this entity.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
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
            </CardContent>
          </Card>

          {/* Invoice Settings */}
          <Card>
            <CardHeader>
              <CardTitle>Invoice Settings</CardTitle>
              <CardDescription>Configure invoice numbering and payment terms for this entity.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
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

              <Separator />

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="invoice_grace_period">Grace Period (days)</Label>
                  <Input
                    id="invoice_grace_period"
                    type="number"
                    min={0}
                    value={form.invoice_grace_period}
                    onChange={(e) => setForm({ ...form, invoice_grace_period: parseInt(e.target.value) || 0 })}
                  />
                  <p className="text-xs text-muted-foreground">Days after billing period before invoice is finalized.</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="net_payment_term">Net Payment Term (days)</Label>
                  <Input
                    id="net_payment_term"
                    type="number"
                    min={0}
                    value={form.net_payment_term}
                    onChange={(e) => setForm({ ...form, net_payment_term: parseInt(e.target.value) || 0 })}
                  />
                  <p className="text-xs text-muted-foreground">Days allowed for payment after invoice is issued.</p>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="invoice_footer">Invoice Footer</Label>
                <Textarea
                  id="invoice_footer"
                  value={form.invoice_footer}
                  onChange={(e) => setForm({ ...form, invoice_footer: e.target.value })}
                  placeholder="Custom text to appear at the bottom of invoices..."
                  rows={3}
                  maxLength={1024}
                />
                <p className="text-xs text-muted-foreground">{form.invoice_footer.length}/1024 characters</p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-4 mt-6">
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate('/admin/billing-entities')}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={isPending || !form.code || !form.name}>
            {isPending
              ? (isEdit ? 'Saving...' : 'Creating...')
              : (isEdit ? 'Save Changes' : 'Create Entity')}
          </Button>
        </div>
      </form>
    </div>
  )
}
