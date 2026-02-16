import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { User, Check, ChevronsUpDown } from 'lucide-react'
import { toast } from 'sonner'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
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
import { cn } from '@/lib/utils'
import { portalApi } from '@/lib/api'
import { usePortalToken } from '@/layouts/PortalLayout'

const TIMEZONES = (
  Intl as unknown as { supportedValuesOf(key: string): string[] }
).supportedValuesOf('timeZone')

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

export default function PortalProfilePage() {
  const token = usePortalToken()
  const queryClient = useQueryClient()

  const { data: customer, isLoading } = useQuery({
    queryKey: ['portal-customer', token],
    queryFn: () => portalApi.getCustomer(token),
    enabled: !!token,
  })

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [timezone, setTimezone] = useState('')
  const [initialized, setInitialized] = useState(false)

  if (customer && !initialized) {
    setName(customer.name)
    setEmail(customer.email ?? '')
    setTimezone(customer.timezone)
    setInitialized(true)
  }

  const timezoneOptions = useMemo(
    () => TIMEZONES.map((tz) => ({ value: tz, label: tz.replace(/_/g, ' ') })),
    [],
  )

  const updateMutation = useMutation({
    mutationFn: (data: { name?: string; email?: string | null; timezone?: string }) =>
      portalApi.updateProfile(token, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portal-customer', token] })
      toast.success('Profile updated successfully')
    },
    onError: () => {
      toast.error('Failed to update profile')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const data: { name?: string; email?: string | null; timezone?: string } = {}
    if (name !== customer?.name) data.name = name
    if ((email || null) !== (customer?.email ?? null)) data.email = email || null
    if (timezone !== customer?.timezone) data.timezone = timezone
    if (Object.keys(data).length === 0) {
      toast.info('No changes to save')
      return
    }
    updateMutation.mutate(data)
  }

  return (
    <div className="space-y-4 md:space-y-6">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold">Profile</h1>
        <p className="text-sm md:text-base text-muted-foreground">
          Update your profile information
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Personal Information
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your@email.com"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="timezone">Timezone</Label>
                <SearchableSelect
                  id="timezone"
                  value={timezone}
                  onSelect={setTimezone}
                  options={timezoneOptions}
                  placeholder="Select timezone..."
                  searchPlaceholder="Search timezones..."
                  emptyMessage="No timezone found."
                />
              </div>

              <Button
                type="submit"
                disabled={updateMutation.isPending}
              >
                {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
