import { Routes, Route, Navigate } from 'react-router-dom'
import AdminLayout from './layouts/AdminLayout'
import {
  DashboardPage,
  CustomersPage,
  CustomerDetailPage,
  MetricsPage,
  PlansPage,
  SubscriptionsPage,
  SubscriptionDetailPage,
  EventsPage,
  InvoicesPage,
  FeesPage,
  PaymentsPage,
  WalletsPage,
  CouponsPage,
  AddOnsPage,
  CreditNotesPage,
  TaxesPage,
  DunningCampaignsPage,
  IntegrationsPage,
  PaymentRequestsPage,
  DataExportsPage,
  WebhooksPage,
} from './pages/admin'
import SettingsPage from './pages/admin/SettingsPage'

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
        <Route path="subscriptions" element={<SubscriptionsPage />} />
        <Route path="subscriptions/:id" element={<SubscriptionDetailPage />} />
        <Route path="events" element={<EventsPage />} />
        <Route path="invoices" element={<InvoicesPage />} />
        <Route path="fees" element={<FeesPage />} />
        <Route path="payments" element={<PaymentsPage />} />
        <Route path="wallets" element={<WalletsPage />} />
        <Route path="coupons" element={<CouponsPage />} />
        <Route path="add-ons" element={<AddOnsPage />} />
        <Route path="credit-notes" element={<CreditNotesPage />} />
        <Route path="taxes" element={<TaxesPage />} />
        <Route path="dunning-campaigns" element={<DunningCampaignsPage />} />
        <Route path="integrations" element={<IntegrationsPage />} />
        <Route path="payment-requests" element={<PaymentRequestsPage />} />
        <Route path="data-exports" element={<DataExportsPage />} />
        <Route path="webhooks" element={<WebhooksPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>

      {/* Redirect root to admin */}
      <Route path="/" element={<Navigate to="/admin" replace />} />
      
      {/* Catch all - redirect to admin */}
      <Route path="*" element={<Navigate to="/admin" replace />} />
    </Routes>
  )
}

export default App
