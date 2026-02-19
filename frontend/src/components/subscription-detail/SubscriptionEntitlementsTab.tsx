import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ToggleLeft } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
import { subscriptionsApi, featuresApi } from '@/lib/api'

interface SubscriptionEntitlementsTabProps {
  subscriptionExternalId: string
}

export function SubscriptionEntitlementsTab({
  subscriptionExternalId,
}: SubscriptionEntitlementsTabProps) {
  const { data: entitlements, isLoading: entitlementsLoading } = useQuery({
    queryKey: ['subscription-entitlements', subscriptionExternalId],
    queryFn: () => subscriptionsApi.getEntitlements(subscriptionExternalId),
    enabled: !!subscriptionExternalId,
  })

  const { data: features } = useQuery({
    queryKey: ['features'],
    queryFn: () => featuresApi.list(),
    enabled: !!entitlements && entitlements.length > 0,
  })

  const featureMap = new Map(features?.map((f) => [f.id, f]) ?? [])

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <ToggleLeft className="h-4 w-4" />
            Entitlements
          </CardTitle>
          <Link
            to="/admin/features"
            className="text-sm text-primary hover:underline"
          >
            Manage Features
          </Link>
        </div>
      </CardHeader>
      <CardContent>
        {entitlementsLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : !entitlements?.length ? (
          <p className="text-sm text-muted-foreground">No features configured for this plan.</p>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Feature</TableHead>
                  <TableHead className="hidden md:table-cell">Code</TableHead>
                  <TableHead className="hidden md:table-cell">Type</TableHead>
                  <TableHead>Value</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entitlements.map((entitlement) => {
                  const feature = featureMap.get(entitlement.feature_id)
                  return (
                    <TableRow key={entitlement.id}>
                      <TableCell className="font-medium">{feature?.name ?? 'Unknown'}</TableCell>
                      <TableCell className="hidden md:table-cell">
                        <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                          {feature?.code ?? entitlement.feature_id}
                        </code>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {feature ? (
                          <Badge variant={feature.feature_type === 'boolean' ? 'default' : feature.feature_type === 'quantity' ? 'secondary' : 'outline'}>
                            {feature.feature_type}
                          </Badge>
                        ) : (
                          '\u2014'
                        )}
                      </TableCell>
                      <TableCell>
                        {feature?.feature_type === 'boolean'
                          ? entitlement.value === 'true' ? 'Enabled' : 'Disabled'
                          : entitlement.value}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
