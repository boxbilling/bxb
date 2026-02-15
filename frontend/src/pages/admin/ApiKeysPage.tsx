import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Key,
  Plus,
  MoreHorizontal,
  Trash2,
  Copy,
  RefreshCw,
} from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'

import {
  organizationsApi,
  ApiError,
} from '@/lib/api'
import type {
  ApiKeyCreate,
  ApiKeyCreateResponse,
  ApiKey,
} from '@/types/billing'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
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

export default function ApiKeysPage() {
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [rawKeyDialog, setRawKeyDialog] = useState<string | null>(null)
  const [revokeKey, setRevokeKey] = useState<ApiKey | null>(null)
  const [rotateKey, setRotateKey] = useState<ApiKey | null>(null)
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

  const rotateMutation = useMutation({
    mutationFn: (id: string) => organizationsApi.rotateApiKey(id),
    onSuccess: (response: ApiKeyCreateResponse) => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
      setRotateKey(null)
      setRawKeyDialog(response.raw_key)
      toast.success('API key rotated')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to rotate API key'
      toast.error(message)
    },
  })

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(createForm)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">API Keys</h2>
          <p className="text-muted-foreground">
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
                        {key.status === 'active' && (
                          <DropdownMenuItem
                            onClick={() => setRotateKey(key)}
                          >
                            <RefreshCw className="mr-2 h-4 w-4" />
                            Rotate
                          </DropdownMenuItem>
                        )}
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

      {/* Rotate Confirmation */}
      <AlertDialog
        open={!!rotateKey}
        onOpenChange={(open) => !open && setRotateKey(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Rotate API Key</AlertDialogTitle>
            <AlertDialogDescription>
              This will revoke &quot;{rotateKey?.name || 'Unnamed'}&quot; and
              create a new key with the same configuration. The old key will
              immediately stop working.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                rotateKey && rotateMutation.mutate(rotateKey.id)
              }
            >
              {rotateMutation.isPending ? 'Rotating...' : 'Rotate'}
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
