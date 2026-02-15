import { Routes, Route, Navigate } from 'react-router-dom'
import AdminLayout from './layouts/AdminLayout'
import PortalLayout from './layouts/PortalLayout'
import {
  DashboardPage,
  CustomersPage,
  CustomerDetailPage,
  MetricsPage,
  PlansPage,
  PlanDetailPage,
  SubscriptionsPage,
  SubscriptionDetailPage,
  EventsPage,
  InvoicesPage,
  InvoiceDetailPage,
  FeesPage,
  PaymentsPage,
  WalletsPage,
  CouponsPage,
  AddOnsPage,
  CreditNotesPage,
  CreditNoteFormPage,
  TaxesPage,
  DunningCampaignsPage,
  IntegrationsPage,
  PaymentRequestsPage,
  DataExportsPage,
  WebhooksPage,
  PaymentMethodsPage,
  AuditLogsPage,
  BillingEntitiesPage,
  BillingEntityFormPage,
  FeaturesPage,
  UsageAlertsPage,
} from './pages/admin'
import {
  PortalDashboardPage,
  PortalInvoicesPage,
  PortalUsagePage,
  PortalPaymentsPage,
  PortalWalletPage,
} from './pages/portal'
import SettingsPage from './pages/admin/SettingsPage'
import ApiKeysPage from './pages/admin/ApiKeysPage'

function App() {
  return (
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
        <Route path="subscriptions/:id" element={<SubscriptionDetailPage />} />
        <Route path="events" element={<EventsPage />} />
        <Route path="invoices" element={<InvoicesPage />} />
        <Route path="invoices/:id" element={<InvoiceDetailPage />} />
        <Route path="fees" element={<FeesPage />} />
        <Route path="payments" element={<PaymentsPage />} />
        <Route path="wallets" element={<WalletsPage />} />
        <Route path="coupons" element={<CouponsPage />} />
        <Route path="add-ons" element={<AddOnsPage />} />
        <Route path="credit-notes" element={<CreditNotesPage />} />
        <Route path="credit-notes/new" element={<CreditNoteFormPage />} />
        <Route path="credit-notes/:id/edit" element={<CreditNoteFormPage />} />
        <Route path="taxes" element={<TaxesPage />} />
        <Route path="dunning-campaigns" element={<DunningCampaignsPage />} />
        <Route path="integrations" element={<IntegrationsPage />} />
        <Route path="payment-requests" element={<PaymentRequestsPage />} />
        <Route path="data-exports" element={<DataExportsPage />} />
        <Route path="payment-methods" element={<PaymentMethodsPage />} />
        <Route path="webhooks" element={<WebhooksPage />} />
        <Route path="billing-entities" element={<BillingEntitiesPage />} />
        <Route path="billing-entities/new" element={<BillingEntityFormPage />} />
        <Route path="billing-entities/:code/edit" element={<BillingEntityFormPage />} />
        <Route path="features" element={<FeaturesPage />} />
        <Route path="usage-alerts" element={<UsageAlertsPage />} />
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
      </Route>

      {/* Redirect root to admin */}
      <Route path="/" element={<Navigate to="/admin" replace />} />

      {/* Catch all - redirect to admin */}
      <Route path="*" element={<Navigate to="/admin" replace />} />
    </Routes>
  )
}

export default App
