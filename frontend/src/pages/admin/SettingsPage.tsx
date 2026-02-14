import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import {
  organizationsApi,
  ApiError,
} from '@/lib/api'
import { useOrganization } from '@/hooks/use-organization'
import type { OrganizationUpdate } from '@/types/billing'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

export default function SettingsPage() {
  const queryClient = useQueryClient()

  const { data: org, isLoading } = useOrganization()

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
        <h2 className="text-2xl font-bold tracking-tight">Organization Settings</h2>
        <p className="text-muted-foreground">
          Configure your organization's billing and branding
        </p>
      </div>

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
    </div>
  )
}
