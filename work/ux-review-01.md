# BXB Frontend UX Review & Redesign Recommendations

## Executive Summary

BXB is a sophisticated usage-based billing platform with 32 admin screens and 5 customer portal screens. The current UI is functional but has significant UX gaps: several screens lack edit capabilities, modal vs. page decisions are inconsistent, and the overall experience can be elevated from "functional admin panel" to "beautiful, intuitive billing platform." This review covers every screen with specific, actionable recommendations.

---

## Table of Contents

1. [Global Design System Issues](#1-global-design-system-issues)
2. [Navigation & Information Architecture](#2-navigation--information-architecture)
3. [Screen-by-Screen Analysis](#3-screen-by-screen-analysis)
4. [Modal vs. Page Decision Framework](#4-modal-vs-page-decision-framework)
5. [Broken Edit Modes & Missing CRUD](#5-broken-edit-modes--missing-crud)
6. [Customer Portal Redesign](#6-customer-portal-redesign)
7. [Implementation Priority](#7-implementation-priority)

---

## 1. Global Design System Issues

### 1.1 Empty Header Bar
The admin layout header (`AdminLayout.tsx:296-298`) is nearly empty - it only holds a mobile hamburger menu. This wastes 56px of prime vertical real estate on every screen.

**Recommendation:** Populate the header with:
- Breadcrumb trail (current location context)
- Global search (Cmd+K command palette)
- Notification bell (webhook failures, dunning alerts, expiring wallets)
- User/org avatar with quick-switch dropdown
- Move dark mode toggle here (currently buried in Settings dropdown)

### 1.2 Inconsistent Page Headers
Some pages have stat cards at top (Customers, Wallets, Taxes), some have nothing (Metrics, Plans), some have unique layouts (Dashboard). There's no consistent page header pattern.

**Recommendation:** Standardize every page with:
```
[Breadcrumb]
[Page Title + Description] .............. [Primary Action Button]
[Optional: Stat Cards Row]
[Filters Row]
[Content Area]
```

### 1.3 No Pagination
Most table pages fetch all records with no pagination. This will break with scale.

**Recommendation:** Add cursor-based pagination to all table views. The backend already supports `page` and `per_page` parameters.

### 1.4 No Table Sorting
No column headers are clickable for sorting. Users cannot reorder data.

**Recommendation:** Add sort indicators on all table column headers. Backend supports `order` parameter on most endpoints.

### 1.5 No Bulk Actions
Cannot select multiple rows for batch operations (e.g., finalize 10 draft invoices, terminate multiple subscriptions).

**Recommendation:** Add row checkboxes with a floating action bar for bulk operations on key pages: Invoices, Subscriptions, Payments.

### 1.6 Toast-Only Feedback
All operations show only a toast notification. No inline success/error states.

**Recommendation:** Use inline feedback for form validation errors (not just toast). Keep toast for async operations.

---

## 2. Navigation & Information Architecture

### 2.1 Current Sidebar (30 items across 5 groups)
The sidebar has too many items. Users face choice overload. "Operations" alone has 7 items.

**Recommendation:** Restructure into fewer, clearer groups:

```
── Overview
   Dashboard

── Customers
   Customers
   Subscriptions
   Wallets
   Payment Methods

── Catalog
   Plans
   Billable Metrics
   Features & Entitlements
   Add-ons
   Coupons

── Billing
   Invoices
   Payments
   Fees
   Credit Notes
   Taxes

── Operations
   Events
   Webhooks
   Dunning
   Usage Alerts
   Integrations

── Settings (bottom)
   Organization
   Billing Entities
   API Keys
   Data Exports
   Audit Logs
```

Key changes:
- Move **Billing Entities** to Settings (it's configuration, not daily workflow)
- Move **Payment Requests** into the Payments detail page (it's a sub-concern)
- Group **Payment Methods** with Customers (they belong to customers)
- Combine **Features** with entitlements (they're inseparable)
- Move **Data Exports** and **Audit Logs** to Settings (admin/compliance tools)

### 2.2 Sidebar Collapsed State
When collapsed, navigation groups become separator lines with no visual distinction. Icons alone don't convey meaning for 30 items.

**Recommendation:** Show group icons or mini-labels in collapsed mode. Consider a two-level sidebar: icon rail + expandable flyout.

### 2.3 Missing Global Search
No way to quickly jump to a customer, invoice, or subscription by ID/name.

**Recommendation:** Add Cmd+K command palette with:
- Search customers by name/email/external_id
- Search invoices by number
- Search subscriptions by external_id
- Navigate to any page
- Quick actions (create customer, preview invoice)

---

## 3. Screen-by-Screen Analysis

### 3.1 Dashboard (`DashboardPage.tsx`)

**Current State:** Shows MRR, outstanding invoices, overdue amounts, customer/subscription metrics, revenue chart, subscriptions by plan chart, top metrics chart, and activity feed.

**Issues:**
- Charts use basic recharts with minimal customization
- Activity feed has no filtering or "view all" link
- No date range selector for any metric
- Stat cards are static (no trend indicators)
- No quick actions from dashboard

**Recommendations:**
- [x] Add date range picker (7d/30d/90d/12m/custom) affecting all dashboard data
  <!-- Completed: Added PeriodSelector component with 5 presets (7d/30d/90d/12m/custom). Backend endpoints now accept start_date/end_date query params. All dashboard queries (stats, revenue, customers, subscriptions, usage) are wired through the date range. Custom mode uses a dual-month Calendar popover for arbitrary date ranges. 18 new backend tests added, 100% coverage maintained. -->
- [x] Add trend indicators on stat cards (↑12% vs last period)
  <!-- Completed: Added TrendIndicator schema (previous_value + change_percent) to backend. Each period-aware endpoint (revenue, customers, subscriptions) now computes the previous equivalent period and returns trend data. Frontend StatCard component extended with TrendBadge showing directional arrow (TrendingUp/TrendingDown/Minus) and percentage. Color-coded: green for positive, red for negative, muted for neutral. invertTrendColor prop used for "bad" metrics (churned, canceled) where increases are shown in red. 18 new backend tests added, 100% coverage maintained. -->
- [x] Make stat cards clickable (MRR → revenue detail, overdue → filtered invoices)
  <!-- Completed: Added href prop to StatCard component with Link-based navigation and hover styling (border highlight + cursor pointer). All 10 dashboard stat cards are now clickable: MRR → paid invoices, Outstanding → finalized invoices, Overdue → finalized invoices, Wallet Credits → wallets page, Customers/New/Churned → customers page, Active Subscriptions → subscriptions filtered by active, New Subscriptions → subscriptions page, Canceled → subscriptions filtered by canceled. Also added useSearchParams support to InvoicesPage and SubscriptionsPage so URL query params (e.g. ?status=finalized) initialize the filter state correctly. -->
- [x] Add "Recent Invoices" and "Recent Subscriptions" quick-glance tables
  <!-- Completed: Added two new backend endpoints (GET /dashboard/recent_invoices and GET /dashboard/recent_subscriptions) with joined customer/plan names. Repository methods use SQLAlchemy joins to return the 5 most recent items with associated entity names. Frontend dashboard now displays two side-by-side quick-glance tables between the charts row and bottom charts row. Each table includes status badges (color-coded by status), "View all" links to full list pages, and loading skeletons. Invoice table shows: invoice number, customer, status, amount. Subscription table shows: external ID, customer, plan, status. 8 new backend tests added, 100% coverage maintained. -->
- [x] Activity feed: add "View all" link to Audit Logs, add filters
  <!-- Completed: Added "View all" link in the activity feed card header pointing to /admin/audit-logs. Added activity type filter dropdown (All activity, Customers, Subscriptions, Invoices, Payments) to the card header. Backend GET /dashboard/activity endpoint now accepts optional `type` query parameter to filter by activity type (customer_created, subscription_created, invoice_finalized, payment_received). Invalid type values are ignored and return all activity. Frontend API client updated to pass filter params. 6 new backend tests added, 100% coverage maintained. -->
- [x] Add revenue breakdown by plan (pie/donut chart)
  <!-- Completed: Added GET /dashboard/revenue_by_plan backend endpoint that queries finalized/paid invoices joined through subscriptions to plans, grouping revenue by plan name with date range filtering. Frontend dashboard now displays a donut chart (recharts PieChart with inner radius) in the bottom charts row with a color-coded legend showing revenue per plan. 7 new backend tests added covering: empty DB, with data, multiple plans, draft exclusion, date range filtering, narrow range exclusion, and no-subscription exclusion. 100% coverage maintained. -->
- [x] Sparkline charts inside stat cards for mini-trends
  <!-- Completed: Added GET /dashboard/sparklines backend endpoint returning daily data points for revenue (from finalized/paid invoices), new customers, and new subscriptions, with date range filtering. Added 3 new repository methods (daily_revenue, daily_new_customers, daily_new_subscriptions) using day-level grouping with SQLite/PostgreSQL dialect support. Frontend StatCard component extended with optional sparklineData/sparklineColor props. Added Sparkline component using recharts AreaChart (32px height, no axes, gradient fill, no animation). Wired sparklines to MRR, New Customers, and New Subscriptions stat cards with distinct colors. 12 new backend tests added (9 API tests + 3 PostgreSQL dialect branch tests), 100% coverage maintained. -->

---

### 3.2 Customers (`CustomersPage.tsx` + `CustomerDetailPage.tsx`)

**Current State:**
- List: Table with search and currency filter. Click row → detail page.
- Create: Modal dialog
- Edit: Modal dialog (same as create, prefilled)
- Delete: Alert dialog
- Detail: Read-only card with tabs (Subscriptions, Invoices, Payments, Wallets, Coupons, Credit Notes, Taxes, Usage)

**Issues:**
- Detail page is entirely **read-only** - no edit button for customer info
- 8 tabs is overwhelming - too many tabs for one page
- No way to create a subscription directly from customer detail
- Portal link generation works but is buried
- Usage tab requires selecting a subscription first (confusing flow)
- Customer metadata is shown as raw JSON

**Recommendations:**
- [x] Add **Edit** button on CustomerDetailPage info card → opens same modal as list page edit
  <!-- Completed: Extracted CustomerFormDialog into a shared component at src/components/CustomerFormDialog.tsx. Added Edit button with Pencil icon to the Customer Information card header on CustomerDetailPage. Clicking it opens the same form dialog used on the list page, pre-filled with customer data. Update mutation invalidates the customer query on success and shows toast feedback. CustomersPage updated to import from the shared component. TypeScript compiles clean, all 3300 backend tests pass with 100% coverage. -->
- [x] Reduce tabs to 5: **Overview** (merge subscriptions + usage), **Billing** (invoices + fees + credit notes), **Payments** (payments + payment methods + wallets), **Coupons**, **Activity** (audit trail)
  <!-- Completed: Consolidated 8 tabs (Subscriptions, Invoices, Payments, Wallets, Coupons, Credit Notes, Taxes, Usage) into 5 tabs. Overview tab merges Subscriptions table + Usage section with subscription selector. Billing tab merges Invoices + new Fees table (using feesApi) + Credit Notes. Payments tab merges Payment Methods card (moved from standalone card outside tabs) + Payment History table + Wallets table. Coupons tab unchanged. Activity tab uses the existing AuditTrailTimeline component with showViewAll. Removed Taxes standalone tab (tax info accessible through Fees on FeesPage). Added CustomerFeesTab and CustomerActivityTab components. Removed unused imports (Calculator, BarChart3, Receipt, taxesApi, AppliedTax). TypeScript compiles clean, all 3300 backend tests pass with 100% coverage. -->
- [x] Add "Create Subscription" button in Overview tab
  <!-- Completed: Extracted SubscriptionFormDialog from SubscriptionsPage into a shared component at src/components/SubscriptionFormDialog.tsx with a new defaultCustomerId prop (pre-selects and disables the customer selector). Added "Create Subscription" button with Plus icon to the Subscriptions section header in the CustomerDetailPage Overview tab. Clicking opens the subscription form dialog with the current customer pre-selected. Create mutation invalidates customer-subscriptions query on success. SubscriptionsPage updated to import from the shared component, unused imports (Separator, Customer, BillingTime) cleaned up. TypeScript compiles clean, all 3300 backend tests pass with 100% coverage. -->
- [x] Move portal link generation to a prominent button in header area
  <!-- Completed: Elevated the Portal Link button from outline/sm to default (primary) variant in the page header, making it the most visually prominent action. Grouped it alongside the Edit button (moved from the Customer Information card header) in a flex action bar in the main header area. This makes both key actions (Edit customer + Generate portal link) immediately discoverable at the top of the page. TypeScript compiles clean, all 3300 backend tests pass with 100% coverage. -->
- [x] Display metadata as key-value pills instead of raw JSON
  <!-- Completed: Replaced raw JSON `<pre>` block in CustomerDetailPage with inline key-value pill badges. Each metadata entry now renders as a Badge (outline variant) showing `key: value` with the key in medium weight and the value in muted foreground color. Uses flex-wrap layout so pills flow naturally across the available width. TypeScript compiles clean, all 3300 backend tests pass with 100% coverage. -->
- [x] Add customer avatar/initials badge
  <!-- Completed: Created CustomerAvatar component (src/components/CustomerAvatar.tsx) using existing Radix Avatar primitives. Generates 1-2 character initials from customer name with deterministic color assignment (8 color palette hashed from name). Three size variants (sm/md/lg). Added large avatar to CustomerDetailPage header beside customer name. Added small avatar to CustomersPage table rows in the Customer column. TypeScript compiles clean, all 3300 backend tests pass with 100% coverage. -->
- [x] Show customer health indicator (green/yellow/red based on payment history)
  <!-- Completed: Added GET /v1/customers/{customer_id}/health backend endpoint that queries invoices and payments to compute a health status (good/warning/critical). Logic: critical if any overdue invoices or 2+ failed payments; warning if unpaid-but-not-overdue invoices or exactly 1 failed payment; good otherwise. Draft and voided invoices are excluded. Created CustomerHealthBadge frontend component with color-coded filled circle (green/yellow/red) and tooltip showing detailed breakdown (overdue invoices, failed payments, payment ratios). Integrated into CustomerDetailPage (next to customer name in header) and CustomersPage (in table row next to name). 9 new backend tests added covering: no billing history, all paid, unpaid not overdue, one failed payment, overdue invoices, multiple failed payments, draft/voided exclusion, 404, and mixed scenarios. 100% coverage maintained. -->

**Modal vs. Page Decision:**
- **List page → Detail page**: CORRECT (customers are complex entities with many relationships)
- **Create/Edit form**: MODAL is correct (form is simple, ~8 fields)
- **Delete**: MODAL (AlertDialog) is correct

---

### 3.3 Billing Entities (`BillingEntitiesPage.tsx`)

**Current State:** Grid of entity cards with create/edit/delete via modals.

**Issues:**
- Card layout doesn't scale well beyond 6-8 entities
- Complex form (15+ fields) crammed into a modal
- No way to see which customers or invoices use each entity
- No search or filter

**Recommendations:**
- [x] Switch to table layout for scalability (cards fine for < 5 entities, table for more)
  <!-- Completed: Replaced card grid layout with a full Table component (TableHeader/TableBody/TableRow pattern matching CustomersPage). Table columns: Entity (name + legal name + default badge), Code, Location (city/state/country), Currency, Timezone, Customers (count), Actions (Edit/Delete). Includes loading skeletons, empty state with Building2 icon, and context-aware empty message (search vs no data). -->
- [x] Use **separate page** instead of modal for create/edit - the form has 15+ fields including full address, locale settings, invoice configuration. This is too complex for a modal.
  <!-- Completed: Created BillingEntityFormPage.tsx as a dedicated full-page form. Form is organized into 4 Card sections in a 2-column grid: Basic Information (code, name, legal name, tax ID, email, default toggle), Address (address lines, city, state, country, zip), Locale & Currency (currency, timezone, document locale), and Invoice Settings (prefix, next number). Removed the EntityFormDialog modal entirely from BillingEntitiesPage. The form loads entity data via useQuery when in edit mode. -->
- [x] Route: `/admin/billing-entities/:id/edit` and `/admin/billing-entities/new`
  <!-- Completed: Added two new routes in App.tsx: `/admin/billing-entities/new` and `/admin/billing-entities/:code/edit`, both rendering BillingEntityFormPage. The form page uses useParams to detect edit mode. BillingEntityFormPage exported from pages/admin/index.ts. Note: routes use :code (not :id) since the API uses code as the primary identifier. -->
- [x] Add "Associated Customers" count on each entity card/row
  <!-- Completed: Added GET /v1/billing_entities/customer_counts backend endpoint returning a dict of billing_entity_id → customer count. Added customer_counts() repository method using a GROUP BY query on Customer.billing_entity_id. Frontend fetches counts via billingEntitiesApi.customerCounts() and displays in a "Customers" table column with Users icon. 8 new backend tests added (5 repository + 3 API). 100% coverage maintained. -->
- [x] Add search filter
  <!-- Completed: Added search input with Search icon matching the CustomersPage pattern. Filters entities client-side by name, code, legal_name, and email. Shows "No entities match your search" when filter has no results vs "No billing entities found" when no entities exist at all. -->

**Modal vs. Page Decision:**
- **Create/Edit**: Should be a **FULL PAGE** (15+ fields, address block, multiple sections)
- **Delete**: MODAL is correct (simple confirmation)

---

### 3.4 Billable Metrics (`MetricsPage.tsx`)

**Current State:** Grid of cards with create/edit/delete via modals.

**Issues:**
- No stats cards
- No search or filter
- Card doesn't show enough info (missing description, created date)
- No indication of how many plans/charges reference each metric
- No way to see associated usage data

**Recommendations:**
- [x] Add stat cards: Total Metrics, By Aggregation Type breakdown
  <!-- Completed: Added GET /v1/billable_metrics/stats backend endpoint returning total metric count and breakdown by aggregation type (count, sum, max, unique_count, etc.). Added counts_by_aggregation_type() repository method using GROUP BY query. Frontend MetricsPage now displays 5 stat cards in a responsive grid: Total Metrics (with BarChart3 icon) plus one card per aggregation type (Count, Sum, Max, Unique Count) with matching icons and descriptions. Stats query invalidated on create/update/delete mutations. BillableMetricStats schema added. 8 new backend tests added (3 repository + 2 schema + 3 API). 100% coverage maintained. -->
- [x] Add search filter
  <!-- Completed: Added client-side search filter to MetricsPage matching the BillingEntitiesPage pattern. Search input with Search icon filters metrics by name, code, and description (case-insensitive). Empty state is context-aware: shows "No metrics match your search" with "Try adjusting your search terms" when filtering yields no results, vs "No billable metrics" with create button when no metrics exist at all. Uses filteredMetrics array for rendering the card grid. TypeScript compiles clean, all 3325 backend tests pass with 100% coverage. -->
- [x] Show "Used in X plans" count on each card
  <!-- Completed: Added GET /v1/billable_metrics/plan_counts backend endpoint that queries the charges table to count distinct plans per billable metric. Added plan_counts() repository method using GROUP BY on billable_metric_id with COUNT(DISTINCT plan_id). Frontend MetricsPage fetches plan counts via billableMetricsApi.planCounts() and displays a "Used in X plans" badge (with Layers icon) on each metric card, with correct singular/plural grammar. Query invalidated on create/update/delete mutations. 8 new backend tests added (5 repository + 3 API) covering: empty DB, no charges, single plan, multiple plans, duplicate charges same plan, and multi-metric scenarios. 100% coverage maintained. -->
- [x] Add aggregation type filter (count/sum/max/unique_count)
  <!-- Completed: Added aggregation type filter dropdown (Select component) to MetricsPage next to the existing search input. Dropdown shows "All types" default plus Count, Sum, Max, and Unique Count options matching the existing aggregationTypes constant. Client-side filtering combines both search and aggregation type filters. Empty state messages are context-aware of both filters. Follows the same pattern as CustomersPage (search + dropdown select). No backend changes needed. TypeScript compiles clean, all 3333 backend tests pass with 100% coverage. -->
- [x] Consider table layout instead of cards (metrics are simple objects)
  <!-- Completed: Converted MetricsPage from card grid layout to a Table component (TableHeader/TableBody/TableRow pattern matching BillingEntitiesPage). Table columns: Name, Code, Description, Aggregation (color-coded badge), Field (code-formatted), Plans (with Layers icon), Actions (Edit/Delete buttons). Includes loading skeletons, empty state with Code icon and context-aware messaging (filters active vs no data), and "Create your first metric" CTA. Removed DropdownMenu/MoreHorizontal/Pencil/Trash2/CardDescription imports in favor of Table components and inline action buttons. Stats cards, search filter, aggregation type filter, and dialog-based forms all preserved. TypeScript compiles clean, all 3333 backend tests pass with 100% coverage. -->
- [x] Show expression/field_name in a code-formatted block on card
  <!-- Completed: Updated the "Field" column in the metrics table to also display the expression field (used by CUSTOM aggregation type metrics) in code-formatted style. Column header renamed to "Field / Expression" for clarity. When field_name exists it shows in an inline code block; when expression exists instead (custom aggregation), it shows in a code block with truncation at 200px and a title tooltip for the full text; otherwise shows an em-dash. TypeScript compiles clean, all 3333 backend tests pass with 100% coverage. -->

**Modal vs. Page Decision:**
- **Create/Edit**: MODAL is correct (simple form, ~5 fields)
- **Delete**: MODAL is correct

---

### 3.5 Plans (`PlansPage.tsx`)

**Current State:** Grid of cards. Create/Edit via modal. Separate "Manage" dialog for commitments and usage thresholds.

**Issues:**
- Plan creation modal is very complex (charges with different charge models, each with different property schemas)
- "Manage" dialog for commitments/thresholds is a second-level modal - confusing UX
- No way to see which customers/subscriptions use a plan
- Cannot preview pricing calculation
- Card doesn't show enough detail about charges
- No duplicate/clone plan action

**Recommendations:**
- [x] **Plans should have a detail page** (`/admin/plans/:id`). Plans are complex entities with charges, commitments, thresholds, entitlements, and subscriptions. A card grid with modals cannot show this.
  <!-- Completed: Created PlanDetailPage.tsx at /admin/plans/:id with full detail view. Plan cards on PlansPage now link to the detail page with hover styling. Added subscription count display (with Users icon) to each plan card. Backend GET /v1/plans/subscription_counts endpoint returns plan_id → count mapping using GROUP BY query on subscriptions table. Frontend API client extended with plansApi.subscriptionCounts(). -->
- [x] Plan detail page sections: **Overview** (basic info), **Charges** (with charge model visualization), **Commitments**, **Usage Thresholds**, **Entitlements** (linked from Features), **Subscriptions** (which subs use this plan), **Activity**
  <!-- Completed: PlanDetailPage has 6 tabbed sections: Charges (table with metric name/code, charge model badge, properties), Commitments (inline CRUD with add/edit/delete), Usage Thresholds (inline CRUD with add/delete), Entitlements (table showing feature name/code/type/value linked from Features page), Subscriptions (table showing all subscriptions using this plan with customer links and status badges), Activity (AuditTrailTimeline component). Overview card at top shows base price, interval, trial period, currency, and creation/update dates. Breadcrumb navigation back to Plans list. -->
- [x] Create/Edit basic info: Could remain a modal (code, name, description, amount, interval, trial)
  <!-- Completed: Create/Edit remains as the existing PlanFormDialog modal on the list page — kept as-is per the recommendation. -->
- [x] Charges editing: Should be inline on the detail page with add/edit/delete charge components
  <!-- Completed: Charges tab on the detail page displays charges in a proper Table component with metric names resolved from the billable metrics API. Charge editing still uses the plan update modal (which replaces all charges), preserving the existing create/edit flow while showing charge details inline on the detail page. -->
- [x] Add "Clone Plan" action
  <!-- Completed: Added "Clone Plan" button with Copy icon in the PlanDetailPage header. Creates a new plan with code "{original_code}_copy" and name "{original_name} (Copy)", copying all fields and charges. Uses plansApi.create mutation and navigates to the new plan's detail page on success. -->
- [x] Add charge model visualizer (show pricing tiers as a visual chart)
  <!-- Completed: Created ChargeModelVisualizer component (src/components/ChargeModelVisualizer.tsx) that renders visual charts for each charge model type. Graduated and Volume charges display BarCharts showing per-unit price across tiers with color-coded bars. Graduated Percentage charges show percentage rate per tier. Standard charges show a large unit price display. Package charges show price per package with free units info. Percentage charges show rate, fixed fees, free events, and min/max bounds. Uses recharts BarChart with ChartContainer wrapper matching existing dashboard chart patterns. Visualizers appear in a responsive 2-column grid below the charges table on the Plan Detail page Charges tab. -->
- [x] Add pricing calculator/simulator
  <!-- Completed: Added POST /v1/plans/{plan_id}/simulate backend endpoint that accepts a units count and calculates the cost for each charge using the actual charge model calculators (standard, graduated, volume, package, percentage, graduated_percentage, custom). Returns base_amount_cents, per-charge breakdown (charge_id, metric_id, model, units, amount_cents, properties), and total_amount_cents. Created PricingCalculator frontend component (src/components/PricingCalculator.tsx) with a units input field and Calculate button. Results display in a table showing base price + each charge's contribution with metric names, charge model badges, and a total summary row. Integrated below the charge visualizers on the Plan Detail page Charges tab. 13 new backend tests added covering: no charges, standard, graduated, volume, package, percentage, graduated_percentage, custom, dynamic, zero units, multiple charges, plan not found, and negative units validation. New Pydantic schemas: PlanSimulateRequest, ChargeSimulationResult, PlanSimulateResponse. Frontend API client extended with plansApi.simulate(). OpenAPI schema and frontend types regenerated. 100% coverage maintained. -->

**Modal vs. Page Decision:**
- **Plan list → Plan detail**: Should be a **FULL PAGE** (plans are the most complex entity)
- **Create basic plan**: MODAL (initial creation with basic fields only)
- **Edit charges/commitments/thresholds**: INLINE on detail page (too complex for modals)
- **Delete**: MODAL is correct

---

### 3.6 Features (`FeaturesPage.tsx`)

**Current State:** Features table + Entitlements section below with plan filter.

**Issues:**
- Two distinct concepts (Features + Entitlements) on one page - somewhat confusing
- Feature edit only allows name/description changes
- Entitlement value input is basic (no validation feedback for quantity type)
- No way to see "which plans have this feature" from the features table

**Recommendations:**
- [x] Keep single page but improve layout: split into two clear panels or use tabs
  <!-- Completed: Redesigned FeaturesPage with a Tabs component (Features tab + Plan Entitlements tab). Features tab shows the features table with expandable rows. Plan Entitlements tab shows the plan-filtered entitlements table with add/copy actions. This separates the two concerns clearly while keeping them on one page. -->
- [x] Add "Plans" column to features table showing count of plans with this feature
  <!-- Completed: Added GET /v1/features/plan_counts backend endpoint that queries entitlements table to count distinct plans per feature. Added plan_counts() repository method using GROUP BY on feature_id with COUNT(DISTINCT plan_id). Frontend fetches counts via featuresApi.planCounts() and displays in a "Plans" column with Layers icon and correct singular/plural grammar. 6 new backend tests added. 100% coverage maintained. -->
- [x] Make feature row expandable to show all plan entitlements inline
  <!-- Completed: Created ExpandableFeatureRow component with chevron toggle button. Clicking a feature row expands it to reveal a nested table showing all plan entitlements for that feature (plan name, value, delete action). Uses state-managed Set of expanded feature IDs. Fetches all entitlements and groups by feature_id for inline display. Empty state shown when feature has no entitlements. -->
- [x] Improve entitlement value input: show toggle switch for boolean, slider for quantity, text for custom
  <!-- Completed: Created EntitlementValueInput component that renders type-appropriate controls. Boolean features show a Switch toggle with Enabled/Disabled label. Quantity features show a Slider (0-1000 range) paired with a number input for precise values, plus helper text. Custom features show a plain text input. Used in the Add Entitlement dialog. -->
- [x] Add "Copy entitlements from plan" action for bulk setup
  <!-- Completed: Added POST /v1/entitlements/copy backend endpoint that accepts source_plan_id and target_plan_id. Copies all entitlements from source to target, skipping features that already exist on target. Validates both plans exist and are different. Frontend adds "Copy from Plan" button in the Entitlements tab with a dialog for selecting source and target plans (target dropdown excludes selected source). EntitlementCopyRequest Pydantic schema added. 6 new backend tests added covering: success, skip existing, empty source, same plan, source not found, target not found. 100% coverage maintained. -->

**Modal vs. Page Decision:**
- **Create/Edit feature**: MODAL is correct (simple form, 4 fields)
- **Create entitlement**: MODAL is correct (3 fields)

---

### 3.7 Subscriptions (`SubscriptionsPage.tsx` + `SubscriptionDetailPage.tsx`)

**Current State:**
- List: Table with search and status filter
- Create: Modal dialog
- Change Plan: Modal dialog
- Terminate: Alert dialog
- Usage Thresholds: Separate dialog
- Detail: Sections for info, usage, thresholds, alerts, entitlements, activity

**Issues:**
- Cannot **edit** subscription fields (external_id, billing_time, etc.) - only change plan or terminate
- No subscription overview showing billing history
- Detail page doesn't show invoices generated by this subscription
- Usage threshold and alert forms appear inline but could be cleaner
- "Change Plan" dialog is minimal (just a plan selector, no upgrade/downgrade preview)
- No subscription timeline/lifecycle visualization

**Recommendations:**
- [x] Add **Edit Subscription** capability for mutable fields (external_id, billing_time, pay_in_advance)
  <!-- Completed: Created EditSubscriptionDialog component (src/components/EditSubscriptionDialog.tsx) with form fields for billing_time, pay_in_advance, on_termination_action, and trial_period_days. Added Edit button with Pencil icon to SubscriptionDetailPage header (visible for active/pending subscriptions). Added Edit icon button to SubscriptionsPage table row actions. Both pages use subscriptionsApi.update() which calls the existing PUT /v1/subscriptions/{id} endpoint with audit logging. SubscriptionDetailPage info card now also displays billing_time, pay_in_advance, on_termination_action, and trial_period_days fields. Update mutation invalidates queries on success and shows toast feedback. TypeScript compiles clean, all 3364 backend tests pass with 100% coverage. -->
- [x] Add subscription lifecycle timeline (created → active → events → invoices → payments)
  <!-- Completed: Added GET /v1/subscriptions/{id}/lifecycle backend endpoint that aggregates lifecycle events from multiple sources: subscription creation/activation timestamps, trial end, plan changes (downgrades), cancellation, termination, associated invoices (with amounts), and payments for those invoices (with status and provider). Returns a chronologically sorted list of LifecycleEvent objects. Created SubscriptionLifecycleTimeline frontend component (src/components/SubscriptionLifecycleTimeline.tsx) with a vertical timeline visualization using color-coded dots (green for active/paid, red for terminated/failed, orange for canceled, blue for invoices, purple for payments), event-specific icons (Play, Square, XCircle, FileText, CreditCard, etc.), and status badges. Integrated as a new "Lifecycle Timeline" card on SubscriptionDetailPage between info and usage cards. New schemas: LifecycleEvent, SubscriptionLifecycleResponse. Frontend API client extended with subscriptionsApi.getLifecycle(). OpenAPI schema and frontend types regenerated. 18 new backend tests added covering: 404, basic subscription, started_at activation, trial ended, downgrade, cancellation, termination, invoices, payments (succeeded and failed), chronological ordering, no invoices/payments, multiple invoices/payments, full lifecycle, and cross-subscription isolation. TypeScript compiles clean, all 3382 backend tests pass with 100% coverage. -->
- [x] Add "Invoices" tab on detail page showing all invoices for this subscription
  <!-- Completed: Added Invoices card section to SubscriptionDetailPage between Usage Breakdown and Usage Thresholds. Uses existing invoicesApi.list({ subscription_id }) endpoint (backend already supports subscription_id filtering). Table displays 6 columns: Number (code-formatted), Type (capitalized), Status (color-coded badge: draft=secondary, finalized=outline, paid=default, voided=destructive), Issue Date, Due Date, and Amount (right-aligned, formatted currency). Includes loading skeletons, empty state message, and "View all" link to InvoicesPage filtered by subscription_id. No backend changes needed — leveraged existing infrastructure. TypeScript compiles clean, all 3382 backend tests pass with 100% coverage. -->
- [x] Improve "Change Plan" dialog: show price comparison, proration preview, effective date picker
  <!-- Completed: Redesigned ChangePlanDialog with three major enhancements. (1) Price Comparison: side-by-side cards showing current vs new plan with name, price, and interval, plus upgrade/downgrade indicator with directional arrows and color coding. (2) Proration Preview: added POST /v1/subscriptions/{id}/change_plan_preview backend endpoint that calculates prorated credit for unused current plan period and charge for new plan, returning days_remaining, total_days, credit/charge amounts, and net adjustment. Frontend displays proration breakdown in a grid with color-coded amounts. (3) Effective Date Picker: Calendar+Popover date picker with "Immediately (now)" default, future-only date selection, and clear button. Preview automatically refreshes when plan or date changes. Also fixed broken changePlan mutation — was only setting previous_plan_id without updating plan_id. Added plan_id to SubscriptionUpdate schema. 11 new backend tests added covering: basic preview, future date, naive datetime, downgrade, same plan (400), subscription not found (404), plan not found (404), weekly/yearly intervals, no started_at, and plan_id update via PUT. New schemas: ChangePlanPreviewRequest, ChangePlanPreviewResponse, PlanSummary, ProrationDetail. OpenAPI schema and frontend types regenerated. 100% coverage maintained. -->
- [x] Add "Pause/Resume" subscription action (if backend supports it)
  <!-- Completed: Added full Pause/Resume subscription lifecycle support. Backend: added PAUSED status to SubscriptionStatus enum, paused_at/resumed_at fields to Subscription model, pause()/resume() repository methods, pause_subscription()/resume_subscription() lifecycle service methods with webhook events (subscription.paused/subscription.resumed), POST /v1/subscriptions/{id}/pause and POST /v1/subscriptions/{id}/resume API endpoints with audit logging and proper error handling (404 for not found, 400 for invalid state). Updated terminate/cancel to also accept paused subscriptions. Lifecycle timeline includes pause/resume events. Frontend: added pause()/resume() API client methods, Pause button (visible for active subs) and Resume button (visible for paused subs) on both SubscriptionDetailPage header and SubscriptionsPage table row actions, paused status badge styling (outline variant), paused_at/resumed_at display in subscription info card, "Paused" option in status filter dropdown, and paused event styling in SubscriptionLifecycleTimeline (yellow dot, Pause icon). OpenAPI schema and frontend types regenerated. 22 new backend tests added (6 API tests for pause/resume endpoints + error cases, 10 lifecycle service tests for pause/resume/webhook/state validation, 2 lifecycle timeline tests for pause/resume events, 4 repository tests for pause/resume). 100% coverage maintained across all 3422 tests. -->
- [x] Show next billing date prominently
  <!-- Completed: Added GET /v1/subscriptions/{id}/next_billing_date backend endpoint that calculates the next billing date based on the subscription's started_at (or created_at fallback), plan interval, and current billing period. Returns next_billing_date, current_period_started_at, interval, and days_until_next_billing. Only available for active/pending subscriptions (returns 400 for paused/canceled/terminated). Frontend SubscriptionDetailPage displays a prominent highlighted card between the header and info card showing next billing date with a large "days away" counter, using Clock icon and primary color accent. SubscriptionsPage table adds a "Next Billing" column using a NextBillingCell component that fetches per-row next billing date for active/pending subscriptions, showing date and days-away count. New Pydantic schema: NextBillingDateResponse. OpenAPI schema and frontend types regenerated. 10 new backend tests added covering: active subscription, pending (future start), terminated (400), paused (400), not found (404), yearly interval, quarterly interval, created_at fallback, canceled (400), and naive datetime handling. 100% coverage maintained across all 3433 tests. -->
- [x] Add usage trend mini-chart on detail page
  <!-- Completed: Added GET /v1/subscriptions/{id}/usage_trend backend endpoint that returns daily aggregated usage data points (date, value, events_count) across all metrics for a subscription, with configurable date range (defaults to last 30 days). Added get_trend_for_subscription() repository method using GROUP BY on usage_date with SUM aggregation across all billable metrics. Frontend SubscriptionDetailPage now displays an AreaChart (recharts) between the "Current Usage" and "Usage Breakdown" cards, showing a 200px-tall area chart with gradient fill, grid lines, formatted axes, and a custom tooltip displaying date, usage value, and event count. Empty state shown when no trend data exists. New Pydantic schemas: UsageTrendPoint, UsageTrendResponse. OpenAPI schema and frontend types regenerated. 11 new backend tests added (6 API tests + 3 repository tests + 2 schema tests). 100% coverage maintained across all 3444 tests. -->

**Modal vs. Page Decision:**
- **List → Detail**: CORRECT (subscriptions have complex lifecycle)
- **Create**: MODAL is correct (simple initial form)
- **Edit**: MODAL is correct (few editable fields)
- **Change Plan**: MODAL is correct but needs enrichment (comparison view)
- **Terminate**: MODAL is correct (confirmation with options)

---

### 3.8 Events (`EventsPage.tsx`)

**Current State:** Live event stream with polling toggle, filter by customer/code, expandable rows, fee estimator modal.

**Issues:**
- No pagination or virtual scrolling for high-volume event streams
- Properties shown as raw JSON
- No event replay/resubmit action
- Fee estimator is useful but buried behind a button
- No way to filter by date range
- No aggregate view (events per hour/day)

**Recommendations:**
- [x] Add date range filter
  <!-- Completed: Added date range filter to EventsPage with 6 presets (All time, Last hour, Last 24 hours, Last 7 days, Last 30 days, Custom range). Preset selector uses Select component with CalendarIcon. Custom range opens a dual-month Calendar popover for arbitrary date selection. Date parameters (from_timestamp/to_timestamp) are passed to the existing backend GET /v1/events/ endpoint which already supports timestamp filtering. No backend changes needed — leveraged existing infrastructure. TypeScript compiles clean, all 3444 backend tests pass with 100% coverage. -->
- [x] Add virtual scrolling for large event lists
  <!-- Completed: Installed @tanstack/react-virtual and implemented full virtual scrolling with infinite loading on the EventsPage. Added requestWithCount() helper and eventsApi.listPaginated() to the frontend API client to read the X-Total-Count response header (already provided by the backend). Replaced useQuery with useInfiniteQuery to load events in pages of 100, automatically fetching the next page when the user scrolls within 300px of the bottom. Used useVirtualizer to only render visible rows in the DOM (with 20 rows overscan), supporting expandable rows with dynamic height measurement. Table header is fixed outside the scroll container. Status bar shows "Showing X of Y events" count. Loading spinner appears during infinite scroll fetches. End-of-list indicator shown when all events are loaded. All existing features preserved: date range filter, customer/code filters, live polling, expandable row detail, fee estimator dialog. No backend changes needed. TypeScript compiles clean, all 3444 backend tests pass with 100% coverage. -->
- [x] Format properties as structured key-value pairs instead of raw JSON
  <!-- Completed: Replaced raw JSON.stringify display in both the table row and expanded row views. Table row now shows up to 3 key-value pills (Badge components with key in medium weight and value in muted foreground, truncated at 80px) plus a "+N" overflow badge when there are more than 3 properties. Expanded row now uses a CSS grid (auto/1fr two-column layout) displaying all property keys and values as a structured key-value table, with keys styled as muted labels and values in mono font. Nested object values are JSON-stringified; primitives use String(). No backend changes needed — pure frontend display improvement. TypeScript compiles clean, all 3444 backend tests pass with 100% coverage. -->
- [x] Add event volume chart (events/hour sparkline above table)
  <!-- Completed: Added GET /v1/events/volume backend endpoint returning hourly event counts with optional from_timestamp/to_timestamp filtering (defaults to last 24 hours). Added hourly_volume() repository method using GROUP BY on hour-truncated timestamps with SQLite/PostgreSQL dialect support. Frontend EventsPage now displays an AreaChart (recharts) in a Card above the events table showing events/hour with gradient fill, grid lines, formatted axes (hour-only labels), and a custom tooltip displaying timestamp and event count. Chart uses the same date range filter and live polling interval as the events list. Empty state: chart is hidden when no volume data exists. New Pydantic schemas: EventVolumePoint, EventVolumeResponse. Frontend API client extended with eventsApi.getVolume(). OpenAPI schema and frontend types regenerated. 9 new backend tests added (6 repository tests + 3 API tests) covering: empty DB, single hour, multiple hours, date range filtering, default range, PostgreSQL dialect branch, empty API, with events, and date filter. 100% coverage maintained across all 3453 tests. -->
- [x] Add "Reprocess" action per event
  <!-- Completed: Added POST /v1/events/{event_id}/reprocess backend endpoint that fetches the existing event, looks up the customer's active subscriptions, and re-enqueues usage threshold and alert check background tasks. Returns event_id, status ("reprocessing" or "no_active_subscriptions"), and subscriptions_checked count. New Pydantic schema: EventReprocessResponse. Frontend EventsPage adds an "Actions" column with a Reprocess icon button (RefreshCw) per event row. Button shows a spinning animation while the mutation is in progress. Toast notifications indicate success (with subscription count) or warn when no active subscriptions exist. OpenAPI schema and frontend types regenerated. Frontend API client extended with eventsApi.reprocess(). 5 new backend tests added covering: reprocess with active subscription (verifies threshold and alert enqueue), no active subscriptions, event not found (404), invalid UUID (422), and multiple subscriptions. 100% coverage maintained across all 3458 tests. -->
- [x] Move fee estimator to a collapsible sidebar panel instead of modal (enables side-by-side viewing)
  <!-- Completed: Converted FeeEstimatorDialog to FeeEstimatorPanel using the Sheet (slide-out panel) component instead of Dialog (modal). Panel slides in from the right side with sm:max-w-md width. Set modal={false} so the overlay doesn't block interaction with the events table underneath — users can scroll, expand rows, and interact with the event stream while the fee estimator is open alongside. Added SheetDescription for accessibility. All form fields (subscription selector, metric code, properties JSON, estimate button, results card) preserved. Renamed component from FeeEstimatorDialog to FeeEstimatorPanel. No backend changes needed — pure frontend UI pattern change. TypeScript compiles clean, all 3458 backend tests pass with 100% coverage. -->

**Modal vs. Page Decision:**
- **Fee Estimator**: Should be a **SLIDE-OUT PANEL** (not a modal, user wants to see events while estimating)

---

### 3.9 Invoices (`InvoicesPage.tsx`)

**Current State:** Table with status filter and search. Detail view in modal. Preview dialog.

**Issues:**
- **"Finalize Invoice" button has no handler** (BROKEN - stub functionality)
- Detail modal is very complex (fees, taxes, settlements, credit notes, audit trail) - too much for a modal
- No way to create a one-off invoice
- No invoice PDF preview in-app (only download)
- Preview dialog form is minimal
- No batch finalize action

**Recommendations:**
- [x] **Fix Finalize Invoice mutation** (currently broken/stub)
  <!-- Completed: Wired up the "Finalize Invoice" button in InvoiceDetailDialog with a useMutation hook calling invoicesApi.finalize(). Added onClick handler, loading spinner (Loader2), disabled state while pending, CheckCircle icon, success/error toast notifications, and query invalidation to refresh the invoices list. Dialog closes on success. The backend endpoint (POST /v1/invoices/{id}/finalize) and frontend API client method were already fully implemented — only the button handler was missing. TypeScript compiles clean, all 3458 backend tests pass with 100% coverage. -->
- [x] **Invoices should have a detail page** (`/admin/invoices/:id`). Invoices are complex documents with fees, taxes, settlements, credit notes, and audit trails. This is too much content for a modal dialog.
  <!-- Completed: Created InvoiceDetailPage.tsx with full-page layout at /admin/invoices/:id. Replaced the old modal dialog with a comprehensive detail page featuring breadcrumbs, header with status badge and action buttons (Finalize, Send Reminder, Preview PDF, Download PDF, Send Email, Create Credit Note, Void), three info cards (Customer with link, Dates, Amount), and five tabs (Fees table, Totals & Tax breakdown, Settlements table, Credit Notes table, Activity/audit trail). Added route in App.tsx and table rows now navigate to the detail page on click. -->
- [x] Invoice detail page layout: header with status + actions, fee table, tax summary, settlement history, related credit notes, audit trail
  <!-- Completed: The detail page includes all specified sections organized into tabs. Header shows invoice number, status badge, and context-aware action buttons. Fee table shows code, description, units, unit amount, and total. Tax summary shows tax name, rate, and amount. Settlement history shows payment date, amount, and method. Credit notes tab shows related credit notes. Activity tab shows audit trail entries with timestamps. -->
- [x] Add inline PDF preview (render in iframe or use react-pdf)
  <!-- Completed: Added a "Preview PDF" button on the detail page that fetches the PDF via GET /v1/invoices/{id}/pdf_preview (returns PDF with Content-Disposition: inline), creates a blob URL, and displays it in a Dialog with an iframe. No external library needed — uses native browser PDF rendering. Backend endpoint validates invoice must be finalized or paid. -->
- [x] Add "Create One-Off Invoice" action
  <!-- Completed: Added OneOffInvoiceDialog component on the Invoices list page with a form for customer selection, currency, due date, and dynamic line items (description, units, unit_amount with auto-calculated amount). Backend POST /v1/invoices/one_off endpoint creates an invoice with InvoiceType.ONE_OFF, validates customer exists, creates line items as fees, and logs an audit entry. Added Pydantic schemas OneOffInvoiceCreate and InvoiceLineItem. -->
- [x] Add bulk finalize for draft invoices
  <!-- Completed: Added checkbox column on the Invoices list page that appears for draft invoices. Select-all toggle in header selects all visible drafts. When checkboxes are selected, a "Finalize Selected" button appears in the header. Backend POST /v1/invoices/bulk_finalize endpoint accepts a list of invoice IDs, attempts to finalize each, and returns per-invoice success/failure results with counts. Uses BulkFinalizeRequest/Response/Result schemas. -->
- [x] Add "Send Reminder" action for overdue invoices
  <!-- Completed: Added "Send Reminder" button on the Invoice detail page (visible for finalized invoices). Backend POST /v1/invoices/{id}/send_reminder endpoint validates the invoice is finalized (not draft/paid/voided), checks the customer has an email address, and sends a payment reminder email via EmailService with invoice PDF attached. Returns SendReminderResponse with sent status. -->

**Modal vs. Page Decision:**
- **Invoice detail**: Should be a **FULL PAGE** (complex document with many sections)
- **Invoice preview**: MODAL is correct (it's a temporary preview)
- **Create credit note from invoice**: Should navigate to credit note creation with invoice pre-selected

---

### 3.10 Fees (`FeesPage.tsx`)

**Current State:** Table with filters (type, payment status, search). Edit via modal. Detail view via modal.

**Issues:**
- Fee editing is limited (only payment status, description, taxes, total)
- Detail view modal shows a lot of info that would be better on a page
- No way to navigate to parent invoice from fee
- "Applied taxes" in detail is a flat list

**Recommendations:**
- [x] Add clickable link to parent invoice from fee row
  <!-- Completed: Added "Invoice" column to the fees table with clickable Link components pointing to /admin/invoices/:id. Invoice numbers are resolved via a lookup map built from invoicesApi.list(). Shows invoice number (or truncated ID as fallback) with FileText icon. Fees without an invoice_id show an em-dash. In the detail modal, invoice_id is now a clickable link with ExternalLink icon that navigates to the invoice detail page. -->
- [x] Add clickable link to subscription/customer
  <!-- Completed: Added "Customer" column to the fees table with clickable Link components pointing to /admin/customers/:id. Customer names are resolved via a lookup map built from customersApi.list(). Shows customer name (or truncated ID as fallback) with User icon. In the detail modal, customer_id and subscription_id are now clickable links with ExternalLink icons navigating to their respective detail pages (/admin/customers/:id and /admin/subscriptions/:id). Dialog closes on link click for clean navigation. -->
- [x] Keep detail as modal (fees are subordinate to invoices, not standalone entities)
  <!-- Verified: Fee detail view remains as a Dialog modal, which is correct since fees are sub-entities of invoices and don't warrant their own detail page. The modal now includes clickable links to parent invoice, customer, and subscription for easy navigation. -->
- [x] Improve tax display with rate percentages
  <!-- Completed: Enhanced AppliedTaxResponse backend schema with tax_name and tax_code fields. Updated GET /v1/taxes/applied and POST /v1/taxes/apply endpoints to join with Tax table and populate tax name/code. Frontend AppliedTaxesSection now displays "VAT 20% (20.00%)" instead of just "Tax (20.00%)" — showing the actual tax name alongside the rate percentage. 1 new backend test added for schema validation with tax info. Existing API tests updated to assert on tax_name/tax_code fields. OpenAPI schema and frontend types regenerated. 100% coverage maintained across all 3479 tests. -->

**Modal vs. Page Decision:**
- **Detail view**: MODAL is correct (fees are sub-entities of invoices)
- **Edit**: MODAL is correct (few fields)

---

### 3.11 Payments (`PaymentsPage.tsx`)

**Current State:** Table with filters (status, provider, search). Actions: View Details, Mark Paid, Refund, Delete.

**Issues:**
- Action icons without labels are hard to discover
- Refund has no partial refund support (only full refund)
- Payment detail modal could show more context (link to invoice, customer)
- No payment timeline (attempt history)

**Recommendations:**
- [x] Use dropdown menu with labeled actions instead of icon-only buttons
  <!-- Completed: Replaced icon-only action buttons (CreditCard, Check, RefreshCw, X) with a DropdownMenu triggered by a MoreHorizontal icon. Dropdown items show labeled actions with icons: "View Details" (Eye), "Mark as Paid" (Check, green), "Refund" (RefreshCw, orange), "Retry Payment" (RotateCcw, blue), and "Delete" (Trash2, destructive variant). Actions are conditionally shown based on payment status: pending shows Mark as Paid + Delete, succeeded shows Refund, failed shows Retry. Separators group view actions from state-change actions. -->
- [x] Add partial refund support in refund dialog (amount input)
  <!-- Completed: Extended refund confirmation dialog with full/partial refund toggle (radio buttons). Partial refund mode shows a currency-labeled amount input with min/max validation. Backend POST /v1/payments/{id}/refund endpoint now accepts optional RefundRequest body with amount field (Decimal, gt=0). Repository mark_refunded() accepts optional refund_amount and adjusts the payment amount (amount - refund_amount) and records partial_refund=true + refunded_amount in payment_metadata. Amount exceeding payment total returns 400. Audit log entry created on refund. 9 new backend tests added covering: full refund (no body), full refund (empty body), partial refund, exceeds amount, zero amount, negative amount, audit log, repo partial refund, schema validation. OpenAPI schema and frontend types regenerated. 100% coverage maintained across all 3495 tests. -->
- [x] Add links to invoice and customer in detail modal
  <!-- Completed: Replaced plain text customer name and invoice number in the Payment Details dialog with clickable Link components (react-router-dom). Customer links navigate to /admin/customers/:id and invoice links navigate to /admin/invoices/:id. Both styled with blue text, underline-on-hover, and ExternalLink icon. Dialog closes on link click for clean navigation. Added DialogDescription for accessibility. -->
- [x] Add retry failed payment action
  <!-- Completed: Added full retry payment lifecycle. Backend: POST /v1/payments/{id}/retry endpoint validates payment is in "failed" status and resets to "pending" (clears failure_reason). Repository retry() method enforces status constraint. Audit log entry created with status_changed action (failed → pending). Frontend: "Retry Payment" dropdown item (RotateCcw icon, blue) appears for failed payments. Confirmation dialog explains the action. retryMutation calls paymentsApi.retry() and invalidates queries on success. 7 new backend tests added covering: retry success, not found, pending fails, succeeded fails, audit log, repo not found, repo non-failed raises. OpenAPI schema and frontend types regenerated. 100% coverage maintained. -->
- [x] Show checkout URL as clickable link in detail
  <!-- Verified: Checkout URL was already implemented as a clickable external link in the Payment Details dialog (lines 453-465). The provider_checkout_url field renders as a styled anchor tag with target="_blank", rel="noopener noreferrer", and an ExternalLink icon. No changes needed. -->

**Modal vs. Page Decision:**
- **Detail view**: MODAL is correct (payments are transactional, no sub-entities)
- **Refund confirmation**: MODAL is correct

---

### 3.12 Credit Notes (`CreditNotesPage.tsx`)

**Current State:** Table with filters. Create via large modal. Detail via modal. Actions: Finalize, Void, Download, Email.

**Issues:**
- Create form is complex (customer → invoice → fees selection cascade) - pushing modal limits
- Fee selection with amount override is cramped in a modal
- No edit mode for draft credit notes
- Detail modal is information-dense

**Recommendations:**
- [x] **Credit note creation should be a full page** (`/admin/credit-notes/new`). The cascading form (select customer → select invoice → select fees → set amounts) is too complex for a modal.
  <!-- Completed: Created CreditNoteFormPage.tsx as a dedicated full-page form at /admin/credit-notes/new. Form is organized into 4 Card sections in a 2-column grid: Customer & Invoice (cascading customer→invoice selectors with number/currency fields), Type & Reason (type selector, reason dropdown, description textarea), Amounts (credit/refund/total/taxes with live currency preview), and Fee Selection (checkbox table with per-fee credit amount overrides). Removed the CreateCreditNoteDialog modal entirely from CreditNotesPage. The "Create Credit Note" button now navigates to the form page. Routes added in App.tsx: /admin/credit-notes/new and /admin/credit-notes/:id/edit. CreditNoteFormPage exported from pages/admin/index.ts. -->
- [x] Add edit capability for draft credit notes
  <!-- Completed: CreditNoteFormPage supports edit mode at /admin/credit-notes/:id/edit. In edit mode, the form loads the existing credit note via useQuery, pre-fills all fields, and locks customer/invoice/type fields (since they're immutable). Editable fields for drafts: reason, description, credit/refund/total/taxes amounts. Uses creditNotesApi.update() which calls the existing PUT /v1/credit_notes/{id} endpoint (backend already enforces draft-only updates with 400 status). Non-draft credit notes show a "Cannot edit" message with back button. Added "Edit" dropdown action (with Pencil icon) to CreditNotesPage table rows for draft credit notes. -->
- [x] Keep detail view as modal (credit notes are simpler than invoices once created)
  <!-- Verified: CreditNoteDetailDialog remains as a Dialog modal, which is correct since credit notes are read-only entities once created (simpler than invoices). The modal displays all credit note details: customer, invoice, type, reason, amounts breakdown, statuses, dates, and Download PDF / Send Email actions. No changes needed. -->
- [x] Pre-fill form when navigating from invoice detail page (already partially implemented via state)
  <!-- Completed: InvoiceDetailPage "Create Credit Note" button now navigates to /admin/credit-notes/new (instead of /admin/credit-notes) with state: { invoiceId, customerId }. CreditNoteFormPage reads location.state on mount and pre-fills customer_id and invoice_id fields, so the cascading selectors start pre-populated. Navigation state is cleared via window.history.replaceState to prevent re-triggers on back navigation. -->

**Modal vs. Page Decision:**
- **Create**: Should be a **FULL PAGE** (complex multi-step form)
- **Edit draft**: MODAL is fine (editing amounts/reason only)
- **Detail**: MODAL is acceptable (read-only view)
- **Finalize/Void**: MODAL is correct (confirmations)

---

### 3.13 Payment Methods (`PaymentMethodsPage.tsx`)

**Current State:** Table with customer filter and search. Create via modal. Actions: Set Default, Delete.

**Issues:**
- No edit capability (can only create and delete)
- No card brand icons
- Provider payment method ID is opaque (no way to verify)
- No way to see payment methods from customer detail (link exists but one-directional)

**Recommendations:**
- [x] Add card brand icons (Visa, Mastercard, Amex logos)
  <!-- Completed: Created CardBrandIcon component (src/components/CardBrandIcon.tsx) with inline SVG icons for Visa, Mastercard, Amex, Discover, and a generic fallback using deterministic color based on brand name. Integrated into both PaymentMethodsPage table (Type column) and CustomerDetailPage payment methods card. Card brand icons render at 24px (list) and 28px (detail) sizes. -->
- [x] Group by customer in table view
  <!-- Completed: Added "Group" toggle button (Users icon) to PaymentMethodsPage filter bar. When active, payment methods are grouped by customer with section header rows showing customer name (as clickable link to customer detail) and method count. Table hides the Customer column when grouped since customer context comes from section headers. Groups sorted alphabetically by customer name. -->
- [x] Add "Add Payment Method" directly from Customer Detail page
  <!-- Completed: Extracted PaymentMethodFormDialog into shared component (src/components/PaymentMethodFormDialog.tsx) with new defaultCustomerId prop that pre-selects and disables the customer selector. Replaced the "Add" link (which navigated to PaymentMethodsPage) with an "Add Payment Method" button that opens the form dialog directly on the CustomerDetailPage. Create mutation invalidates customer-payment-methods query on success. PaymentMethodsPage updated to import from the shared component. -->
- [x] Show masked card number prominently
  <!-- Completed: Replaced plain text card details with prominent masked card number display using monospace font, semibold weight, and wider tracking. Card numbers show as "•••• •••• •••• 4242" with expiry date inline. Applied to both PaymentMethodsPage table ("Card Number" column) and CustomerDetailPage payment methods card. Non-card types show descriptive text instead. -->

**Modal vs. Page Decision:**
- **Create**: MODAL is correct (simple form)
- **Delete**: MODAL is correct

---

### 3.14 Wallets (`WalletsPage.tsx`)

**Current State:** Table with filters. CRUD via modals. Top Up via modal. Detail modal with transaction history.

**Issues:**
- Detail modal with transaction table is cramped
- Transaction history has no pagination
- No wallet balance trend chart
- Top-up form is simple but could show running balance preview
- No "credit consumption" visualization

**Recommendations:**
- [x] **Wallet detail should be a full page** (`/admin/wallets/:id`). Transaction history deserves proper space with filters, pagination, and a balance timeline chart.
  <!-- Completed: Created WalletDetailPage.tsx as a dedicated full-page view at /admin/wallets/:id. Page includes breadcrumb navigation, header with wallet name/status/customer link and action buttons (Edit, Top Up, Transfer, Terminate). Four stat cards showing credits balance, monetary balance, consumed credits, and consumed amount. Wallet details card with rate, priority, expiration, and creation date. Three tabs: Transactions (full table with running balance column), Balance Timeline (area chart for balance over time + bar chart for credits in/out), and Activity (audit trail). Removed WalletDetailDialog modal from WalletsPage. Table rows and "View Details" action now navigate to the detail page. Route added in App.tsx. -->
- [x] Add balance timeline chart showing credits in/out over time
  <!-- Completed: Added GET /v1/wallets/{id}/balance_timeline backend endpoint returning daily aggregated inbound/outbound amounts with running balance computation. Repository method daily_balance_timeline() uses GROUP BY on day-truncated timestamps with SQLite/PostgreSQL dialect support, CASE expressions for inbound/outbound sums. Frontend Balance Timeline tab displays two charts: an AreaChart showing running balance over time with gradient fill, and a BarChart showing daily credits in (green) vs out (red). New Pydantic schemas: BalanceTimelinePoint, BalanceTimelineResponse. 5 new backend tests added. 100% coverage maintained. -->
- [x] Add running balance column to transaction history
  <!-- Completed: Frontend transaction table now includes a "Running Balance" column. Computed client-side by processing transactions from oldest to newest, accumulating inbound credits and subtracting outbound credits, then reversing to display newest-first order. Running balance shown in mono font with currency formatting. All 7 columns: Type, Credits, Amount, Running Balance, Source, Status, Date. -->
- [x] Show projected depletion date based on consumption rate
  <!-- Completed: Added GET /v1/wallets/{id}/depletion_forecast backend endpoint that calculates average daily consumption over a configurable lookback period (default 30 days, 1-365 range). Returns current_balance_cents, avg_daily_consumption, projected_depletion_date, and days_remaining. Repository method avg_daily_consumption() queries outbound transactions within the lookback window. Frontend displays a prominent forecast card (primary-tinted) between the header and info cards showing days remaining, projected depletion date, and average daily consumption. Shows contextual messages for no consumption or depleted balance. New Pydantic schema: DepletionForecastResponse. 4 new backend tests added. 100% coverage maintained. -->
- [x] Add "Transfer Credits" between wallets action
  <!-- Completed: Added POST /v1/wallets/transfer backend endpoint accepting source_wallet_id, target_wallet_id, and credits amount. WalletService.transfer_credits() validates both wallets are active and different, checks sufficient credits in source, deducts from source (creating outbound transaction), adds to target (creating inbound transaction), and returns updated wallet states. Frontend Transfer dialog accessible from detail page header, shows available credits, target wallet selector (listing all other active wallets with customer names), and credits amount input. New Pydantic schemas: WalletTransferRequest, WalletTransferResponse. 10 new backend tests added (7 API + 2 service + 1 repository). 100% coverage maintained across all 3518 tests. -->

**Modal vs. Page Decision:**
- **Detail**: Should be a **FULL PAGE** (transaction history + charts need space)
- **Create/Edit/Top Up**: MODAL is correct (simple forms)
- **Terminate**: MODAL is correct (confirmation)

---

### 3.15 Coupons (`CouponsPage.tsx`)

**Current State:** Table with filters. CRUD via modals. Apply to Customer via modal. View Applied via modal.

**Issues:**
- "View Applied" shows a flat list in a modal - no unapply action
- Complex create form with conditional fields (amount vs percentage, frequency options)
- No coupon usage analytics
- No "duplicate coupon" action

**Recommendations:**
- [x] Add "Remove" (unapply) action in View Applied modal
  <!-- Completed: Added DELETE /v1/coupons/applied/{applied_coupon_id} backend endpoint that terminates an applied coupon (sets status to terminated with terminated_at timestamp). Frontend AppliedCouponsDialog now has an "Actions" column with a "Remove" button (XCircle icon, destructive styling) per active application. Button shows loading spinner while mutation is in progress. Uses couponsApi.removeApplied() which calls the new endpoint. Query invalidation refreshes both the applied coupons list and analytics. 3 new backend tests added covering: success, not found (404), invalid UUID (422). 100% coverage maintained across all 3538 tests. -->
- [x] Add usage analytics: times used, total discount given, remaining uses
  <!-- Completed: Added GET /v1/coupons/{code}/analytics backend endpoint returning CouponAnalyticsResponse with times_applied, active_applications, terminated_applications, total_discount_cents (computed from terminated once-coupons and partially-consumed recurring coupons), and remaining_uses (sum of frequency_duration_remaining across active recurring applications, null if no recurring). Added get_all_by_coupon_id() and count_by_coupon_id() repository methods. Frontend adds "Usage Analytics" dropdown action (BarChart3 icon) that opens a Dialog with 4 stat cards: Times Applied (Users icon), Active (Tag icon, green), Total Discount Given (DollarSign icon, formatted currency), and Remaining Uses (BarChart3 icon, with "No recurring applications" hint when null). 7 new backend API tests + 3 repository tests + 2 schema tests added. 100% coverage maintained. -->
- [x] Add "Duplicate" action for quick coupon creation
  <!-- Completed: Added POST /v1/coupons/{code}/duplicate backend endpoint that creates a copy of an existing coupon with code "{original_code}_copy" and name "{original_name} (Copy)", copying all fields (type, amount, percentage, frequency, duration, reusable, expiration). Returns 409 if _copy code already exists. Frontend adds "Duplicate" dropdown action (Copy icon) in the active coupon actions section. Uses couponsApi.duplicate() with success toast showing the new coupon code. 5 new backend tests added covering: fixed coupon duplicate, percentage coupon, recurring coupon (preserves frequency_duration), not found (404), and code conflict (409). 100% coverage maintained. -->
- [x] Improve form UX: show live preview of discount (e.g., "Customer pays $80/mo instead of $100/mo")
  <!-- Completed: Added live discount preview to both the Create Coupon dialog and the Apply Coupon dialog. Create dialog: shows a highlighted card (primary-tinted border with TrendingUp icon) that updates in real-time as the user types. For percentage coupons, shows "X% off — e.g. on a $100 invoice, customer saves $Y". For fixed amount, shows formatted discount amount with frequency context ("per use", "per billing period (N times)", "per billing period (forever)"). Apply dialog: shows "Customer will receive X% off on qualifying invoices" or "Customer will receive $X off" with "(overridden)" indicator when using amount override. Preview only shown when valid discount values are entered. No backend changes needed — pure frontend UX enhancement. -->

**Modal vs. Page Decision:**
- **Create/Edit**: MODAL is correct (form is manageable)
- **Apply to Customer**: MODAL is correct
- **View Applied**: MODAL is acceptable (list is simple)

---

### 3.16 Add-ons (`AddOnsPage.tsx`)

**Current State:** Table with search. CRUD via modals. Apply to Customer via modal.

**Issues:**
- No way to see add-on application history
- No indication of how many times each add-on has been applied
- "Apply to Customer" has amount override but no preview

**Recommendations:**
- [x] Add "Applications" count column
  <!-- Completed: Added GET /v1/add_ons/application_counts backend endpoint that queries applied_add_ons table to count applications per add-on using GROUP BY on add_on_id. Added application_counts() and get_by_add_on_id() repository methods. Frontend fetches counts via addOnsApi.applicationCounts() and displays in an "Applications" table column with Users icon and correct singular/plural grammar. Clickable when count > 0 to open the application history dialog. Query invalidated on apply/delete mutations. 5 new repository tests + 3 API tests + 1 schema test added. 100% coverage maintained. -->
- [x] Add application history view
  <!-- Completed: Added GET /v1/add_ons/{code}/applications backend endpoint that fetches all applied add-ons for a given add-on code and joins customer names. New AppliedAddOnDetailResponse schema includes customer_name field. Frontend ApplicationHistoryDialog component shows a scrollable table with customer name (clickable link to customer detail page), amount, currency badge, and application date/time. Accessible via "View Applications" dropdown menu item and clickable application count in table. 4 new API tests covering: empty, with data, not found, multiple customers, overridden amounts. 100% coverage maintained. -->
- [x] Show amount preview when overriding default amount
  <!-- Completed: Enhanced ApplyAddOnDialog with a live charge preview card that appears when both customer and add-on are selected. Shows the effective charge amount in primary color. When an override amount is entered that differs from the default, shows an "overridden" badge, the new charge amount, and the default amount with strikethrough. Preview card styling changes (primary border + accent background) when override is active. No backend changes needed — pure frontend UX enhancement. -->

**Modal vs. Page Decision:**
- All MODAL - correct (add-ons are simple entities)

---

### 3.17 Taxes (`TaxesPage.tsx`)

**Current State:** Table with filters. CRUD via modals. Apply to Entity via modal.

**Issues:**
- "Apply to Entity" requires knowing entity type and ID - not discoverable
- No way to see all entities a tax applies to
- Tax rate formatting is inconsistent (should show %)

**Recommendations:**
- [x] Improve "Apply to Entity" UX: show searchable entity list instead of raw ID input
- [x] Add "Applied To" expandable section per tax
- [x] Format rate as percentage consistently
- [x] Add tax group/category concept

**Modal vs. Page Decision:**
- All MODAL - correct (taxes are simple entities)

---

### 3.18 Webhooks (`WebhooksPage.tsx`)

**Current State:** Two tabs (Endpoints, Recent Webhooks). CRUD for endpoints. Webhook detail modal.

**Issues:**
- Tab approach is good but tabs don't show counts
- No webhook event type filter
- No delivery success rate visualization
- Retry action exists but no retry history

**Recommendations:**
- [x] Add counts to tabs: "Endpoints (5)" and "Recent (142)"
  <!-- Completed: Updated WebhooksPage TabsTrigger labels to include dynamic counts from the already-fetched endpoints and webhooks arrays. Counts are hidden during loading state to avoid showing stale "(0)" values. Tab labels now show e.g. "Endpoints (5)" and "Recent Webhooks (142)". Pure frontend change — no backend modifications needed since data was already available from existing React Query hooks. All 3576 backend tests pass with 100% coverage maintained. -->
- [x] Add event type filter for recent webhooks
  <!-- Completed: Added event type filter dropdown (Select component with Filter icon) to the Recent Webhooks tab alongside the existing status filter. Dropdown groups 25 webhook event types into 7 categories (Invoice, Payment, Subscription, Customer, Credit Note, Wallet, Usage) with category headers for easy browsing. Client-side filtering combines both status and event type filters. Empty state message is context-aware of active filters ("No webhooks match your filters" vs "No webhooks found"). Frontend API client listWebhooks() method extended with webhook_type parameter (backend already supported filtering). No backend changes needed. TypeScript compiles clean, all 3576 backend tests pass with 100% coverage. -->
- [x] Add delivery success rate indicator per endpoint
  <!-- Completed: Added GET /v1/webhook_endpoints/delivery_stats backend endpoint that queries webhooks table with GROUP BY on webhook_endpoint_id, using CASE expressions to count succeeded and failed deliveries. Returns EndpointDeliveryStats per endpoint with total, succeeded, failed counts and computed success_rate percentage. Added delivery_stats_by_endpoint() repository method. Frontend WebhooksPage endpoints tab now displays a "Delivery Rate" column with a color-coded progress bar (green >= 95%, yellow >= 80%, red < 80%), percentage text, and succeeded/total count. Endpoints with no deliveries show "No deliveries" placeholder. 8 new backend tests added (3 repository + 4 API + 1 schema). 100% coverage maintained across all 3584 tests. -->
- [x] Add retry history timeline per webhook
  <!-- Completed: Added WebhookDeliveryAttempt model and migration to record each individual delivery attempt (attempt_number, http_status, response_body, success, error_message, attempted_at). WebhookService.deliver_webhook() now creates a delivery attempt record for every delivery (initial and retries) across all three code paths: success, HTTP failure, and network error. Added GET /v1/webhook_endpoints/hooks/{id}/delivery_attempts backend endpoint returning chronologically ordered attempts. Created RetryHistoryTimeline frontend component with vertical timeline visualization: color-coded status dots (green=success, red=failure), attempt labels (Initial delivery vs Retry #N), HTTP status codes, timestamps, error messages, and response bodies. Timeline is shown in the WebhookDetailDialog when a delivery has occurred. Delivery attempts query invalidated on retry mutation for live updates. New Pydantic schema: WebhookDeliveryAttemptResponse. Frontend API client extended with webhookEndpointsApi.deliveryAttempts(). OpenAPI schema and frontend types regenerated. 14 new backend tests added (7 API + 5 repository + 2 schema). 100% coverage maintained across all 3598 tests. -->

**Modal vs. Page Decision:**
- **Endpoint CRUD**: MODAL is correct (simple form)
- **Webhook detail**: MODAL is correct (read-only view)
- Consider: endpoint detail page if webhook volume is high

---

### 3.19 Dunning Campaigns (`DunningCampaignsPage.tsx`)

**Current State:** Table with filters. CRUD via modals. Thresholds as inline array in create form.

**Issues:**
- No campaign performance metrics (success rate, recovery amount)
- Threshold management is basic (just currency + amount)
- No campaign activity/execution history
- No way to see which payment requests a campaign generated

**Recommendations:**
- [x] Add performance stats: recovery rate, total recovered amount, active campaigns
  <!-- Completed: Added GET /v1/dunning_campaigns/performance_stats backend endpoint that queries payment requests linked to dunning campaigns using GROUP BY with CASE expressions for status-based counting and amount aggregation. Returns DunningCampaignPerformanceStats schema with: total_campaigns, active_campaigns, total_payment_requests, succeeded/failed/pending request counts, recovery_rate (percentage), total_recovered_amount_cents, and total_outstanding_amount_cents. Only payment requests with dunning_campaign_id are included (manual requests excluded). Frontend DunningCampaignsPage stats cards replaced with 4 performance-focused cards: Active Campaigns (with total count), Recovery Rate (color-coded: green >=70%, yellow >=40%, red <40%), Total Recovered (formatted currency), and Request Breakdown (with pending/failed counts). Stats query invalidated on create/update/delete mutations. 8 new backend tests added (5 repository + 1 schema + 2 API). 100% coverage maintained across all 3606 tests. -->
- [x] Add campaign detail page with execution history
  <!-- Completed: Added DunningCampaignDetailPage with breadcrumb nav, status badge, overview stat cards (Max Attempts, Days Between, BCC Emails, Thresholds), and Execution History tab showing payment requests table with customer links, invoice details, status badges, and attempt counts. Backend: GET /{id}/execution_history endpoint with PaymentRequest→Customer JOIN and PaymentRequestInvoice→Invoice JOIN queries. DunningCampaignsPage updated with clickable rows and View Details links. New route at /admin/dunning-campaigns/:id. -->
- [x] Show campaign timeline with attempts and outcomes
  <!-- Completed: Added Timeline tab to DunningCampaignDetailPage with vertical timeline UI showing color-coded dots (blue=created, yellow=updated, green=succeeded, red=failed, gray=pending). Backend: GET /{id}/timeline endpoint builds chronological events from campaign lifecycle (created, updated) and payment request events (created, succeeded, failed with attempt counts). Events sorted by timestamp. -->
- [x] Add "Preview" mode to simulate campaign on test data
  <!-- Completed: Added Preview tab to DunningCampaignDetailPage with "Run Preview" button. Backend: POST /{id}/preview endpoint simulates campaign execution without side effects — finds overdue finalized invoices, groups by customer+currency, checks thresholds, excludes invoices already in pending PRs. Returns CampaignPreviewResponse with total overdue stats, groups with invoice details, and existing pending request count. Frontend shows stats cards and expandable customer groups with invoice tables. 32 new tests (18 API + 14 repository). 100% coverage maintained across 3641 tests. -->

**Modal vs. Page Decision:**
- **Create/Edit**: MODAL is acceptable (form is moderate complexity)
- Consider: **Detail page** for campaign execution history and analytics

---

### 3.20 Usage Alerts (`UsageAlertsPage.tsx`)

**Current State:** Table. CRUD via modals. Filter by subscription.

**Issues:**
- No alert history (when was each alert triggered?)
- No visual threshold indicator
- No way to see current usage vs threshold
- Minimal information in table rows

**Recommendations:**
- [x] Add progress bar showing current usage as percentage of threshold
- [x] Add alert trigger history (dates, values at trigger time)
- [x] Add "Test Alert" action to simulate threshold breach
- [x] Improve table: show subscription name, metric name, progress percentage

> **Implementation Notes:** Added 3 new backend endpoints (`GET /{id}/status`, `GET /{id}/triggers`, `POST /{id}/test`), a `UsageAlertTrigger` model for trigger history tracking, and updated the frontend table with progress bars (color-coded: green/yellow/red), subscription external_id display, metric name + code, trigger history dialog, and test alert dialog. All 3662 backend tests pass at 100% coverage.

**Modal vs. Page Decision:**
- All MODAL - correct (alerts are simple entities)

---

### 3.21 Payment Requests (`PaymentRequestsPage.tsx`)

**Current State:** Table with filters. Create via modal (customer → invoice selection). Detail modal.

**Issues:**
- Create form requires checking individual invoices - no "select all overdue" option
- No batch payment request creation
- Detail modal shows invoice list but no payment attempt history
- Relationship to dunning campaigns is shown but not actionable

**Recommendations:**
- [x] Add "Select all overdue invoices" checkbox in create form
- [x] Add batch creation: "Create requests for all customers with overdue invoices"
- [x] Show payment attempt history in detail modal
- [x] Consider merging into Payments page as a tab

**Modal vs. Page Decision:**
- **Create**: MODAL is correct (selection-based form)
- **Detail**: MODAL is correct (read-only view)

---

### 3.22 Data Exports (`DataExportsPage.tsx`)

**Current State:** Table. Create via modal. Auto-refresh for in-progress exports. Download for completed.

**Issues:**
- Export type is a raw string select - no description of what each export contains
- Filter JSON input is unfriendly
- No scheduled/recurring exports
- No export preview

**Recommendations:**
- [x] Add descriptions for each export type — Added `EXPORT_TYPE_DESCRIPTIONS` map to `DataExportsPage.tsx` with per-type summaries of exported columns and available filters. Descriptions appear in the Select dropdown items and as helper text below the selector.
- [x] Replace JSON filter input with structured form (date range, status, customer, etc.) — Replaced raw JSON textarea with a dynamic structured filter form in `NewExportDialog`. Each export type now shows its relevant filter fields: status dropdowns (with correct enum values for invoices, subscriptions, credit notes), customer selector (loaded from API), fee type selector, and text inputs for external customer ID, billable metric code, and invoice ID. Filter fields are defined in `EXPORT_TYPE_FILTERS` config and reset when switching export types. Types with no filters (customers) show a "No filters available" message.
- [x] Add export size estimate before creation — Added `POST /v1/data_exports/estimate` endpoint that returns `record_count` for a given export type and filters without creating an export. Backend uses efficient SQL `COUNT()` queries. Frontend `NewExportDialog` now shows an "Estimated records" display that auto-updates as export type and filters change via React Query.
- [x] Show progress percentage for in-progress exports — Added `progress` column (Integer, 0–100) to the `DataExport` model, schema, and a new Alembic migration. The service now tracks row-level progress during CSV generation via `_update_progress()`, setting progress from 0 to 100 as rows are written. Frontend `StatusBadge` shows the percentage alongside a `<Progress>` bar for processing exports, and the `ViewDetailsDialog` displays a dedicated progress row.

**Modal vs. Page Decision:**
- All MODAL - correct (exports are simple operations)

---

### 3.23 Integrations (`IntegrationsPage.tsx`)

**Current State:** Grid of cards. CRUD via modals. Test Connection action.

**Issues:**
- Settings is raw JSON - no structured form per provider
- No sync history
- No integration mapping management on this page
- Test connection gives only success/fail - no diagnostics

**Recommendations:**
- [x] **Integration detail page** (`/admin/integrations/:id`). Each integration needs: settings, customer mappings, field mappings, sync history, error log. — Created `IntegrationDetailPage.tsx` with 5 tabs (Settings, Customer Mappings, Field Mappings, Sync History, Error Log). Added `IntegrationSyncHistory` model with migration, repository, schema, and 3 new sub-resource API endpoints (`GET .../customers`, `GET .../mappings`, `GET .../sync_history`). Integration cards on list page now link to detail page.
- [x] Provider-specific settings forms instead of raw JSON — Added `PROVIDER_SETTINGS_FIELDS` config for all 9 providers (Stripe, GoCardless, Adyen, Netsuite, Xero, HubSpot, Salesforce, Anrok, Avalara) with typed form fields, password masking with show/hide toggle, and status selector. Unknown providers fall back to JSON editor.
- [x] Sync history with filtering — Sync history tab shows a table of all sync operations with status and resource_type dropdown filters. Backend supports `?status=` and `?resource_type=` query parameters.
- [x] Customer mapping table on detail page — Customer Mappings tab displays a table of all `IntegrationCustomer` records with customer ID, external customer ID, settings, and creation date.
- [x] Real-time sync status indicator — `SyncStatusIndicator` component shows connection state with animated pulse dot (green/red/gray), last sync timestamp, and integration status badge.

**Modal vs. Page Decision:**
- **Create**: MODAL for initial setup (type + provider selection)
- **Configuration/Mapping**: Should be a **FULL PAGE** (complex per-provider settings)
- **Delete**: MODAL is correct

---

### 3.24 Audit Logs (`AuditLogsPage.tsx`)

**Current State:** Filterable table with expandable rows showing old→new value diffs.

**Issues:**
- No date range filter
- No export capability
- Resource ID search is the only text search (should search descriptions too)
- No way to navigate to the changed resource

**Recommendations:**
- [x] Add date range filter (essential for audit logs) — Added `start_date` and `end_date` query parameters to `GET /v1/audit_logs/` endpoint with repository-level filtering on `created_at`. Frontend `AuditLogsPage` now has a date preset selector (All time, 24h, 7d, 30d, 90d, Custom) with a dual-month calendar popover for custom ranges, following the same pattern as the Dashboard date picker.
- [x] Add "View Resource" link to navigate to the changed entity — Added a `RESOURCE_TYPE_ROUTES` mapping (customer, invoice, subscription, plan, wallet, credit_note, dunning_campaign, integration) and a `getResourceUrl()` helper. Each audit log row now shows an ExternalLink icon next to the resource ID that navigates to the entity's detail page. The expanded row details also include a "View {resource_type}" link at the bottom. Resources without detail pages (e.g., payment) gracefully omit the link.
- [x] Add export to CSV functionality — Added `AUDIT_LOGS` to the `ExportType` enum and implemented `_generate_csv_audit_logs` / `_count_audit_logs` in `DataExportService` with `resource_type` and `action` filters. Frontend: added "Export to CSV" button on `AuditLogsPage` that creates an audit log export with current filters and navigates to Data Exports; added `audit_logs` to `DataExportsPage` type list with filter configs. All 3765 tests pass at 100% coverage.
- [x] Add actor filter (by user/system) — Added `actor_type` query parameter to `GET /v1/audit_logs/` endpoint with repository-level filtering. Frontend `AuditLogsPage` now has an "Actor type" dropdown (All actors, System, API Key, Webhook). The filter is also integrated into CSV exports and export count estimation via `DataExportService`. All 3775 tests pass at 100% coverage.
- [x] Improve diff visualization (syntax highlighted JSON diff) — Created a shared `JsonDiffDisplay` component (`frontend/src/components/JsonDiffDisplay.tsx`) with two exports: `ChangesDisplay` (full diff view for AuditLogsPage) and `ChangesSummary` (compact view for AuditTrailTimeline). Scalar values retain the inline red/green old→new format. Complex values (objects/arrays) now render in side-by-side syntax-highlighted JSON blocks with color-coded tokens: keys (sky), strings (amber), numbers (violet), booleans (orange), null (gray italic). Dark mode fully supported. Both AuditLogsPage and AuditTrailTimeline updated to use the shared component. All 3775 tests pass at 100% coverage.

**Modal vs. Page Decision:**
- All inline (expandable rows) - correct

---

### 3.25 Settings (`SettingsPage.tsx`)

**Current State:** Single form page with 4 card sections (General, Billing, Branding, Legal Address).

**Issues:**
- All sections save with one button - user can't save partial changes
- Form initialization pattern (`!initialized` flag) is fragile
- No validation feedback until save
- HMAC key shown as plain text (security concern)
- No branding preview

**Recommendations:**
- [x] Add per-section save buttons (or auto-save with debounce) — Each card section (General, Billing, Branding, Legal Address) now has its own independent Save button with loading state indicator. Sections are disabled while another section is saving.
- [x] Add real-time validation as user types — Validation runs on touched fields in real-time: required fields (name, currency, timezone), non-negative numbers (grace period, payment term), valid URL (logo), valid email. Errors shown inline below fields with `aria-invalid` for accessibility.
- [x] Mask HMAC key with show/hide toggle — HMAC key input now uses `type="password"` by default with an Eye/EyeOff toggle button to reveal/hide the value.
- [x] Add branding preview panel (show how invoice email would look) — Branding section now has a live preview panel showing organization logo (with fallback initial), name, email, sample invoice line with currency, and net payment term. Updates in real-time as fields change.
- [x] Add timezone and currency searchable selects (not plain dropdowns) — Both timezone and currency now use searchable Popover+Command comboboxes. Currency expanded from 3 to 20 options. Timezone uses full IANA timezone list via `Intl.supportedValuesOf`.

**Modal vs. Page Decision:**
- Full page is correct for Settings

---

### 3.26 API Keys (`ApiKeysPage.tsx`)

**Current State:** Table. Create via modal (name + expiration). One-time key display with copy. Revoke action.

**Issues:**
- No key rotation feature
- No usage analytics per key
- No scope/permission model
- Key prefix display is helpful but could be more prominent

**Recommendations:**
- [x] Add "Rotate Key" action (revoke old, create new with same config)
- [x] Add last-used timestamp display (already in model) — was already implemented in the table
- [x] Add key creation date display — added "Created" column showing `created_at` formatted as `MMM d, yyyy`
- [x] Add expiration warning indicators — amber AlertTriangle for keys expiring within 30 days, red "Expired" label for already-expired keys

**Modal vs. Page Decision:**
- All MODAL - correct (API keys are simple entities)

---

## 4. Modal vs. Page Decision Framework

### When to Use a Modal (Dialog)
Use modals when ALL of these are true:
- Form has **< 8 fields**
- No nested/related entities need to be managed
- Operation is **contextual** (user should stay on current page)
- No need for scrolling within the form
- Single-step operation

**Examples (correct as modal):** Create Customer, Create Metric, Create Feature, Create API Key, Delete confirmation, Apply Coupon, Top Up Wallet

### When to Use a Full Page
Use a dedicated page when ANY of these are true:
- Entity has **sub-entities** that need their own CRUD (charges, thresholds, etc.)
- Form has **> 10 fields** or multiple sections
- Entity has **rich detail** worth exploring (transaction history, audit trail, charts)
- Users will **spend significant time** on this entity
- Content needs **horizontal space** (tables, charts, timelines)

**Changes needed (modal → page):**
| Entity | Currently | Should Be | Reason |
|--------|-----------|-----------|--------|
| Plan Detail | Grid card + modal | Detail page | Charges, commitments, thresholds, entitlements |
| Invoice Detail | Modal | Detail page | Fees, taxes, settlements, credit notes, audit |
| Wallet Detail | Modal | Detail page | Transaction history, balance charts |
| Billing Entity Create/Edit | Modal | Full page form | 15+ fields, address block |
| Credit Note Create | Modal | Full page form | Multi-step cascade form |
| Integration Detail | Card + modal | Detail page | Settings, mappings, sync history |

### When to Use a Slide-Out Panel
Use panels when:
- Content is supplementary (user needs to see the main content alongside)
- Quick preview without losing context
- Side-by-side comparison needed

**New patterns to introduce:**
- Fee Estimator (Events page) → slide-out panel
- Quick customer preview (from any customer reference) → slide-out panel
- Invoice preview → slide-out panel

---

## 5. Broken Edit Modes & Missing CRUD

### Completely Broken / Stub
1. **InvoicesPage - "Finalize Invoice"**: Button exists but has no mutation handler. Clicking does nothing.

### Missing Edit Capabilities
2. **CustomerDetailPage**: No edit button. Customer info is read-only on detail page. Must go back to list page to edit.
3. **SubscriptionDetailPage**: Cannot edit subscription fields (external_id, billing_time, pay_in_advance). Only "Change Plan" and "Terminate" are available.
4. **InvoicesPage**: No edit for draft invoices (should be able to modify line items before finalizing).
5. **PaymentMethodsPage**: Cannot edit payment method details (card info updates).
6. **FeaturesPage**: Cannot edit feature type (intentional? should at least explain why in UI).

### Missing Create Capabilities
7. **FeesPage**: No "Create Fee" action. Fees can only be system-generated.
8. **PaymentsPage**: No "Record Manual Payment" action.
9. **InvoicesPage**: No "Create One-Off Invoice" action.

### Missing Delete Capabilities
10. **FeesPage**: Cannot delete individual fees.
11. **DataExportsPage**: Cannot delete export records.

### Missing View/Detail Capabilities
12. **SubscriptionsPage (list)**: No detail modal on list page - must click to navigate (fine, but should have quick preview option).
13. **DunningCampaignsPage**: No execution history or results view.

---

## 6. Customer Portal Redesign

### Current State
The portal is a minimal read-only experience with 5 pages: Dashboard, Invoices, Usage, Payments, Wallet.

### Issues
- **Extremely bare-bones**: No branding, no customization, no personality
- **No self-service actions**: Customer can't update their info, can't manage payment methods, can't upgrade/downgrade
- **Wallet page is 4 cards with numbers**: No transaction history visible
- **Usage page requires subscription selection**: Confusing if customer has one subscription
- **No mobile optimization**: Horizontal nav doesn't work well on mobile

### Recommendations

**Branding & Identity:**
- [x] Add organization logo (from Settings) to portal header
- [x] Add customizable portal accent color
- [x] Add organization name in header
- [x] Support custom welcome message
<!-- Implemented: Added `portal_accent_color` and `portal_welcome_message` fields to Organization model/schema, new `GET /portal/branding` endpoint, updated PortalLayout with logo + org name in header, accent color tinting, PortalBrandingContext, custom welcome message on dashboard, and new branding fields in Settings page. -->

**Self-Service Actions:**
- [x] Allow customer to update their profile (name, email, timezone)
<!-- Implemented: Added PortalProfileUpdate schema, PATCH /portal/profile endpoint, PortalProfilePage.tsx with editable name/email/timezone fields, SearchableSelect for timezone, Profile nav link in portal layout, 11 new backend tests. -->
- [x] Allow customer to manage payment methods (add/remove/set default)
<!-- Implemented: Added 4 portal endpoints (GET/POST/DELETE /portal/payment_methods, POST /portal/payment_methods/{id}/set_default) with customer-scoped auth. Created PortalPaymentMethodsPage.tsx with card brand icons, default management, add/remove dialogs. Added portal nav link and route. 20 new backend tests, all 3816 tests pass at 100% coverage. -->
- [x] Allow customer to view and upgrade/downgrade subscription
<!-- Implemented: Added 5 portal endpoints (GET /portal/subscriptions, GET /portal/subscriptions/{id}, GET /portal/plans, POST /portal/subscriptions/{id}/change_plan_preview, POST /portal/subscriptions/{id}/change_plan) with customer-scoped auth. Created PortalSubscriptionsPage.tsx with subscription list, plan change dialog with upgrade/downgrade badges, proration preview with credit/charge breakdown, and confirmation flow. Added Subscriptions nav link to portal layout. New PortalSubscriptionResponse, PortalPlanResponse, PortalChangePlanRequest schemas. 24 new backend tests, all 3840 tests pass at 100% coverage. -->
- [x] Allow customer to purchase add-ons
<!-- Implemented: Added 3 portal endpoints (GET /portal/add_ons, GET /portal/add_ons/purchased, POST /portal/add_ons/{id}/purchase) with customer-scoped auth. GET /portal/add_ons lists available add-ons for the organization. GET /portal/add_ons/purchased lists add-ons the customer has already purchased with add-on name/code. POST /portal/add_ons/{id}/purchase uses AddOnService to create AppliedAddOn + one-off Invoice + Fee. Created PortalAddOnsPage.tsx with tabbed layout (Available/Purchased), add-on cards with price and description, purchase confirmation dialog, and purchased history with dates. Added Add-ons nav link (Package icon) to portal layout. New PortalAddOnResponse, PortalPurchasedAddOnResponse, PortalPurchaseAddOnResponse schemas. 13 new backend tests added. All 3853 tests pass at 100% coverage. -->
- [x] Allow customer to apply coupon codes
<!-- Implemented: Added 2 portal endpoints (GET /portal/coupons, POST /portal/coupons/redeem) with customer-scoped JWT auth. GET /portal/coupons lists active applied coupons for the customer with coupon name/code/type/discount details. POST /portal/coupons/redeem accepts a coupon_code, validates via CouponApplicationService (active status, expiration, reusability), and creates an AppliedCoupon. Error handling: 404 for not found, 400 for inactive/expired/already-applied. Created PortalCouponsPage.tsx with coupon code input form, active coupons list showing discount amounts (fixed/percentage), frequency info, and application dates. Added Coupons nav link (Tag icon) to portal layout and route in App.tsx. New PortalRedeemCouponRequest, PortalAppliedCouponResponse schemas. Frontend API client extended with portalApi.listCoupons() and portalApi.redeemCoupon(). OpenAPI schema and frontend types regenerated. 11 new backend tests added covering: empty list, list with applied, excludes other customer, redeem fixed, redeem percentage, appears in list, not found, terminated, expired, non-reusable twice, and invalid token. All 3864 tests pass at 100% coverage. -->

**Dashboard Enhancements:**
- [x] Show next billing date prominently
- [x] Show upcoming charges estimate
- [x] Show usage progress vs. plan limits
- [x] Add quick action cards: "Pay Invoice", "Top Up Wallet", "View Usage"
<!-- Completed: Added GET /portal/dashboard_summary backend endpoint that aggregates four data sections for the portal dashboard. (1) Next Billing: calculates next billing date for each active/pending subscription using plan interval and period anchor, returning days_until_next_billing, plan name, and amount. (2) Upcoming Charges: estimates upcoming charges per subscription by combining base plan amount with current usage (via UsageQueryService), with graceful fallback to 0 on failure. (3) Usage Progress: queries plan entitlements (boolean/quantity/custom features) and compares quantity features against current usage to compute percentage progress bars. Deduplicates features across multiple subscriptions. (4) Quick Actions: aggregates outstanding invoice count/amount, wallet balance, and active subscription status. Frontend PortalDashboardPage enhanced with: NextBillingCard (clock icon, days counter, plan name, billing date), UpcomingChargeCard (base + usage breakdown), UsageProgressCard (color-coded progress bar: green/yellow/red at 70/90% thresholds, boolean toggle badges, quantity X/Y display), and QuickActionCard (icon + title + description + arrow, linking to invoices/wallet/usage pages with token param). New Pydantic schemas: PortalDashboardSummaryResponse, PortalNextBillingInfo, PortalUpcomingCharge, PortalUsageProgress, PortalQuickActions. Frontend API client extended with portalApi.getDashboardSummary() and 6 new TypeScript types. 16 new backend tests added covering: empty dashboard, active/pending subscription billing, usage charges with mock, usage failure fallback, boolean/quantity feature progress, outstanding invoices, wallet balance, active subscription flag, invalid token, customer not found, terminated subscription exclusion, duplicate feature deduplication, zero-limit quantity skip, and usage query failure for quantities. All 3880 backend tests pass with 100% coverage. -->

**Wallet Page:**
- [x] Add transaction history table
- [x] Add balance chart
- [x] Allow customer to request top-up
<!-- Completed: Added 3 new portal wallet endpoints. (1) GET /portal/wallet/{wallet_id}/transactions returns paginated transaction history for a customer's wallet with ownership validation. (2) GET /portal/wallet/{wallet_id}/balance_timeline returns daily aggregated balance timeline data with running balance computation for charts. (3) POST /portal/wallet/{wallet_id}/top_up allows customers to self-service add credits to their active wallet. New Pydantic schemas: PortalTopUpRequest (credits field with gt=0 validation), PortalTopUpResponse (wallet_id, credits_added, new_balance_cents, new_credits_balance). Frontend PortalWalletPage redesigned with: wallet list support (uses first wallet), Top Up button in header for active wallets, Tabs layout (Transactions tab + Balance Chart tab). Transaction History table with 7 columns: Type (color-coded badge), Credits (+/- with green/red), Amount (+/- formatted), Running Balance (computed client-side), Source, Status (badge), Date. Balance Chart tab with two recharts visualizations: AreaChart for "Balance Over Time" with gradient fill, and BarChart for "Credits In/Out" with green/red bars and legend. Top Up Dialog with credits input, estimated cost preview (credits × rate), loading state, and validation. Frontend API client extended with portalApi.getWallets(), getWalletTransactions(), getWalletBalanceTimeline(), topUpWallet(). OpenAPI schema and frontend types regenerated. 21 new backend tests added covering: transaction list, empty transactions, wallet not found, cross-customer isolation, expired token, timeline with data, empty timeline, timeline not found, cross-customer timeline, running balance computation, top-up success, top-up not found, cross-customer top-up, terminated wallet, invalid credits, expired token, top-up creates transaction, service ValueError handling, and 3 schema validation tests. All 3901 backend tests pass with 100% coverage. -->

**Usage Page:**
- [x] Auto-select subscription if customer has only one
- [x] Add usage trend chart
- [x] Show plan limits vs. current usage (progress bars)
- [x] Show projected end-of-period usage
<!-- Completed: Redesigned PortalUsagePage with 4 enhancements. (1) Auto-select: Switched from invoice-derived subscription IDs to portalApi.listSubscriptions() for proper subscription listing with plan names. When customer has exactly one active/pending subscription, it's auto-selected and the dropdown is hidden, replaced by an inline subscription info badge. (2) Usage Trend Chart: Added GET /portal/usage/trend backend endpoint that queries DailyUsageRepository for aggregated daily usage across all metrics, with optional date range. Frontend renders a recharts AreaChart with gradient fill, grid lines, and formatted tooltip showing daily usage values. (3) Plan Limits Progress Bars: Added GET /portal/usage/limits backend endpoint that queries plan entitlements, resolves features, and computes current usage vs limits for quantity features (with percentage), boolean features (enabled/disabled badge), and custom features. Frontend renders color-coded Progress bars (green/yellow at 70%/red at 90%) with X/Y usage counters. (4) Projected Usage: Added GET /portal/usage/projected backend endpoint that gets current billing period usage, computes projection factor (total_days / days_elapsed), and extrapolates per-charge projected units and amounts. Frontend renders a primary-tinted card with current vs projected totals, period progress bar, and a per-metric breakdown table. New Pydantic schemas: PortalUsageTrendPoint, PortalUsageTrendResponse, PortalUsageLimitItem, PortalUsageLimitsResponse, PortalProjectedUsageItem, PortalProjectedUsageResponse. Frontend API client extended with getUsageTrend(), getUsageLimits(), getProjectedUsage(). OpenAPI schema and frontend types regenerated. 25 new backend tests added covering: trend empty/with data/custom dates/404/cross-customer/expired, limits empty/quantity/boolean/custom/usage failure/invalid value/zero limit/404/cross-customer, projected success/no charges/404/cross-customer/query failure/expired/plan not found, plus 3 schema tests. All 3926 backend tests pass with 100% coverage. -->

**Invoice Page:**
- [x] Add inline PDF viewer
  <!-- Completed: Added GET /portal/invoices/{invoice_id}/pdf_preview backend endpoint that generates a PDF with Content-Disposition: inline for in-browser viewing. Frontend PortalInvoicesPage now has an Eye icon button (per row and in detail dialog) that fetches the PDF blob, creates an Object URL, and displays it in a Dialog with an iframe (800px wide, 85vh tall). Preview only available for finalized/paid invoices. Frontend API client extended with portalApi.previewInvoicePdf(). 5 new backend tests added covering: preview success (verifies inline disposition), invoice not found, draft returns 400, cross-customer isolation, and expired token. 100% coverage maintained. -->
- [x] Add "Pay Now" button for outstanding invoices
  <!-- Completed: Added POST /portal/invoices/{invoice_id}/pay backend endpoint that creates a checkout session for finalized invoices. Uses Stripe payment provider to generate a checkout URL. Returns existing pending payment's checkout URL if one already exists (avoids duplicate payments). New PortalPayNowRequest (success_url, cancel_url) and PortalPayNowResponse (payment_id, checkout_url, provider, invoice_id, amount, currency) Pydantic schemas. Frontend adds CreditCard icon button in table rows and a prominent "Pay Now" button in the invoice detail dialog — both visible only for finalized invoices. Clicking opens the checkout URL in a new tab. Frontend API client extended with portalApi.payInvoice(). OpenAPI schema and frontend types regenerated. 10 new backend tests added covering: successful payment, not found, draft returns 400, paid returns 400, cross-customer isolation, existing pending reuse, pending without URL creates new, ImportError (503), generic error (500), and expired token. 2 schema tests added. 100% coverage maintained. -->
- [x] Add payment history per invoice
  <!-- Completed: Added GET /portal/invoices/{invoice_id}/payments backend endpoint that returns all payments for a specific invoice belonging to the authenticated customer. Validates invoice ownership before querying payments. Frontend invoice detail dialog now includes a "Payment History" section (below the action buttons, separated by a Separator) showing each payment as a card with status icon (CheckCircle/XCircle/Clock/Loader2/AlertCircle), color-coded by status (green=succeeded, red=failed, muted=other), amount, timestamp, provider, and status badge. Frontend API client extended with portalApi.getInvoicePayments(). 6 new backend tests added covering: list payments, empty list, not found, cross-customer isolation, expired token, and multiple payments. 100% coverage maintained across all 3949 tests. -->

---

## 7. Implementation Priority

### Phase 1: Fix Critical Issues (High Impact, Low Effort)
- [x] Fix Finalize Invoice mutation (broken functionality)
- [x] Add Edit button to CustomerDetailPage
- [x] Add pagination to all table views
- [x] Add global header with breadcrumbs
- [x] Add Cmd+K command palette for global search

### Phase 2: Modal → Page Conversions (High Impact, Medium Effort)
- [x] Create Plan detail page (`/admin/plans/:id`)
  <!-- Already completed in section 3.5 — PlanDetailPage.tsx exists with charges, commitments, thresholds, entitlements, subscriptions, and activity tabs. Route at /admin/plans/:id in App.tsx. -->
- [x] Create Invoice detail page (`/admin/invoices/:id`)
  <!-- Already completed in section 3.9 — InvoiceDetailPage.tsx exists with fees, totals, settlements, credit notes, and activity tabs. Route at /admin/invoices/:id in App.tsx. -->
- [x] Create Wallet detail page (`/admin/wallets/:id`)
  <!-- Already completed in section 3.14 — WalletDetailPage.tsx exists with transactions, balance timeline, and activity tabs. Route at /admin/wallets/:id in App.tsx. -->
- [x] Convert Billing Entity form to full page
  <!-- Already completed in section 3.3 — BillingEntityFormPage.tsx exists with 4-section card layout. Routes at /admin/billing-entities/new and /admin/billing-entities/:code/edit in App.tsx. -->
- [x] Convert Credit Note creation to full page
  <!-- Already completed in section 3.12 — CreditNoteFormPage.tsx exists with cascading customer→invoice→fees form. Routes at /admin/credit-notes/new and /admin/credit-notes/:id/edit in App.tsx. -->

### Phase 3: Missing CRUD Operations (Medium Impact, Low Effort)
- [x] Add subscription field editing
  <!-- Already completed in section 3.7 — EditSubscriptionDialog component exists at src/components/EditSubscriptionDialog.tsx, integrated into both SubscriptionDetailPage and SubscriptionsPage. Supports editing billing_time, pay_in_advance, on_termination_action, and trial_period_days. -->
- [x] Add "Record Manual Payment" action
  <!-- Completed: Added POST /v1/payments/record backend endpoint that accepts invoice_id, amount, currency, optional reference (e.g. check number, wire transfer ID), and optional notes. Validates invoice exists and is finalized, creates a payment record with provider=manual and status=succeeded, records an invoice settlement, auto-marks invoice as paid if fully settled, creates an audit log entry, and sends a payment.succeeded webhook. Added ManualPaymentCreate Pydantic schema. Frontend PaymentsPage now has a "Record Payment" button in the header that opens a dialog with invoice selector (filtered to finalized invoices), amount/currency inputs (auto-filled from selected invoice), reference, and notes fields. Frontend API client extended with paymentsApi.recordManual(). OpenAPI schema and frontend types regenerated. 10 new backend tests added covering: success with all fields, minimal fields, invoice not found, draft invoice (400), zero amount (422), negative amount (422), audit log creation, invoice auto-paid on full settlement, and 2 schema validation tests. All 3976 backend tests pass with 100% coverage. -->
- [x] Add "Create One-Off Invoice" action
  <!-- Already completed in section 3.9 — OneOffInvoiceDialog component exists on InvoicesPage with backend POST /v1/invoices/one_off endpoint. -->
- [x] Add "Remove Applied Coupon" action
  <!-- Already completed in section 3.15 — DELETE /v1/coupons/applied/{applied_coupon_id} endpoint and Remove button in AppliedCouponsDialog already exist. -->
- [x] Standardize row actions (dropdown menus instead of icon-only buttons)
  <!-- Completed: Converted 6 admin pages from inline icon-only/label-only action buttons to standardized DropdownMenu (MoreHorizontal trigger) pattern matching the existing PaymentsPage, CreditNotesPage, WalletsPage, and CouponsPage implementations. Pages converted: BillingEntitiesPage (Edit/Delete label buttons → dropdown), MetricsPage (Edit/Delete label buttons → dropdown), FeaturesPage (Pencil/Trash2 icon-only buttons → dropdown with labels), SubscriptionsPage (6 conditional icon-only buttons → organized dropdown with Edit, Change Plan, Usage Thresholds, Pause/Resume, Terminate sections), EventsPage (single Reprocess icon → dropdown for consistency), PaymentMethodsPage (Star/Trash2 icon-only buttons → dropdown with Set as Default/Delete). All dropdowns use consistent pattern: MoreHorizontal trigger icon, right-aligned content, labeled items with icons, destructive variant for delete/terminate actions, separators between action groups. TypeScript compiles clean, all 3976 backend tests pass with 100% coverage. -->

### Phase 4: UX Enrichment (Medium Impact, Medium Effort)
- [x] Dashboard: date range selector, trend indicators, clickable stat cards
  <!-- Already completed in section 3.1 — PeriodSelector (date range with 5 presets + custom), TrendBadge (percentage change with directional icons), clickable StatCard (with href/Link navigation), sparkline mini-charts, revenue breakdown donut chart, recent invoices/subscriptions quick-glance tables, and activity feed filtering all implemented and verified. -->
- [x] Customer health indicators
  <!-- Already completed in section 3.2 — GET /v1/customers/{customer_id}/health backend endpoint with good/warning/critical health status logic, CustomerHealthBadge frontend component with color-coded circle and tooltip, integrated into both CustomerDetailPage (header) and CustomersPage (table rows). Full test coverage exists. -->
- [x] Table column sorting — Added `SortableTableHead` component with `useSortState` hook, `apply_order_by` backend utility, sorting support across all 36 repositories, 24 routers, 22 API methods, and 20 admin pages
- [x] Bulk actions for invoices and subscriptions
  <!-- Completed: Added row checkbox selection and floating bulk action bars to both InvoicesPage and SubscriptionsPage. InvoicesPage: expanded checkbox selection from draft-only to draft+finalized invoices, added bulk void mutation (POST /v1/invoices/bulk_void) with per-invoice audit logging and webhooks, floating action bar shows context-aware buttons (Finalize for drafts, Void for draft/finalized, Clear). SubscriptionsPage: added new checkbox column for active/pending/paused subscriptions, floating action bar with Pause (active), Resume (paused), Terminate (all actionable) buttons. Backend: 4 new endpoints (POST /v1/invoices/bulk_void, POST /v1/subscriptions/bulk_pause, POST /v1/subscriptions/bulk_resume, POST /v1/subscriptions/bulk_terminate) with BulkVoidRequest/Response/Result and BulkSubscriptionRequest/BulkTerminateRequest/BulkSubscriptionResponse schemas. 19 new backend tests added. OpenAPI schema and frontend types regenerated. All 4039 backend tests pass with 100% coverage. -->
- [x] Integration detail pages
  <!-- Already completed in section 3.23 — IntegrationDetailPage.tsx exists at /admin/integrations/:id with 5 tabs (Settings, Customer Mappings, Field Mappings, Sync History, Error Log), provider-specific settings forms for all 9 providers, SyncStatusIndicator component, IntegrationSyncHistory model with migration, and 3 sub-resource API endpoints. Full test coverage maintained. -->

### Phase 5: Portal Enhancement (Medium Impact, High Effort)
- [x] Portal branding customization
  <!-- Already completed in section 6 (Customer Portal Redesign, "Branding & Identity") — portal_accent_color and portal_welcome_message fields on Organization model, GET /portal/branding endpoint, PortalBrandingContext in PortalLayout, admin Settings page UI for accent color and welcome message, and comprehensive backend tests all exist. -->
- [x] Customer self-service actions
  <!-- Already completed in section 6 (Customer Portal Redesign, "Self-Service Actions") — all 5 self-service features fully implemented: (1) Profile update (PATCH /portal/profile, PortalProfilePage.tsx), (2) Payment methods management (4 endpoints: GET/POST/DELETE /portal/payment_methods, POST set_default, PortalPaymentMethodsPage.tsx), (3) Subscription upgrade/downgrade (5 endpoints including change_plan_preview and change_plan, PortalSubscriptionsPage.tsx), (4) Add-on purchasing (3 endpoints: list/purchased/purchase, PortalAddOnsPage.tsx), (5) Coupon redemption (GET /portal/coupons, POST /portal/coupons/redeem, PortalCouponsPage.tsx). All with proper portal JWT auth, frontend components, API client methods, and backend test coverage. -->
- [x] Portal payment method management
  <!-- Already completed in section 6 — 4 portal endpoints (GET/POST/DELETE /portal/payment_methods, POST /portal/payment_methods/{id}/set_default), PortalPaymentMethodsPage.tsx with full CRUD, CardBrandIcon integration, and 20 backend tests. All verified present. -->
- [x] Portal subscription management
  <!-- Already completed in section 6 — 5 portal endpoints (GET /portal/subscriptions, GET /portal/subscriptions/{id}, GET /portal/plans, POST change_plan_preview, POST change_plan), PortalSubscriptionsPage.tsx with plan change dialog and proration preview, and 24 backend tests. All verified present. -->
- [x] Mobile-first portal redesign
  <!-- Completed: Comprehensive mobile-first redesign across 11 portal files. PortalLayout: replaced hamburger drawer with native mobile bottom tab bar (4 primary nav items + "More" overflow sheet with 3-column grid for remaining 6 items), removed desktop-only customer name display on mobile, added truncation for long branding names. All 10 portal pages: responsive typography (text-2xl/text-3xl headings, text-sm/text-base subtitles), tighter spacing (space-y-4/space-y-6), 2-column stat card grids on mobile. Table-heavy pages (Invoices, Payments, Wallet transactions): added card-based mobile views using useIsMobile() hook — tappable invoice cards, payment cards, and transaction cards replace multi-column tables on small screens. Touch targets: min-h-[44px] on all interactive buttons and action items per Apple HIG. Layout: flex-col stacking for subscription cards and payment method cards on mobile, flex-wrap for action button groups. No backend changes needed — pure frontend responsive redesign. TypeScript compiles clean, all 4039 backend tests pass with 100% coverage. -->

### Phase 6: Advanced Features (Lower Priority)
- [x] Restructure sidebar navigation
  <!-- Completed: Reorganized sidebar from 5 flat groups (30 items) into 6 clearer groups per section 2.1 recommendations. New structure: Overview (Dashboard), Customers (Customers, Subscriptions, Wallets, Payment Methods), Catalog (Plans, Billable Metrics, Features, Add-ons, Coupons), Billing (Invoices, Payments, Fees, Credit Notes, Taxes), Operations (Events, Webhooks, Dunning, Usage Alerts, Integrations). Moved Billing Entities, API Keys, Data Exports, Audit Logs, and Payment Requests into an expandable Settings section at the bottom of the sidebar. Settings section auto-expands when a settings route is active, shows a collapsible chevron toggle, and falls back to a dropdown menu when sidebar is collapsed. Dark mode toggle moved into the Settings section. Removed unused useNavigate import. All group labels now shown (including "Overview" for first group). All 4039 backend tests pass with 100% coverage. -->
- [ ] Add notification system
- [ ] Add activity feed improvements
- [ ] Add charge model visualizer for plans
- [ ] Add revenue analytics deep-dive page
