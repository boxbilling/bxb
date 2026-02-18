import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ExternalLink, Copy, Check } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { customersApi, ApiError } from '@/lib/api'

export function PortalLinkDialog({ externalId }: { externalId: string }) {
  const [open, setOpen] = useState(false)
  const [portalUrl, setPortalUrl] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const mutation = useMutation({
    mutationFn: () => customersApi.getPortalUrl(externalId),
    onSuccess: (data) => {
      setPortalUrl(data.portal_url)
      setCopied(false)
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : 'Failed to generate portal link')
    },
  })

  const handleOpen = () => {
    setOpen(true)
    setPortalUrl(null)
    setCopied(false)
    mutation.mutate()
  }

  const handleCopy = async () => {
    if (!portalUrl) return
    await navigator.clipboard.writeText(portalUrl)
    setCopied(true)
    toast.success('Portal link copied to clipboard')
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <>
      <Button variant="default" size="sm" className="w-full md:w-auto" onClick={handleOpen}>
        <ExternalLink className="mr-2 h-4 w-4" />
        Portal Link
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Customer Portal Link</DialogTitle>
            <DialogDescription>
              Share this link with the customer. Link expires in 12 hours.
            </DialogDescription>
          </DialogHeader>
          {mutation.isPending ? (
            <Skeleton className="h-10 w-full" />
          ) : portalUrl ? (
            <div className="flex items-center gap-2">
              <Input readOnly value={portalUrl} className="font-mono text-xs" />
              <Button variant="outline" size="icon" onClick={handleCopy}>
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>
          ) : mutation.isError ? (
            <p className="text-sm text-destructive">Failed to generate portal link.</p>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  )
}
