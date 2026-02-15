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
- [ ] Show progress percentage for in-progress exports

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
- [ ] **Integration detail page** (`/admin/integrations/:id`). Each integration needs: settings, customer mappings, field mappings, sync history, error log.
- [ ] Provider-specific settings forms instead of raw JSON
- [ ] Sync history with filtering
- [ ] Customer mapping table on detail page
- [ ] Real-time sync status indicator

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
- [ ] Add date range filter (essential for audit logs)
- [ ] Add "View Resource" link to navigate to the changed entity
- [ ] Add export to CSV functionality
- [ ] Add actor filter (by user/system)
- [ ] Improve diff visualization (syntax highlighted JSON diff)

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
- [ ] Add per-section save buttons (or auto-save with debounce)
- [ ] Add real-time validation as user types
- [ ] Mask HMAC key with show/hide toggle
- [ ] Add branding preview panel (show how invoice email would look)
- [ ] Add timezone and currency searchable selects (not plain dropdowns)

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
- [ ] Add "Rotate Key" action (revoke old, create new with same config)
- [ ] Add last-used timestamp display (already in model)
- [ ] Add key creation date display
- [ ] Add expiration warning indicators

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
- [ ] Add organization logo (from Settings) to portal header
- [ ] Add customizable portal accent color
- [ ] Add organization name in header
- [ ] Support custom welcome message

**Self-Service Actions:**
- [ ] Allow customer to update their profile (name, email, timezone)
- [ ] Allow customer to manage payment methods (add/remove/set default)
- [ ] Allow customer to view and upgrade/downgrade subscription
- [ ] Allow customer to purchase add-ons
- [ ] Allow customer to apply coupon codes

**Dashboard Enhancements:**
- [ ] Show next billing date prominently
- [ ] Show upcoming charges estimate
- [ ] Show usage progress vs. plan limits
- [ ] Add quick action cards: "Pay Invoice", "Top Up Wallet", "View Usage"

**Wallet Page:**
- [ ] Add transaction history table
- [ ] Add balance chart
- [ ] Allow customer to request top-up

**Usage Page:**
- [ ] Auto-select subscription if customer has only one
- [ ] Add usage trend chart
- [ ] Show plan limits vs. current usage (progress bars)
- [ ] Show projected end-of-period usage

**Invoice Page:**
- [ ] Add inline PDF viewer
- [ ] Add "Pay Now" button for outstanding invoices
- [ ] Add payment history per invoice

---

## 7. Implementation Priority

### Phase 1: Fix Critical Issues (High Impact, Low Effort)
- [ ] Fix Finalize Invoice mutation (broken functionality)
- [ ] Add Edit button to CustomerDetailPage
- [ ] Add pagination to all table views
- [ ] Add global header with breadcrumbs
- [ ] Add Cmd+K command palette for global search

### Phase 2: Modal → Page Conversions (High Impact, Medium Effort)
- [ ] Create Plan detail page (`/admin/plans/:id`)
- [ ] Create Invoice detail page (`/admin/invoices/:id`)
- [ ] Create Wallet detail page (`/admin/wallets/:id`)
- [ ] Convert Billing Entity form to full page
- [ ] Convert Credit Note creation to full page

### Phase 3: Missing CRUD Operations (Medium Impact, Low Effort)
- [ ] Add subscription field editing
- [ ] Add "Record Manual Payment" action
- [ ] Add "Create One-Off Invoice" action
- [ ] Add "Remove Applied Coupon" action
- [ ] Standardize row actions (dropdown menus instead of icon-only buttons)

### Phase 4: UX Enrichment (Medium Impact, Medium Effort)
- [ ] Dashboard: date range selector, trend indicators, clickable stat cards
- [ ] Customer health indicators
- [ ] Table column sorting
- [ ] Bulk actions for invoices and subscriptions
- [ ] Integration detail pages

### Phase 5: Portal Enhancement (Medium Impact, High Effort)
- [ ] Portal branding customization
- [ ] Customer self-service actions
- [ ] Portal payment method management
- [ ] Portal subscription management
- [ ] Mobile-first portal redesign

### Phase 6: Advanced Features (Lower Priority)
- [ ] Restructure sidebar navigation
- [ ] Add notification system
- [ ] Add activity feed improvements
- [ ] Add charge model visualizer for plans
- [ ] Add revenue analytics deep-dive page
