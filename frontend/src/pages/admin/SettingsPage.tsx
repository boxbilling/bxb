import { Settings, Key, Bell, Users, Database, Shield } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Separator } from '@/components/ui/separator'

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Settings</h2>
        <p className="text-muted-foreground">
          Configure your billing platform
        </p>
      </div>

      <div className="grid gap-6">
        {/* API Keys */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Key className="h-5 w-5" />
              <CardTitle>API Keys</CardTitle>
            </div>
            <CardDescription>
              Manage API keys for accessing the billing API
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div>
                <p className="font-medium">Production Key</p>
                <code className="text-sm text-muted-foreground">
                  sk_live_••••••••••••••••
                </code>
              </div>
              <Button variant="outline" size="sm">
                Regenerate
              </Button>
            </div>
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div>
                <p className="font-medium">Test Key</p>
                <code className="text-sm text-muted-foreground">
                  sk_test_••••••••••••••••
                </code>
              </div>
              <Button variant="outline" size="sm">
                Regenerate
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Webhooks */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Bell className="h-5 w-5" />
              <CardTitle>Webhooks</CardTitle>
            </div>
            <CardDescription>
              Configure webhook endpoints for billing events
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="webhook-url">Webhook URL</Label>
              <Input
                id="webhook-url"
                placeholder="https://your-app.com/webhooks/billing"
              />
            </div>
            <div className="space-y-3">
              <Label>Events to send</Label>
              <div className="space-y-2">
                {[
                  'customer.created',
                  'subscription.created',
                  'subscription.terminated',
                  'invoice.finalized',
                  'invoice.paid',
                ].map((event) => (
                  <div key={event} className="flex items-center justify-between">
                    <Label htmlFor={event} className="font-normal">
                      {event}
                    </Label>
                    <Switch id={event} defaultChecked />
                  </div>
                ))}
              </div>
            </div>
            <Button>Save Webhook Settings</Button>
          </CardContent>
        </Card>

        {/* Payment Provider */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              <CardTitle>Payment Provider</CardTitle>
            </div>
            <CardDescription>
              Configure Stripe integration for payment processing
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="stripe-key">Stripe Secret Key</Label>
              <Input
                id="stripe-key"
                type="password"
                placeholder="sk_live_..."
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="stripe-webhook">Stripe Webhook Secret</Label>
              <Input
                id="stripe-webhook"
                type="password"
                placeholder="whsec_..."
              />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Auto-charge invoices</p>
                <p className="text-sm text-muted-foreground">
                  Automatically charge customers when invoices are finalized
                </p>
              </div>
              <Switch defaultChecked />
            </div>
            <Button>Save Payment Settings</Button>
          </CardContent>
        </Card>

        {/* Organization */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              <CardTitle>Organization</CardTitle>
            </div>
            <CardDescription>
              General organization settings
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="org-name">Organization Name</Label>
                <Input id="org-name" defaultValue="Acme Inc" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="currency">Default Currency</Label>
                <Input id="currency" defaultValue="USD" />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="timezone">Timezone</Label>
              <Input id="timezone" defaultValue="America/New_York" />
            </div>
            <Button>Save Organization Settings</Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
