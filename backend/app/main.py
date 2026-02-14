from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import (
    add_ons,
    billable_metrics,
    commitments,
    coupons,
    credit_notes,
    customers,
    dashboard,
    data_exports,
    dunning_campaigns,
    events,
    fees,
    integrations,
    invoices,
    items,
    organizations,
    payment_requests,
    payments,
    plans,
    subscriptions,
    taxes,
    usage_thresholds,
    wallets,
    webhook_endpoints,
)

OPENAPI_TAGS = [
    {"name": "Dashboard", "description": "Analytics dashboard and overview statistics."},
    {"name": "Customers", "description": "Create, read, update, and delete customers."},
    {"name": "Plans", "description": "Create, read, update, and delete billing plans."},
    {"name": "Subscriptions", "description": "Manage customer subscriptions to plans."},
    {"name": "Events", "description": "Ingest and query usage events."},
    {"name": "Fees", "description": "Query and manage invoice fees."},
    {"name": "Invoices", "description": "Manage invoices and their lifecycle."},
    {"name": "Payments", "description": "Process payments, checkout sessions, and refunds."},
    {"name": "Wallets", "description": "Manage prepaid credit wallets for customers."},
    {"name": "Coupons", "description": "Create and apply discount coupons."},
    {"name": "Add-ons", "description": "Create and apply one-time add-on charges."},
    {"name": "Credit Notes", "description": "Issue and manage credit notes against invoices."},
    {"name": "Taxes", "description": "Configure tax rates and apply taxes to entities."},
    {"name": "Webhooks", "description": "Manage webhook endpoints and monitor deliveries."},
    {"name": "Organizations", "description": "Manage organization settings and API keys."},
    {"name": "Dunning", "description": "Configure dunning campaigns for failed payments."},
    {"name": "Payment Requests", "description": "Create and track manual payment requests."},
    {"name": "Commitments", "description": "Manage minimum spend commitments on plans."},
    {"name": "Thresholds", "description": "Configure usage-based billing thresholds."},
    {"name": "Data Exports", "description": "Export billing data as CSV files."},
    {"name": "Integrations", "description": "Connect and manage external system integrations."},
    {"name": "Items", "description": "Internal item management."},
]

app = FastAPI(
    title="BxB Billing API",
    version="1.0.0",
    description=(
        "A comprehensive usage-based billing platform API. "
        "Manage customers, plans, subscriptions, invoices, payments, wallets, "
        "coupons, credit notes, taxes, webhooks, and more."
    ),
    openapi_tags=OPENAPI_TAGS,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(items.router, prefix="/items", tags=["Items"])
app.include_router(customers.router, prefix="/v1/customers", tags=["Customers"])
app.include_router(
    billable_metrics.router, prefix="/v1/billable_metrics", tags=["Customers"]
)
app.include_router(plans.router, prefix="/v1/plans", tags=["Plans"])
app.include_router(subscriptions.router, prefix="/v1/subscriptions", tags=["Subscriptions"])
app.include_router(events.router, prefix="/v1/events", tags=["Events"])
app.include_router(fees.router, prefix="/v1/fees", tags=["Fees"])
app.include_router(invoices.router, prefix="/v1/invoices", tags=["Invoices"])
app.include_router(payments.router, prefix="/v1/payments", tags=["Payments"])
app.include_router(wallets.router, prefix="/v1/wallets", tags=["Wallets"])
app.include_router(coupons.router, prefix="/v1/coupons", tags=["Coupons"])
app.include_router(add_ons.router, prefix="/v1/add_ons", tags=["Add-ons"])
app.include_router(credit_notes.router, prefix="/v1/credit_notes", tags=["Credit Notes"])
app.include_router(taxes.router, prefix="/v1/taxes", tags=["Taxes"])
app.include_router(
    webhook_endpoints.router,
    prefix="/v1/webhook_endpoints",
    tags=["Webhooks"],
)
app.include_router(
    organizations.router,
    prefix="/v1/organizations",
    tags=["Organizations"],
)
app.include_router(
    dunning_campaigns.router,
    prefix="/v1/dunning_campaigns",
    tags=["Dunning"],
)
app.include_router(
    payment_requests.router,
    prefix="/v1/payment_requests",
    tags=["Payment Requests"],
)
app.include_router(
    commitments.router,
    prefix="/v1",
    tags=["Commitments"],
)
app.include_router(
    usage_thresholds.router,
    prefix="/v1",
    tags=["Thresholds"],
)
app.include_router(
    data_exports.router,
    prefix="/v1/data_exports",
    tags=["Data Exports"],
)
app.include_router(
    integrations.router,
    prefix="/v1/integrations",
    tags=["Integrations"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": settings.APP_DOMAIN,
        "status": "running",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}
