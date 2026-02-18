import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'

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
import { walletsApi } from '@/lib/api'
import { formatCents } from '@/lib/utils'

export function CustomerWalletsTable({ customerId }: { customerId: string }) {
  const { data: wallets, isLoading } = useQuery({
    queryKey: ['customer-wallets', customerId],
    queryFn: () => walletsApi.list({ customer_id: customerId }),
  })

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (!wallets?.length) {
    return <p className="text-sm text-muted-foreground py-4">No wallets found</p>
  }

  const statusVariant: Record<string, 'default' | 'destructive'> = {
    active: 'default',
    terminated: 'destructive',
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Balance</TableHead>
            <TableHead>Credits Balance</TableHead>
            <TableHead>Expiration</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {wallets.map((wallet) => (
            <TableRow key={wallet.id}>
              <TableCell>
                <div>{wallet.name ?? '\u2014'}</div>
                {wallet.code && <div className="text-xs text-muted-foreground">{wallet.code}</div>}
              </TableCell>
              <TableCell>
                <Badge variant={statusVariant[wallet.status] ?? 'outline'}>{wallet.status}</Badge>
              </TableCell>
              <TableCell className="font-mono">{formatCents(Number(wallet.balance_cents), wallet.currency)}</TableCell>
              <TableCell>{wallet.credits_balance}</TableCell>
              <TableCell>{wallet.expiration_at ? format(new Date(wallet.expiration_at), 'MMM d, yyyy') : 'Never'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
