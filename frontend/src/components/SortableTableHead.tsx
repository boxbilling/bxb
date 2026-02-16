import { useState } from 'react'
import { ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react'
import { TableHead } from '@/components/ui/table'
import { cn } from '@/lib/utils'

export interface SortState {
  field: string | null
  direction: 'asc' | 'desc'
}

interface SortableTableHeadProps {
  label: string
  sortKey: string
  sort: SortState
  onSort: (field: string) => void
  className?: string
}

export function SortableTableHead({
  label,
  sortKey,
  sort,
  onSort,
  className,
}: SortableTableHeadProps) {
  const isActive = sort.field === sortKey

  return (
    <TableHead
      className={cn('cursor-pointer select-none hover:bg-muted/50', className)}
      onClick={() => onSort(sortKey)}
    >
      <div className="flex items-center gap-1">
        {label}
        {isActive ? (
          sort.direction === 'asc' ? (
            <ArrowUp className="h-3.5 w-3.5" />
          ) : (
            <ArrowDown className="h-3.5 w-3.5" />
          )
        ) : (
          <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground/50" />
        )}
      </div>
    </TableHead>
  )
}

export function useSortState(defaultField?: string, defaultDirection: 'asc' | 'desc' = 'desc'): {
  sort: SortState
  setSort: (field: string) => void
  orderBy: string | undefined
} {
  const [sort, setSortState] = useState<SortState>({
    field: defaultField ?? null,
    direction: defaultDirection,
  })

  const setSort = (field: string) => {
    setSortState((prev) => {
      if (prev.field === field) {
        return prev.direction === 'asc'
          ? { field, direction: 'desc' }
          : { field: null, direction: 'desc' }
      }
      return { field, direction: 'asc' }
    })
  }

  const orderBy = sort.field ? `${sort.field}:${sort.direction}` : undefined

  return { sort, setSort, orderBy }
}
