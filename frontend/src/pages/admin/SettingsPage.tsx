import { useState, useMemo } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Check, ChevronsUpDown, Eye, EyeOff, Loader2, Mail } from 'lucide-react'

import {
  organizationsApi,
  ApiError,
} from '@/lib/api'
import { useOrganization } from '@/hooks/use-organization'
import type { OrganizationUpdate } from '@/types/billing'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'

const CURRENCIES = [
  { value: 'USD', label: 'USD - US Dollar' },
  { value: 'EUR', label: 'EUR - Euro' },
  { value: 'GBP', label: 'GBP - British Pound' },
  { value: 'CAD', label: 'CAD - Canadian Dollar' },
  { value: 'AUD', label: 'AUD - Australian Dollar' },
  { value: 'JPY', label: 'JPY - Japanese Yen' },
  { value: 'CHF', label: 'CHF - Swiss Franc' },
  { value: 'CNY', label: 'CNY - Chinese Yuan' },
  { value: 'INR', label: 'INR - Indian Rupee' },
  { value: 'BRL', label: 'BRL - Brazilian Real' },
  { value: 'MXN', label: 'MXN - Mexican Peso' },
  { value: 'SEK', label: 'SEK - Swedish Krona' },
  { value: 'NOK', label: 'NOK - Norwegian Krone' },
  { value: 'DKK', label: 'DKK - Danish Krone' },
  { value: 'SGD', label: 'SGD - Singapore Dollar' },
  { value: 'HKD', label: 'HKD - Hong Kong Dollar' },
  { value: 'KRW', label: 'KRW - South Korean Won' },
  { value: 'NZD', label: 'NZD - New Zealand Dollar' },
  { value: 'ZAR', label: 'ZAR - South African Rand' },
  { value: 'PLN', label: 'PLN - Polish Zloty' },
]

const TIMEZONES = (Intl as unknown as { supportedValuesOf(key: string): string[] }).supportedValuesOf('timeZone')

type ValidationErrors = Partial<Record<keyof OrganizationUpdate, string>>

function validateEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

function validateUrl(url: string): boolean {
  try {
    new URL(url)
    return true
  } catch {
    return false
  }
}

function validateSection(
  section: 'general' | 'billing' | 'branding' | 'legal',
  formData: OrganizationUpdate,
): ValidationErrors {
  const errors: ValidationErrors = {}

  if (section === 'general') {
    if (!formData.name?.trim()) {
      errors.name = 'Organization name is required'
    }
    if (!formData.default_currency) {
      errors.default_currency = 'Currency is required'
    }
    if (!formData.timezone) {
      errors.timezone = 'Timezone is required'
    }
  }

  if (section === 'billing') {
    if (
      formData.invoice_grace_period != null &&
      formData.invoice_grace_period < 0
    ) {
      errors.invoice_grace_period = 'Grace period cannot be negative'
    }
    if (formData.net_payment_term != null && formData.net_payment_term < 0) {
      errors.net_payment_term = 'Payment term cannot be negative'
    }
  }

  if (section === 'branding') {
    if (formData.logo_url && !validateUrl(formData.logo_url)) {
      errors.logo_url = 'Please enter a valid URL'
    }
    if (formData.email && !validateEmail(formData.email)) {
      errors.email = 'Please enter a valid email address'
    }
    if (formData.portal_accent_color && !/^#[0-9a-fA-F]{6}$/.test(formData.portal_accent_color)) {
      errors.portal_accent_color = 'Please enter a valid hex color (e.g. #ff6600)'
    }
  }

  return errors
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null
  return <p className="text-sm text-destructive">{message}</p>
}

function SectionSaveButton({
  onClick,
  isPending,
  disabled,
}: {
  onClick: () => void
  isPending: boolean
  disabled: boolean
}) {
  return (
    <div className="flex justify-end pt-2">
      <Button
        type="button"
        size="sm"
        onClick={onClick}
        disabled={isPending || disabled}
      >
        {isPending ? (
          <>
            <Loader2 className="animate-spin" />
            Saving...
          </>
        ) : (
          'Save'
        )}
      </Button>
    </div>
  )
}

function SearchableSelect({
  value,
  onSelect,
  options,
  placeholder,
  searchPlaceholder,
  emptyMessage,
  id,
}: {
  value: string
  onSelect: (value: string) => void
  options: { value: string; label: string }[]
  placeholder: string
  searchPlaceholder: string
  emptyMessage: string
  id?: string
}) {
  const [open, setOpen] = useState(false)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between font-normal"
        >
          {value
            ? options.find((o) => o.value === value)?.label ?? value
            : placeholder}
          <ChevronsUpDown className="opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0">
        <Command>
          <CommandInput placeholder={searchPlaceholder} />
          <CommandList>
            <CommandEmpty>{emptyMessage}</CommandEmpty>
            <CommandGroup>
              {options.map((option) => (
                <CommandItem
                  key={option.value}
                  value={option.label}
                  onSelect={() => {
                    onSelect(option.value)
                    setOpen(false)
                  }}
                >
                  {option.label}
                  <Check
                    className={cn(
                      'ml-auto',
                      value === option.value ? 'opacity-100' : 'opacity-0',
                    )}
                  />
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}

export default function SettingsPage() {
  const queryClient = useQueryClient()

  const { data: org, isLoading } = useOrganization()

  const [formData, setFormData] = useState<OrganizationUpdate>({})
  const [initialized, setInitialized] = useState(false)
  const [touched, setTouched] = useState<Set<keyof OrganizationUpdate>>(
    new Set(),
  )
  const [savingSection, setSavingSection] = useState<string | null>(null)
  const [showHmacKey, setShowHmacKey] = useState(false)

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
      portal_accent_color: org.portal_accent_color,
      portal_welcome_message: org.portal_welcome_message,
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
    onSuccess: (_data, _variables, _context) => {
      queryClient.invalidateQueries({ queryKey: ['organization'] })
      toast.success('Settings saved')
      setSavingSection(null)
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to update settings'
      toast.error(message)
      setSavingSection(null)
    },
  })

  const updateField = (
    field: keyof OrganizationUpdate,
    value: string | number | null,
  ) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
    setTouched((prev) => new Set(prev).add(field))
  }

  const generalErrors = useMemo(
    () => validateSection('general', formData),
    [formData],
  )
  const billingErrors = useMemo(
    () => validateSection('billing', formData),
    [formData],
  )
  const brandingErrors = useMemo(
    () => validateSection('branding', formData),
    [formData],
  )

  const timezoneOptions = useMemo(
    () => TIMEZONES.map((tz) => ({ value: tz, label: tz.replace(/_/g, ' ') })),
    [],
  )

  const saveSection = (
    section: 'general' | 'billing' | 'branding' | 'legal',
  ) => {
    const errors = validateSection(section, formData)
    if (Object.keys(errors).length > 0) {
      // Mark all section fields as touched to show errors
      const sectionFields: Record<string, (keyof OrganizationUpdate)[]> = {
        general: ['name', 'default_currency', 'timezone'],
        billing: [
          'invoice_grace_period',
          'net_payment_term',
          'document_number_prefix',
          'hmac_key',
        ],
        branding: ['logo_url', 'email', 'portal_accent_color', 'portal_welcome_message'],
        legal: [
          'legal_name',
          'address_line1',
          'address_line2',
          'city',
          'state',
          'zipcode',
          'country',
        ],
      }
      setTouched((prev) => {
        const next = new Set(prev)
        for (const f of sectionFields[section]) next.add(f)
        return next
      })
      toast.error('Please fix validation errors before saving')
      return
    }
    setSavingSection(section)
    updateMutation.mutate(formData)
  }

  const hasError = (field: keyof OrganizationUpdate, errors: ValidationErrors) =>
    touched.has(field) && errors[field]

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-64 mt-2" />
        </div>
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
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">
          Organization Settings
        </h2>
        <p className="text-muted-foreground">
          Configure your organization's billing and branding
        </p>
      </div>

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
              aria-invalid={!!hasError('name', generalErrors)}
            />
            <FieldError
              message={
                hasError('name', generalErrors)
                  ? generalErrors.name
                  : undefined
              }
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="currency">Default Currency</Label>
              <SearchableSelect
                id="currency"
                value={formData.default_currency ?? ''}
                onSelect={(v) => updateField('default_currency', v)}
                options={CURRENCIES}
                placeholder="Select currency..."
                searchPlaceholder="Search currencies..."
                emptyMessage="No currency found."
              />
              <FieldError
                message={
                  hasError('default_currency', generalErrors)
                    ? generalErrors.default_currency
                    : undefined
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="timezone">Timezone</Label>
              <SearchableSelect
                id="timezone"
                value={formData.timezone ?? ''}
                onSelect={(v) => updateField('timezone', v)}
                options={timezoneOptions}
                placeholder="Select timezone..."
                searchPlaceholder="Search timezones..."
                emptyMessage="No timezone found."
              />
              <FieldError
                message={
                  hasError('timezone', generalErrors)
                    ? generalErrors.timezone
                    : undefined
                }
              />
            </div>
          </div>
          <SectionSaveButton
            onClick={() => saveSection('general')}
            isPending={
              updateMutation.isPending && savingSection === 'general'
            }
            disabled={updateMutation.isPending && savingSection !== 'general'}
          />
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
              <Label htmlFor="grace-period">
                Invoice Grace Period (days)
              </Label>
              <Input
                id="grace-period"
                type="number"
                min={0}
                value={formData.invoice_grace_period ?? 0}
                onChange={(e) =>
                  updateField(
                    'invoice_grace_period',
                    parseInt(e.target.value) || 0,
                  )
                }
                aria-invalid={
                  !!hasError('invoice_grace_period', billingErrors)
                }
              />
              <FieldError
                message={
                  hasError('invoice_grace_period', billingErrors)
                    ? billingErrors.invoice_grace_period
                    : undefined
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="net-term">Net Payment Term (days)</Label>
              <Input
                id="net-term"
                type="number"
                min={0}
                value={formData.net_payment_term ?? 0}
                onChange={(e) =>
                  updateField(
                    'net_payment_term',
                    parseInt(e.target.value) || 0,
                  )
                }
                aria-invalid={!!hasError('net_payment_term', billingErrors)}
              />
              <FieldError
                message={
                  hasError('net_payment_term', billingErrors)
                    ? billingErrors.net_payment_term
                    : undefined
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
                  updateField(
                    'document_number_prefix',
                    e.target.value || null,
                  )
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="hmac-key">HMAC Key</Label>
              <div className="relative">
                <Input
                  id="hmac-key"
                  type={showHmacKey ? 'text' : 'password'}
                  value={formData.hmac_key ?? ''}
                  onChange={(e) =>
                    updateField('hmac_key', e.target.value || null)
                  }
                  className="pr-10"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  className="absolute right-1 top-1/2 -translate-y-1/2"
                  onClick={() => setShowHmacKey((v) => !v)}
                  aria-label={showHmacKey ? 'Hide HMAC key' : 'Show HMAC key'}
                >
                  {showHmacKey ? (
                    <EyeOff className="size-4" />
                  ) : (
                    <Eye className="size-4" />
                  )}
                </Button>
              </div>
            </div>
          </div>
          <SectionSaveButton
            onClick={() => saveSection('billing')}
            isPending={
              updateMutation.isPending && savingSection === 'billing'
            }
            disabled={updateMutation.isPending && savingSection !== 'billing'}
          />
        </CardContent>
      </Card>

      {/* Branding */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Branding</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="logo-url">Logo URL</Label>
                <Input
                  id="logo-url"
                  value={formData.logo_url ?? ''}
                  onChange={(e) =>
                    updateField('logo_url', e.target.value || null)
                  }
                  placeholder="https://example.com/logo.png"
                  aria-invalid={!!hasError('logo_url', brandingErrors)}
                />
                <FieldError
                  message={
                    hasError('logo_url', brandingErrors)
                      ? brandingErrors.logo_url
                      : undefined
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
                  placeholder="billing@example.com"
                  aria-invalid={!!hasError('email', brandingErrors)}
                />
                <FieldError
                  message={
                    hasError('email', brandingErrors)
                      ? brandingErrors.email
                      : undefined
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="portal-accent-color">Portal Accent Color</Label>
                <div className="flex items-center gap-2">
                  <Input
                    id="portal-accent-color"
                    value={formData.portal_accent_color ?? ''}
                    onChange={(e) =>
                      updateField('portal_accent_color', e.target.value || null)
                    }
                    placeholder="#4f46e5"
                    className="flex-1"
                    aria-invalid={!!hasError('portal_accent_color', brandingErrors)}
                  />
                  {formData.portal_accent_color && /^#[0-9a-fA-F]{6}$/.test(formData.portal_accent_color) ? (
                    <div
                      className="h-9 w-9 rounded border shrink-0"
                      style={{ backgroundColor: formData.portal_accent_color }}
                    />
                  ) : null}
                </div>
                <FieldError
                  message={
                    hasError('portal_accent_color', brandingErrors)
                      ? brandingErrors.portal_accent_color
                      : undefined
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="portal-welcome-message">Portal Welcome Message</Label>
                <Input
                  id="portal-welcome-message"
                  value={formData.portal_welcome_message ?? ''}
                  onChange={(e) =>
                    updateField('portal_welcome_message', e.target.value || null)
                  }
                  placeholder="Welcome to your billing portal"
                  maxLength={500}
                />
              </div>
            </div>

            {/* Branding Preview */}
            <div className="space-y-2">
              <Label className="text-muted-foreground text-xs uppercase tracking-wider">
                Invoice Email Preview
              </Label>
              <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
                <div className="flex items-center gap-3 border-b pb-3">
                  {formData.logo_url ? (
                    <img
                      src={formData.logo_url}
                      alt="Logo preview"
                      className="h-8 w-8 rounded object-contain"
                      onError={(e) => {
                        e.currentTarget.style.display = 'none'
                        e.currentTarget.nextElementSibling?.classList.remove(
                          'hidden',
                        )
                      }}
                    />
                  ) : null}
                  <div
                    className={cn(
                      'flex h-8 w-8 items-center justify-center rounded bg-primary/10 text-primary text-xs font-bold',
                      formData.logo_url && 'hidden',
                    )}
                  >
                    {(formData.name ?? 'O').charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <p className="text-sm font-medium">
                      {formData.name || 'Your Organization'}
                    </p>
                    {formData.email ? (
                      <p className="text-xs text-muted-foreground flex items-center gap-1">
                        <Mail className="size-3" />
                        {formData.email}
                      </p>
                    ) : null}
                  </div>
                </div>
                <div className="space-y-1.5">
                  <div className="h-2 w-3/4 rounded bg-muted" />
                  <div className="h-2 w-1/2 rounded bg-muted" />
                  <div className="h-2 w-5/6 rounded bg-muted" />
                </div>
                <div className="rounded border p-2 text-xs text-muted-foreground space-y-1">
                  <div className="flex justify-between">
                    <span>Invoice #INV-001</span>
                    <span className="font-medium">
                      {formData.default_currency ?? 'USD'} 250.00
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Due date</span>
                    <span>
                      Net {formData.net_payment_term ?? 30} days
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <SectionSaveButton
            onClick={() => saveSection('branding')}
            isPending={
              updateMutation.isPending && savingSection === 'branding'
            }
            disabled={
              updateMutation.isPending && savingSection !== 'branding'
            }
          />
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
          <SectionSaveButton
            onClick={() => saveSection('legal')}
            isPending={
              updateMutation.isPending && savingSection === 'legal'
            }
            disabled={updateMutation.isPending && savingSection !== 'legal'}
          />
        </CardContent>
      </Card>
    </div>
  )
}
