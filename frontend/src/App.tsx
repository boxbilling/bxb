import { Routes, Route, Navigate } from 'react-router-dom'
import AdminLayout from './layouts/AdminLayout'
import {
  DashboardPage,
  CustomersPage,
  MetricsPage,
  PlansPage,
  SubscriptionsPage,
  InvoicesPage,
} from './pages/admin'
import SettingsPage from './pages/admin/SettingsPage'

function App() {
  return (
    <Routes>
      {/* Admin Dashboard */}
      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="customers" element={<CustomersPage />} />
        <Route path="metrics" element={<MetricsPage />} />
        <Route path="plans" element={<PlansPage />} />
        <Route path="subscriptions" element={<SubscriptionsPage />} />
        <Route path="invoices" element={<InvoicesPage />} />
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
