from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import billable_metrics, customers, dashboard, items, plans, subscriptions

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


@app.get("/")
async def root():
    return {
        "message": settings.APP_DOMAIN,
        "status": "running",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
