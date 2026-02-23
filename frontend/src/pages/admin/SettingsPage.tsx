import { useState, useMemo } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Check, ChevronsUpDown, Eye, EyeOff, Loader2 } from 'lucide-react'

import {
  organizationsApi,
  ApiError,
} from '@/lib/api'
import { useOrganization } from '@/hooks/use-organization'
import type { OrganizationUpdate } from '@/lib/api'

import PageHeader from '@/components/PageHeader'
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

function validateUrl(url: string): boolean {
  try {
    new URL(url)
    return true
  } catch {
    return false
  }
}

function validateSection(
  section: 'general' | 'branding',
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

  if (section === 'branding') {
    if (formData.logo_url && !validateUrl(formData.logo_url)) {
      errors.logo_url = 'Please enter a valid URL'
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
        className="w-full md:w-auto"
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
      hmac_key: org.hmac_key,
      logo_url: org.logo_url,
      portal_accent_color: org.portal_accent_color,
      portal_welcome_message: org.portal_welcome_message,
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
  const brandingErrors = useMemo(
    () => validateSection('branding', formData),
    [formData],
  )

  const timezoneOptions = useMemo(
    () => TIMEZONES.map((tz) => ({ value: tz, label: tz.replace(/_/g, ' ') })),
    [],
  )

  const saveSection = (
    section: 'general' | 'branding',
  ) => {
    const errors = validateSection(section, formData)
    if (Object.keys(errors).length > 0) {
      // Mark all section fields as touched to show errors
      const sectionFields: Record<string, (keyof OrganizationUpdate)[]> = {
        general: ['name', 'default_currency', 'timezone'],
        branding: ['logo_url', 'portal_accent_color', 'portal_welcome_message'],
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
        {Array.from({ length: 2 }).map((_, i) => (
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
      <PageHeader
        title="Organization Settings"
        description="Configure your organization's general settings and branding"
      />

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
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
          <SectionSaveButton
            onClick={() => saveSection('general')}
            isPending={
              updateMutation.isPending && savingSection === 'general'
            }
            disabled={updateMutation.isPending && savingSection !== 'general'}
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
                      loading="lazy"
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
    </div>
  )
}
