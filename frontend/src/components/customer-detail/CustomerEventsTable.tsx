import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Search } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { TablePagination } from '@/components/TablePagination'
import { eventsApi } from '@/lib/api'

export function CustomerEventsTable({ externalId }: { externalId: string }) {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)
  const [codeFilter, setCodeFilter] = useState('')
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())

  const { data, isLoading } = useQuery({
    queryKey: ['customer-events', externalId, page, pageSize, codeFilter],
    queryFn: () =>
      eventsApi.listPaginated({
        external_customer_id: externalId,
        limit: pageSize,
        skip: (page - 1) * pageSize,
        ...(codeFilter ? { code: codeFilter } : {}),
      }),
  })

  const events = data?.data ?? []
  const totalCount = data?.totalCount ?? 0

  const toggleRow = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Filter by event code..."
          value={codeFilter}
          onChange={(e) => {
            setCodeFilter(e.target.value)
            setPage(1)
          }}
          className="pl-9 h-9"
        />
      </div>

      {!events.length ? (
        <p className="text-sm text-muted-foreground py-4">No events found</p>
      ) : (
        <>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Transaction ID</TableHead>
                  <TableHead>Event Code</TableHead>
                  <TableHead>Timestamp</TableHead>
                  <TableHead>Properties</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((event) => (
                  <>
                    <TableRow key={event.id}>
                      <TableCell>
                        <code
                          className="text-xs bg-muted px-1.5 py-0.5 rounded"
                          title={event.transaction_id}
                        >
                          {event.transaction_id.substring(0, 12)}...
                        </code>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{event.code}</Badge>
                      </TableCell>
                      <TableCell>
                        {format(new Date(event.timestamp), 'MMM d, yyyy HH:mm:ss')}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => toggleRow(event.id)}
                        >
                          {expandedRows.has(event.id) ? 'Hide' : 'View'}
                        </Button>
                      </TableCell>
                    </TableRow>
                    {expandedRows.has(event.id) && (
                      <TableRow key={`${event.id}-props`}>
                        <TableCell colSpan={4} className="bg-muted/30">
                          <pre className="text-xs font-mono whitespace-pre-wrap overflow-auto max-h-48 p-2">
                            {JSON.stringify(event.properties, null, 2)}
                          </pre>
                        </TableCell>
                      </TableRow>
                    )}
                  </>
                ))}
              </TableBody>
            </Table>
          </div>
          <TablePagination
            page={page}
            pageSize={pageSize}
            totalCount={totalCount}
            onPageChange={setPage}
            onPageSizeChange={setPageSize}
            pageSizeOptions={[25, 50, 100]}
          />
        </>
      )}
    </div>
  )
}
