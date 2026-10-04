from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .routers import (
    admin,
    auth,
    dashboard,
    invoices,
    products,
    team,
    webhook_settings,
    webhooks_in,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(products.router)
app.include_router(dashboard.router)
app.include_router(team.router)
app.include_router(invoices.router)
app.include_router(webhook_settings.router)
app.include_router(webhooks_in.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name}
