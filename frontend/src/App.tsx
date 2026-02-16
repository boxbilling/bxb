import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import AdminLayout from './layouts/AdminLayout'
import PortalLayout from './layouts/PortalLayout'
import { Spinner } from './components/ui/spinner'

// Admin pages - lazy loaded
const DashboardPage = lazy(() => import('./pages/admin/DashboardPage'))
const CustomersPage = lazy(() => import('./pages/admin/CustomersPage'))
const CustomerDetailPage = lazy(() => import('./pages/admin/CustomerDetailPage'))
const MetricsPage = lazy(() => import('./pages/admin/MetricsPage'))
const PlansPage = lazy(() => import('./pages/admin/PlansPage'))
const PlanDetailPage = lazy(() => import('./pages/admin/PlanDetailPage'))
const SubscriptionsPage = lazy(() => import('./pages/admin/SubscriptionsPage'))
const SubscriptionDetailPage = lazy(
  () => import('./pages/admin/SubscriptionDetailPage'),
)
const EventsPage = lazy(() => import('./pages/admin/EventsPage'))
const InvoicesPage = lazy(() => import('./pages/admin/InvoicesPage'))
const InvoiceDetailPage = lazy(() => import('./pages/admin/InvoiceDetailPage'))
const FeesPage = lazy(() => import('./pages/admin/FeesPage'))
const PaymentsPage = lazy(() => import('./pages/admin/PaymentsPage'))
const WalletsPage = lazy(() => import('./pages/admin/WalletsPage'))
const WalletDetailPage = lazy(() => import('./pages/admin/WalletDetailPage'))
const CouponsPage = lazy(() => import('./pages/admin/CouponsPage'))
const AddOnsPage = lazy(() => import('./pages/admin/AddOnsPage'))
const CreditNotesPage = lazy(() => import('./pages/admin/CreditNotesPage'))
const CreditNoteFormPage = lazy(
  () => import('./pages/admin/CreditNoteFormPage'),
)
const TaxesPage = lazy(() => import('./pages/admin/TaxesPage'))
const DunningCampaignsPage = lazy(
  () => import('./pages/admin/DunningCampaignsPage'),
)
const DunningCampaignDetailPage = lazy(
  () => import('./pages/admin/DunningCampaignDetailPage'),
)
const IntegrationsPage = lazy(() => import('./pages/admin/IntegrationsPage'))
const IntegrationDetailPage = lazy(
  () => import('./pages/admin/IntegrationDetailPage'),
)
const PaymentRequestsPage = lazy(
  () => import('./pages/admin/PaymentRequestsPage'),
)
const DataExportsPage = lazy(() => import('./pages/admin/DataExportsPage'))
const WebhooksPage = lazy(() => import('./pages/admin/WebhooksPage'))
const PaymentMethodsPage = lazy(
  () => import('./pages/admin/PaymentMethodsPage'),
)
const AuditLogsPage = lazy(() => import('./pages/admin/AuditLogsPage'))
const BillingEntitiesPage = lazy(
  () => import('./pages/admin/BillingEntitiesPage'),
)
const BillingEntityFormPage = lazy(
  () => import('./pages/admin/BillingEntityFormPage'),
)
const FeaturesPage = lazy(() => import('./pages/admin/FeaturesPage'))
const UsageAlertsPage = lazy(() => import('./pages/admin/UsageAlertsPage'))
const RevenueAnalyticsPage = lazy(
  () => import('./pages/admin/RevenueAnalyticsPage'),
)
const SettingsPage = lazy(() => import('./pages/admin/SettingsPage'))
const ApiKeysPage = lazy(() => import('./pages/admin/ApiKeysPage'))

// Portal pages - lazy loaded
const PortalDashboardPage = lazy(
  () => import('./pages/portal/PortalDashboardPage'),
)
const PortalInvoicesPage = lazy(
  () => import('./pages/portal/PortalInvoicesPage'),
)
const PortalUsagePage = lazy(() => import('./pages/portal/PortalUsagePage'))
const PortalPaymentsPage = lazy(
  () => import('./pages/portal/PortalPaymentsPage'),
)
const PortalWalletPage = lazy(() => import('./pages/portal/PortalWalletPage'))
const PortalProfilePage = lazy(
  () => import('./pages/portal/PortalProfilePage'),
)
const PortalPaymentMethodsPage = lazy(
  () => import('./pages/portal/PortalPaymentMethodsPage'),
)
const PortalSubscriptionsPage = lazy(
  () => import('./pages/portal/PortalSubscriptionsPage'),
)
const PortalAddOnsPage = lazy(() => import('./pages/portal/PortalAddOnsPage'))
const PortalCouponsPage = lazy(
  () => import('./pages/portal/PortalCouponsPage'),
)

function PageFallback() {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <Spinner className="size-6" />
    </div>
  )
}

function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        {/* Admin Dashboard */}
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="customers" element={<CustomersPage />} />
          <Route path="customers/:id" element={<CustomerDetailPage />} />
          <Route path="metrics" element={<MetricsPage />} />
          <Route path="plans" element={<PlansPage />} />
          <Route path="plans/:id" element={<PlanDetailPage />} />
          <Route path="subscriptions" element={<SubscriptionsPage />} />
          <Route
            path="subscriptions/:id"
            element={<SubscriptionDetailPage />}
          />
          <Route path="events" element={<EventsPage />} />
          <Route path="invoices" element={<InvoicesPage />} />
          <Route path="invoices/:id" element={<InvoiceDetailPage />} />
          <Route path="fees" element={<FeesPage />} />
          <Route path="payments" element={<PaymentsPage />} />
          <Route path="wallets" element={<WalletsPage />} />
          <Route path="wallets/:id" element={<WalletDetailPage />} />
          <Route path="coupons" element={<CouponsPage />} />
          <Route path="add-ons" element={<AddOnsPage />} />
          <Route path="credit-notes" element={<CreditNotesPage />} />
          <Route path="credit-notes/new" element={<CreditNoteFormPage />} />
          <Route
            path="credit-notes/:id/edit"
            element={<CreditNoteFormPage />}
          />
          <Route path="taxes" element={<TaxesPage />} />
          <Route path="dunning-campaigns" element={<DunningCampaignsPage />} />
          <Route
            path="dunning-campaigns/:id"
            element={<DunningCampaignDetailPage />}
          />
          <Route path="integrations" element={<IntegrationsPage />} />
          <Route
            path="integrations/:id"
            element={<IntegrationDetailPage />}
          />
          <Route path="payment-requests" element={<PaymentRequestsPage />} />
          <Route path="data-exports" element={<DataExportsPage />} />
          <Route path="payment-methods" element={<PaymentMethodsPage />} />
          <Route path="webhooks" element={<WebhooksPage />} />
          <Route path="billing-entities" element={<BillingEntitiesPage />} />
          <Route
            path="billing-entities/new"
            element={<BillingEntityFormPage />}
          />
          <Route
            path="billing-entities/:code/edit"
            element={<BillingEntityFormPage />}
          />
          <Route path="features" element={<FeaturesPage />} />
          <Route path="usage-alerts" element={<UsageAlertsPage />} />
          <Route path="revenue-analytics" element={<RevenueAnalyticsPage />} />
          <Route path="audit-logs" element={<AuditLogsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="api-keys" element={<ApiKeysPage />} />
        </Route>

        {/* Customer Portal */}
        <Route path="/portal" element={<PortalLayout />}>
          <Route index element={<PortalDashboardPage />} />
          <Route path="invoices" element={<PortalInvoicesPage />} />
          <Route path="usage" element={<PortalUsagePage />} />
          <Route path="payments" element={<PortalPaymentsPage />} />
          <Route path="wallet" element={<PortalWalletPage />} />
          <Route path="subscriptions" element={<PortalSubscriptionsPage />} />
          <Route
            path="payment-methods"
            element={<PortalPaymentMethodsPage />}
          />
          <Route path="add-ons" element={<PortalAddOnsPage />} />
          <Route path="coupons" element={<PortalCouponsPage />} />
          <Route path="profile" element={<PortalProfilePage />} />
        </Route>

        {/* Redirect root to admin */}
        <Route path="/" element={<Navigate to="/admin" replace />} />

        {/* Catch all - redirect to admin */}
        <Route path="*" element={<Navigate to="/admin" replace />} />
      </Routes>
    </Suspense>
  )
}

export default App
