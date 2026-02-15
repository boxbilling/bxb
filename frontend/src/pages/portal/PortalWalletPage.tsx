import { useQuery } from '@tanstack/react-query'
import { Wallet } from 'lucide-react'
import { format } from 'date-fns'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { portalApi } from '@/lib/api'
import { formatCents } from '@/lib/utils'
import { usePortalToken } from '@/layouts/PortalLayout'

export default function PortalWalletPage() {
  const token = usePortalToken()

  const { data: wallet, isLoading } = useQuery({
    queryKey: ['portal-wallet', token],
    queryFn: () => portalApi.getWallet(token),
    enabled: !!token,
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Wallet</h1>
        <p className="text-muted-foreground">Your wallet balance and details</p>
      </div>

      {isLoading ? (
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-24" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-10 w-32" />
          </CardContent>
        </Card>
      ) : !wallet ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Wallet className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">No wallet found</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Balance
              </CardTitle>
              <Wallet className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatCents(Number(wallet.balance_cents), wallet.currency)}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Credits Balance
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {wallet.credits_balance}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Consumed
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatCents(Number(wallet.consumed_amount_cents), wallet.currency)}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {wallet.consumed_credits} credits
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Status
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Badge variant={wallet.status === 'active' ? 'default' : 'secondary'}>
                {wallet.status}
              </Badge>
              {wallet.expiration_at ? (
                <p className="text-xs text-muted-foreground mt-2">
                  Expires {format(new Date(wallet.expiration_at), 'MMM d, yyyy')}
                </p>
              ) : (
                <p className="text-xs text-muted-foreground mt-2">
                  No expiration
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
