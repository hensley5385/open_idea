from fastapi import FastAPI, Request, Header, Depends
from fastapi.staticfiles import StaticFiles
from database import engine, Base, get_db, migrate_sqlite_schema
from routers import storefront, admin, portal
from models import Lead
from sqlalchemy.orm import Session
import os
from pathlib import Path

# Migrate older local SQLite schemas (adds missing columns)
migrate_sqlite_schema()

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="The Bridge")

# Secret hash for webhook verification (In production, use ENV VARIABLE)
FLUTTERWAVE_SECRET_HASH = "the_bridge_secret_123"

# Mount static files
PROJECT_ROOT = Path(__file__).resolve().parent
STATIC_DIR = PROJECT_ROOT / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

from routers import storefront, admin, portal, webhooks
from routers import chat as chat_router

# Register routers
app.include_router(storefront.router)
app.include_router(portal.router)
app.include_router(webhooks.router)
app.include_router(chat_router.router)

# Admin is mounted behind a secret prefix (do not mount at /admin)
ADMIN_PREFIX = os.getenv("ADMIN_PREFIX", "").strip() or "/_controlpanel"
app.include_router(admin.router, prefix=ADMIN_PREFIX)
