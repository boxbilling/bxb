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
- [ ] Add subscription lifecycle timeline (created → active → events → invoices → payments)
- [ ] Add "Invoices" tab on detail page showing all invoices for this subscription
- [ ] Improve "Change Plan" dialog: show price comparison, proration preview, effective date picker
- [ ] Add "Pause/Resume" subscription action (if backend supports it)
- [ ] Show next billing date prominently
- [ ] Add usage trend mini-chart on detail page

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
- [ ] Add date range filter
- [ ] Add virtual scrolling for large event lists
- [ ] Format properties as structured key-value pairs instead of raw JSON
- [ ] Add event volume chart (events/hour sparkline above table)
- [ ] Add "Reprocess" action per event
- [ ] Move fee estimator to a collapsible sidebar panel instead of modal (enables side-by-side viewing)

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
- [ ] **Fix Finalize Invoice mutation** (currently broken/stub)
- [ ] **Invoices should have a detail page** (`/admin/invoices/:id`). Invoices are complex documents with fees, taxes, settlements, credit notes, and audit trails. This is too much content for a modal dialog.
- [ ] Invoice detail page layout: header with status + actions, fee table, tax summary, settlement history, related credit notes, audit trail
- [ ] Add inline PDF preview (render in iframe or use react-pdf)
- [ ] Add "Create One-Off Invoice" action
- [ ] Add bulk finalize for draft invoices
- [ ] Add "Send Reminder" action for overdue invoices

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
- [ ] Add clickable link to parent invoice from fee row
- [ ] Add clickable link to subscription/customer
- [ ] Keep detail as modal (fees are subordinate to invoices, not standalone entities)
- [ ] Improve tax display with rate percentages

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
- [ ] Use dropdown menu with labeled actions instead of icon-only buttons
- [ ] Add partial refund support in refund dialog (amount input)
- [ ] Add links to invoice and customer in detail modal
- [ ] Add retry failed payment action
- [ ] Show checkout URL as clickable link in detail

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
- [ ] **Credit note creation should be a full page** (`/admin/credit-notes/new`). The cascading form (select customer → select invoice → select fees → set amounts) is too complex for a modal.
- [ ] Add edit capability for draft credit notes
- [ ] Keep detail view as modal (credit notes are simpler than invoices once created)
- [ ] Pre-fill form when navigating from invoice detail page (already partially implemented via state)

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
- [ ] Add card brand icons (Visa, Mastercard, Amex logos)
- [ ] Group by customer in table view
- [ ] Add "Add Payment Method" directly from Customer Detail page
- [ ] Show masked card number prominently

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
- [ ] **Wallet detail should be a full page** (`/admin/wallets/:id`). Transaction history deserves proper space with filters, pagination, and a balance timeline chart.
- [ ] Add balance timeline chart showing credits in/out over time
- [ ] Add running balance column to transaction history
- [ ] Show projected depletion date based on consumption rate
- [ ] Add "Transfer Credits" between wallets action

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
- [ ] Add "Remove" (unapply) action in View Applied modal
- [ ] Add usage analytics: times used, total discount given, remaining uses
- [ ] Add "Duplicate" action for quick coupon creation
- [ ] Improve form UX: show live preview of discount (e.g., "Customer pays $80/mo instead of $100/mo")

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
- [ ] Add "Applications" count column
- [ ] Add application history view
- [ ] Show amount preview when overriding default amount

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
- [ ] Improve "Apply to Entity" UX: show searchable entity list instead of raw ID input
- [ ] Add "Applied To" expandable section per tax
- [ ] Format rate as percentage consistently
- [ ] Add tax group/category concept

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
- [ ] Add counts to tabs: "Endpoints (5)" and "Recent (142)"
- [ ] Add event type filter for recent webhooks
- [ ] Add delivery success rate indicator per endpoint
- [ ] Add retry history timeline per webhook

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
- [ ] Add performance stats: recovery rate, total recovered amount, active campaigns
- [ ] Add campaign detail page with execution history
- [ ] Show campaign timeline with attempts and outcomes
- [ ] Add "Preview" mode to simulate campaign on test data

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
- [ ] Add progress bar showing current usage as percentage of threshold
- [ ] Add alert trigger history (dates, values at trigger time)
- [ ] Add "Test Alert" action to simulate threshold breach
- [ ] Improve table: show subscription name, metric name, progress percentage

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
- [ ] Add "Select all overdue invoices" checkbox in create form
- [ ] Add batch creation: "Create requests for all customers with overdue invoices"
- [ ] Show payment attempt history in detail modal
- [ ] Consider merging into Payments page as a tab

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
- [ ] Add descriptions for each export type
- [ ] Replace JSON filter input with structured form (date range, status, customer, etc.)
- [ ] Add export size estimate before creation
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
