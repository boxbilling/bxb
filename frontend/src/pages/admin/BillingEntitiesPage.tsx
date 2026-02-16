import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, Building2, Users, MoreHorizontal, Pencil, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
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
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { TablePagination } from '@/components/TablePagination'
import { billingEntitiesApi, ApiError } from '@/lib/api'
import type { BillingEntity } from '@/types/billing'

const PAGE_SIZE = 20

export default function BillingEntitiesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)
  const [deleteEntity, setDeleteEntity] = useState<BillingEntity | undefined>()

  const { data, isLoading } = useQuery({
    queryKey: ['billing-entities', page, pageSize],
    queryFn: () => billingEntitiesApi.listPaginated({ skip: (page - 1) * pageSize, limit: pageSize }),
  })
  const entities = data?.data
  const totalCount = data?.totalCount ?? 0

  const { data: customerCounts } = useQuery({
    queryKey: ['billing-entity-customer-counts'],
    queryFn: () => billingEntitiesApi.customerCounts(),
  })

  const deleteMutation = useMutation({
    mutationFn: (code: string) => billingEntitiesApi.delete(code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billing-entities'] })
      queryClient.invalidateQueries({ queryKey: ['billing-entity-customer-counts'] })
      setDeleteEntity(undefined)
      toast.success('Billing entity deleted successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to delete billing entity'
      toast.error(message)
    },
  })

  const filteredEntities = entities?.filter((e) => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      e.name.toLowerCase().includes(q) ||
      e.code.toLowerCase().includes(q) ||
      e.legal_name?.toLowerCase().includes(q) ||
      e.email?.toLowerCase().includes(q)
    )
  }) ?? []

  const formatAddress = (entity: BillingEntity) => {
    const parts = [entity.city, entity.state, entity.country].filter(Boolean)
    return parts.length > 0 ? parts.join(', ') : null
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Billing Entities</h1>
          <p className="text-muted-foreground">Manage billing entities for multi-entity billing.</p>
        </div>
        <Button onClick={() => navigate('/admin/billing-entities/new')}>
          <Plus className="mr-2 h-4 w-4" />
          Create Entity
        </Button>
      </div>

      {/* Search Filter */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search entities..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Entity</TableHead>
              <TableHead>Code</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>Currency</TableHead>
              <TableHead>Timezone</TableHead>
              <TableHead>Customers</TableHead>
              <TableHead className="w-[100px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [...Array(3)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-40" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-12" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-12" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                </TableRow>
              ))
            ) : filteredEntities.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-24 text-center">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <Building2 className="h-8 w-8 text-muted-foreground" />
                    <p className="text-muted-foreground">
                      {search ? 'No entities match your search' : 'No billing entities found'}
                    </p>
                    {!search && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-2"
                        onClick={() => navigate('/admin/billing-entities/new')}
                      >
                        <Plus className="mr-2 h-4 w-4" />
                        Create your first entity
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              filteredEntities.map((entity) => {
                const count = customerCounts?.[entity.id] ?? 0
                return (
                  <TableRow key={entity.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        {entity.name}
                        {entity.is_default && (
                          <Badge variant="secondary" className="text-xs">Default</Badge>
                        )}
                      </div>
                      {entity.legal_name && (
                        <p className="text-xs text-muted-foreground">{entity.legal_name}</p>
                      )}
                    </TableCell>
                    <TableCell>
                      <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{entity.code}</code>
                    </TableCell>
                    <TableCell>
                      {formatAddress(entity) ? (
                        <span className="text-sm">{formatAddress(entity)}</span>
                      ) : (
                        <span className="text-muted-foreground">&mdash;</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{entity.currency}</Badge>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm">{entity.timezone}</span>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1 text-sm">
                        <Users className="h-3.5 w-3.5 text-muted-foreground" />
                        {count}
                      </div>
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => navigate(`/admin/billing-entities/${entity.code}/edit`)}>
                            <Pencil className="mr-2 h-4 w-4" />
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            variant="destructive"
                            onClick={() => setDeleteEntity(entity)}
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
        <TablePagination
          page={page}
          pageSize={pageSize}
          totalCount={totalCount}
          onPageChange={setPage}
          onPageSizeChange={(size) => { setPageSize(size); setPage(1) }}
        />
      </div>

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
