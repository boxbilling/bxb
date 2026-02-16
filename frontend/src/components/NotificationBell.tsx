import { Bell, Check, CheckCheck, AlertTriangle, Webhook, Wallet, FileText, CreditCard, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { notificationsApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'

const CATEGORY_CONFIG: Record<string, { icon: typeof Bell; color: string; label: string }> = {
  webhook: { icon: Webhook, color: 'text-red-500', label: 'Webhook' },
  dunning: { icon: AlertTriangle, color: 'text-orange-500', label: 'Dunning' },
  wallet: { icon: Wallet, color: 'text-yellow-500', label: 'Wallet' },
  invoice: { icon: FileText, color: 'text-blue-500', label: 'Invoice' },
  payment: { icon: CreditCard, color: 'text-red-500', label: 'Payment' },
  subscription: { icon: RefreshCw, color: 'text-purple-500', label: 'Subscription' },
}

const RESOURCE_ROUTES: Record<string, string> = {
  webhook: '/admin/webhooks',
  payment_request: '/admin/payment-requests',
  wallet: '/admin/wallets',
  invoice: '/admin/invoices',
  payment: '/admin/payments',
  subscription: '/admin/subscriptions',
}

function timeAgo(dateStr: string): string {
  const now = new Date()
  const date = new Date(dateStr)
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000)

  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: countData } = useQuery({
    queryKey: ['notifications', 'unread-count'],
    queryFn: notificationsApi.unreadCount,
    refetchInterval: 30000,
  })

  const { data: notifications } = useQuery({
    queryKey: ['notifications', 'list'],
    queryFn: () => notificationsApi.list({ limit: 20, order_by: '-created_at' }),
    enabled: open,
  })

  const markReadMutation = useMutation({
    mutationFn: notificationsApi.markAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })

  const markAllReadMutation = useMutation({
    mutationFn: notificationsApi.markAllAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })

  const unreadCount = countData?.unread_count ?? 0

  const handleNotificationClick = (notification: NonNullable<typeof notifications>[number]) => {
    if (!notification.is_read) {
      markReadMutation.mutate(notification.id)
    }
    if (notification.resource_type && notification.resource_id) {
      const baseRoute = RESOURCE_ROUTES[notification.resource_type]
      if (baseRoute) {
        setOpen(false)
        navigate(`${baseRoute}/${notification.resource_id}`)
      }
    }
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="icon" className="relative h-8 w-8">
          <Bell className="h-4 w-4" />
          {unreadCount > 0 && (
            <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-medium text-destructive-foreground">
              {unreadCount > 99 ? '99+' : unreadCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-96 p-0" align="end">
        <div className="flex items-center justify-between px-4 py-3">
          <h4 className="text-sm font-semibold">Notifications</h4>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs"
              onClick={() => markAllReadMutation.mutate()}
              disabled={markAllReadMutation.isPending}
            >
              <CheckCheck className="mr-1 h-3 w-3" />
              Mark all read
            </Button>
          )}
        </div>
        <Separator />
        <ScrollArea className="max-h-[400px]">
          {notifications && notifications.length > 0 ? (
            <div className="divide-y">
              {notifications.map((notification) => {
                const config = CATEGORY_CONFIG[notification.category] ?? {
                  icon: Bell,
                  color: 'text-muted-foreground',
                  label: notification.category,
                }
                const Icon = config.icon
                return (
                  <button
                    key={notification.id}
                    className={`flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/50 ${
                      !notification.is_read ? 'bg-muted/30' : ''
                    }`}
                    onClick={() => handleNotificationClick(notification)}
                  >
                    <div className={`mt-0.5 shrink-0 ${config.color}`}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm ${!notification.is_read ? 'font-semibold' : 'font-medium'}`}>
                          {notification.title}
                        </span>
                        {!notification.is_read && (
                          <span className="h-2 w-2 shrink-0 rounded-full bg-primary" />
                        )}
                      </div>
                      <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
                        {notification.message}
                      </p>
                      <div className="mt-1 flex items-center gap-2">
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                          {config.label}
                        </Badge>
                        <span className="text-[10px] text-muted-foreground">
                          {timeAgo(notification.created_at)}
                        </span>
                      </div>
                    </div>
                    {!notification.is_read && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 shrink-0"
                        onClick={(e) => {
                          e.stopPropagation()
                          markReadMutation.mutate(notification.id)
                        }}
                      >
                        <Check className="h-3 w-3" />
                      </Button>
                    )}
                  </button>
                )
              })}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
              <Bell className="mb-2 h-8 w-8" />
              <p className="text-sm">No notifications</p>
            </div>
          )}
        </ScrollArea>
      </PopoverContent>
    </Popover>
  )
}
