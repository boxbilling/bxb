## [0.4.0] - 2026-02-27

- Bump version to 0.3.6 and update release workflow to trigger on pushes to `main` affecting `VERSION`.
- Update `openapi.json` to enhance API documentation with detailed paths and response schemas for dashboard and customer operations.
- Fix duplicate Alembic revision ID in monetary fields migration.
- Migrate from `amount` to `amount_cents` across all models and APIs to standardize monetary values representation. (#1)
- Fix improper JSX structure and ensure proper wrapping for AlertDialogs in PlanDetailPage.
- Add MetricFormPage and routes for metric creation/editing in the admin panel.
- Add PlanFormPage and routes for plan creation/editing in the admin panel.
- Add PlanFormPage and routes for plan creation/editing in the admin panel.
- Use UTC timezone for datetime operations in customer router.
- Bump version to 0.3.5 and add Node.js setup in packages.yml workflow.
- BXB: Test readme update to clarify
- move docs
- BXB: Add testing strategy README for backend/tests
- BXB: Remove unused generate_openapi.py script
- BXB: Remove Portal SDK, consolidate to single bxb package
- BXB: Update README to reflect public smoke-test-only strategy
- BXB: Add pre-commit hook and fix lint errors for clean hook execution
- BXB: Add explicit work/_internal_staging/ entry to .gitignore
- BXB: Strip coverage enforcement and Postgres from CI test workflow
- BXB: Update CLAUDE.md for public repo smoke-test workflow
- BXB: Replace full frontend test suite with minimal smoke tests
- BXB: Remove 100% coverage enforcement from Makefile test-cov target
- BXB: Remove 100% coverage enforcement from public repo pyproject.toml
- BXB: Replace full backend test suite with minimal smoke tests
- BXB: Add executive summary for event ingestion architecture
- BXB: Review and refine documentation for team publication
- BXB: Add data flow diagrams and capacity planning visualization assets
- BXB: Add technical blog post on Kafka + ClickHouse event ingestion architecture
- BXB: Add ingestion pattern comparison matrix and decision framework
- BXB: Add streaming ingestion patterns research document
- BXB: Add API direct-write patterns research document
- BXB: Add direct ClickHouse ingestion research document
- Update openapi to generate and publish Python SDKs.
- update openapi
- Generate portal JWT token for auth endpoint.
- package update
- package update
- version
- consolidate
- names
- Merge remote-tracking branch 'origin/main'
- workflow
- Update README.md
- workflow
- workflow
- workflow
- Merge remote-tracking branch 'origin/main'
- add script
- add script
- pip package
- version

## [0.3.0] - 2026-02-23

- fastapi
- Fix data exports download auth and dialog sizing
- BXB: Enable Stripe Link payment method in checkout sessions
- build
- Add onboarding page with setup progress tracking
- toast
- buttons
- breadcrumbs
- package updates
- Shared models functions
- BXB: Add ChangePlanDialog and TerminateSubscriptionDialog tests
- BXB: Add SubscriptionDetailPage tests for tab-based layout
- BXB: Add tests for all subscription detail tab components
- BXB: Add SubscriptionHeader and SubscriptionKPICards tests
- BXB: Add frontend test infrastructure and SubscriptionInfoSidebar tests
- BXB: Add cross-entity navigation links and Related section to SubscriptionInfoSidebar
- BXB: Add row click navigation and cross-entity links to SubscriptionsPage
- BXB: Extract TerminateSubscriptionDialog to shared component and wire into SubscriptionDetailPage
- BXB: Extract ChangePlanDialog to shared component and wire into SubscriptionDetailPage
- BXB: Add Plan Summary Card to SubscriptionOverviewTab
- BXB: Add payments and credit notes to SubscriptionInvoicesTab
- BXB: Refactor SubscriptionDetailPage to use extracted tab components
- BXB: Add SubscriptionActivityTab component for subscription detail redesign
- BXB: Add SubscriptionLifecycleTab component for subscription detail redesign
- BXB: Add SubscriptionEntitlementsTab component for subscription detail redesign
- BXB: Add SubscriptionThresholdsAlertsTab component for subscription detail redesign
- BXB: Add SubscriptionInvoicesTab component for subscription detail redesign
- BXB: Add SubscriptionOverviewTab component for subscription detail redesign
- BXB: Restructure SubscriptionDetailPage into modular tab-based layout
- BXB: Add SubscriptionKPICards component for subscription detail redesign
- BXB: Add SubscriptionHeader component for subscription detail redesign
- BXB: Add SubscriptionInfoSidebar component for subscription detail redesign
- BXB: Add Quick Actions section to CustomerInfoSidebar and move Create Subscription button
- BXB: Add cross-entity navigation links to customer detail tables
- BXB: Restructure CustomerDetailPage tabs with Add-ons & Coupons and Events tabs
- BXB: Add integration mappings and billing entity to CustomerInfoSidebar
- BXB: Add CustomerEventsTable component with pagination and code filter
- BXB: Add CustomerAddOnsTable component for applied add-ons
- BXB: Enhance CustomerSubscriptionsTable with Plan Name column, Billing Time, and clickable rows
- BXB: Enhance CustomerKPICards with Lifetime Revenue and Active Subscriptions cards
- BXB: Implement sidebar + main content grid layout in CustomerDetailPage
- BXB: Extract CustomerInfoSidebar component from CustomerDetailPage
- BXB: Extract CustomerHeader component from CustomerDetailPage
- BXB: Extract remaining inline components from CustomerDetailPage into separate files
- BXB: Extract seven table tab components from CustomerDetailPage into separate files
- BXB: Extract CustomerPaymentMethodsCard and PortalLinkDialog into separate files
- BXB: Wire up customer applied_add_ons and integration_mappings in frontend API layer
- BXB: Regenerate OpenAPI spec for customer redesign endpoints
- BXB: Add GET /v1/customers/{customer_id}/integration_mappings endpoint
- BXB: Add GET /v1/customers/{customer_id}/applied_add_ons endpoint
- BXB: Add billing_entity_id to CustomerResponse schema
- BXB: Fix chart colors for dark mode readability
- BXB: Make RevenueAnalyticsPage responsive for mobile viewports
- BXB: Make IntegrationsPage and IntegrationDetailPage responsive for mobile viewports
- BXB: Make BillingEntitiesPage responsive for mobile viewports
- BXB: Make DataExportsPage responsive for mobile viewports
- BXB: Make TaxesPage responsive for mobile viewports
- BXB: Make AuditLogsPage responsive with collapsible filters for mobile viewports
- BXB: Make WebhooksPage and ApiKeysPage responsive for mobile viewports
- BXB: Make PaymentMethodsPage and PaymentRequestsPage responsive for mobile viewports
- BXB: Make UsageAlertsPage responsive for mobile viewports
- BXB: Make DunningCampaignsPage and DunningCampaignDetailPage responsive for mobile viewports
- BXB: Make CreditNoteFormPage responsive for mobile viewports
- BXB: Make CreditNotesPage responsive for mobile viewports
- BXB: Make FeesPage responsive for mobile viewports
- BXB: Make catalog pages (MetricsPage, FeaturesPage, AddOnsPage, CouponsPage) responsive for mobile viewports
- BXB: Make BillingEntityFormPage responsive for mobile viewports
- BXB: Make SettingsPage responsive for mobile viewports
- BXB: Make WalletDetailPage responsive for mobile viewports
- BXB: Make SubscriptionDetailPage responsive for mobile viewports
- BXB: Make InvoiceDetailPage responsive for mobile viewports
- BXB: Make PlanDetailPage responsive for mobile viewports
- BXB: Make CustomerDetailPage responsive for mobile viewports
- BXB: Make PaymentsPage responsive for mobile viewports
- BXB: Make EventsPage responsive for mobile viewports
- BXB: Make PlansPage card grid responsive for mobile viewports
- BXB: Make SubscriptionsPage responsive for mobile viewports
- BXB: Make InvoicesPage responsive for mobile viewports
- BXB: Make CustomersPage responsive for mobile viewports
- BXB: Hide less critical table columns on mobile in dashboard cards
- BXB: Make DashboardPage PeriodSelector responsive for mobile
- BXB: Fix dashboard grid layouts for mobile breakpoints
- BXB: Improve AdminLayout mobile header with touch targets and page title
- BXB: Add ResponsiveDialog components that render as Drawer on mobile
- BXB: Make TablePagination responsive for mobile
- BXB: Make PageHeader responsive for mobile
- migration
- portal updates
- Remove revenue trend chart and reorganize layout in `DashboardPage`.
- Add Sentry integration: configure SDK, update dependencies, and extend `.env.example`
- Refactor `AdminLayout` navigation: add `NavItemDef` type, support separators, and enhance external link handling with `_blank` targets.
- Extract `useTheme` hook and refactor `AdminLayout` to use the shared implementation.
- Remove `faqs.ts` and update `AdminLayout` navigation: reorganize and add new menu items (e.g., "Help", "Docs", and "License").
- Update OpenAPI tags: add "Billable Metrics" and fix tag mapping in router config
- Restrict GitHub Actions workflow triggers to `backend/**` path on push.
- Remove `organization_id` column and related constraints from taxes table migration, retain only `category` column.
- Refactor breadcrumb logic: extract `HeaderBreadcrumb` to its own component and use `BreadcrumbProvider` for route label context management in `AdminLayout`.
- BXB: Add missing organization_id and category columns to taxes table
- BXB: Implement route-based code splitting for all 44 page routes (FIX-007)
- BXB: Increase mobile nav link touch targets and spacing in AdminLayout
- BXB: Implement mobile touch target and lazy loading fixes (FIX-002 through FIX-006)

## [0.2.0] - 2026-02-16



# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-10

### Features
- Initial release
- Customer management API (`/v1/customers`)
- Billable Metrics API (`/v1/billable_metrics`)
- Plans API with Charges (`/v1/plans`)
- Subscriptions API (`/v1/subscriptions`)
- FastAPI backend with SQLAlchemy
- React admin dashboard
- 100% test coverage enforcement
- CI/CD with GitHub Actions

### Infrastructure
- Docker support
- PostgreSQL database
- OpenAPI schema generation
- TypeScript client generation
