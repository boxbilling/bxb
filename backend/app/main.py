from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import dashboard, items

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


@app.get("/")
async def root():
    return {
        "message": settings.APP_DOMAIN,
        "status": "running",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
