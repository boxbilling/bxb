from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import (
    add_ons,
    billable_metrics,
    coupons,
    credit_notes,
    customers,
    dashboard,
    dunning_campaigns,
    events,
    fees,
    invoices,
    items,
    organizations,
    payment_requests,
    payments,
    plans,
    subscriptions,
    taxes,
    wallets,
    webhook_endpoints,
)

app = FastAPI(title="API", version="0.0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router, prefix="/dashboard")
app.include_router(items.router, prefix="/items", tags=["items"])
app.include_router(customers.router, prefix="/v1/customers", tags=["customers"])
app.include_router(
    billable_metrics.router, prefix="/v1/billable_metrics", tags=["billable_metrics"]
)
app.include_router(plans.router, prefix="/v1/plans", tags=["plans"])
app.include_router(subscriptions.router, prefix="/v1/subscriptions", tags=["subscriptions"])
app.include_router(events.router, prefix="/v1/events", tags=["events"])
app.include_router(fees.router, prefix="/v1/fees", tags=["fees"])
app.include_router(invoices.router, prefix="/v1/invoices", tags=["invoices"])
app.include_router(payments.router, prefix="/v1/payments", tags=["payments"])
app.include_router(wallets.router, prefix="/v1/wallets", tags=["wallets"])
app.include_router(coupons.router, prefix="/v1/coupons", tags=["coupons"])
app.include_router(add_ons.router, prefix="/v1/add_ons", tags=["add_ons"])
app.include_router(credit_notes.router, prefix="/v1/credit_notes", tags=["credit_notes"])
app.include_router(taxes.router, prefix="/v1/taxes", tags=["taxes"])
app.include_router(
    webhook_endpoints.router,
    prefix="/v1/webhook_endpoints",
    tags=["webhook_endpoints"],
)
app.include_router(
    organizations.router,
    prefix="/v1/organizations",
    tags=["organizations"],
)
app.include_router(
    dunning_campaigns.router,
    prefix="/v1/dunning_campaigns",
    tags=["dunning_campaigns"],
)
app.include_router(
    payment_requests.router,
    prefix="/v1/payment_requests",
    tags=["payment_requests"],
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
