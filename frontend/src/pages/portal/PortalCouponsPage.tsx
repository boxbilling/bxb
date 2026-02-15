import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Tag, Ticket, Percent, DollarSign, Loader2, Check, Clock } from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { portalApi, ApiError } from '@/lib/api'
import { usePortalToken } from '@/layouts/PortalLayout'
import type { PortalAppliedCoupon } from '@/types/billing'

function formatDiscount(coupon: PortalAppliedCoupon): string {
  if (coupon.coupon_type === 'percentage' && coupon.percentage_rate) {
    return `${Number(coupon.percentage_rate)}% off`
  }
  if (coupon.amount_cents != null && coupon.amount_currency) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: coupon.amount_currency,
    }).format(Number(coupon.amount_cents) / 100) + ' off'
  }
  return 'Discount'
}

function formatFrequency(coupon: PortalAppliedCoupon): string {
  if (coupon.frequency === 'once') return 'One-time'
  if (coupon.frequency === 'forever') return 'Every billing period'
  if (coupon.frequency === 'recurring') {
    const remaining = coupon.frequency_duration_remaining
    if (remaining != null) {
      return `${remaining} use${remaining === 1 ? '' : 's'} remaining`
    }
    return 'Recurring'
  }
  return coupon.frequency
}

export default function PortalCouponsPage() {
  const token = usePortalToken()
  const queryClient = useQueryClient()
  const [couponCode, setCouponCode] = useState('')

  const { data: coupons, isLoading } = useQuery({
    queryKey: ['portal-coupons', token],
    queryFn: () => portalApi.listCoupons(token),
    enabled: !!token,
  })

  const redeemMutation = useMutation({
    mutationFn: (code: string) => portalApi.redeemCoupon(token, code),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['portal-coupons', token] })
      toast.success(`Coupon "${data.coupon_name}" applied successfully!`)
      setCouponCode('')
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : 'Failed to redeem coupon'
      toast.error(msg)
    },
  })

  const handleRedeem = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = couponCode.trim()
    if (!trimmed) return
    redeemMutation.mutate(trimmed)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Coupons</h1>
        <p className="text-muted-foreground">
          Redeem coupon codes and view your active discounts
        </p>
      </div>

      {/* Redeem coupon form */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Ticket className="h-5 w-5" />
            Redeem a Coupon
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleRedeem} className="flex gap-3">
            <Input
              placeholder="Enter coupon code"
              value={couponCode}
              onChange={(e) => setCouponCode(e.target.value)}
              disabled={redeemMutation.isPending}
              className="max-w-sm"
            />
            <Button
              type="submit"
              disabled={!couponCode.trim() || redeemMutation.isPending}
            >
              {redeemMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Applying...
                </>
              ) : (
                'Apply Coupon'
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Active coupons list */}
      <div>
        <h2 className="text-lg font-semibold mb-3">
          Active Coupons{coupons?.length ? ` (${coupons.length})` : ''}
        </h2>
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <Skeleton key={i} className="h-20" />
            ))}
          </div>
        ) : !coupons?.length ? (
          <Card>
            <CardContent className="py-12 text-center">
              <Tag className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-muted-foreground">
                No active coupons. Enter a coupon code above to apply a discount.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {coupons.map((coupon) => (
              <CouponCard key={coupon.id} coupon={coupon} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function CouponCard({ coupon }: { coupon: PortalAppliedCoupon }) {
  const isPercentage = coupon.coupon_type === 'percentage'

  return (
    <Card>
      <CardContent className="flex items-center justify-between py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
            {isPercentage ? (
              <Percent className="h-5 w-5 text-primary" />
            ) : (
              <DollarSign className="h-5 w-5 text-primary" />
            )}
          </div>
          <div>
            <div className="font-medium">{coupon.coupon_name}</div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="outline" className="text-xs">
                {coupon.coupon_code}
              </Badge>
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {formatFrequency(coupon)}
              </span>
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-lg font-semibold text-primary">
            {formatDiscount(coupon)}
          </div>
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Check className="h-3 w-3" />
            Applied {format(new Date(coupon.created_at), 'MMM d, yyyy')}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
