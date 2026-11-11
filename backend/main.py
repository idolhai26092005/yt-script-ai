import uvicorn
import os
import sys
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

admin_secret = settings.ADMIN_SECRET
env = settings.ENV.strip('\'"').strip().lower()
db_url = settings.DATABASE_URL.strip('\'"').strip().lower()


def enforce_runtime_config():
    if env == "production" and db_url.startswith("sqlite") and "pytest" not in sys.modules:
        raise RuntimeError("CRITICAL: production ENV requires a PostgreSQL/Supabase DATABASE_URL, not SQLite.")


# Startup migration guard: keep current auto-upgrade default, but allow Render or
# Supabase deployments to run Alembic out-of-band without code changes.
def run_alembic_upgrade():
    from alembic.config import Config
    from alembic import command
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ini_path = os.path.join(base_dir, "alembic.ini")
        alembic_cfg = Config(ini_path)
        alembic_cfg.set_main_option("script_location", os.path.join(base_dir, "alembic"))
        command.upgrade(alembic_cfg, "head")
        print("INFO: Alembic migrations applied successfully.")
    except Exception as e:
        print(f"Database migration error: {e}")
        if env == "production":
            raise


# Startup migration guard: this wrapper centralizes the feature flag so tests and
# deploy scripts can verify skip behavior without touching Alembic internals.
def run_startup_migrations():
    if not settings.AUTO_RUN_MIGRATIONS:
        print("INFO: Alembic auto migration skipped by AUTO_RUN_MIGRATIONS=false.")
        return
    run_alembic_upgrade()


enforce_runtime_config()
run_startup_migrations()

# Default API key seeding removed for security



from contextlib import asynccontextmanager
import asyncio
from app.api.v1.endpoints.gemini import start_cleanup_tasks

@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_task = start_cleanup_tasks()
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

from app.api.v1.router import api_router
from app.core.limiter import limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

app = FastAPI(title="YouTube Script AI Generator API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Validate ADMIN_SECRET
import logging
logger = logging.getLogger("uvicorn.error")

if not admin_secret or admin_secret.strip('\'"').strip() == "admin_secret_key_here":
    logger.warning("WARNING: ADMIN_SECRET is unset or using default value. This is insecure in production.")

# Configure CORS
allowed_origins_str = settings.ALLOWED_ORIGINS
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]

allow_origin_regex = None
allow_credentials = True
if not allowed_origins:
    # Default fallback: localhost only
    allow_origin_regex = r"https?://localhost(:\d+)?"
elif "*" in allowed_origins:
    if env == "production" and "pytest" not in sys.modules:
        raise RuntimeError("CRITICAL: ALLOWED_ORIGINS='*' is not allowed in production.")
    logger.warning("WARNING: ALLOWED_ORIGINS contains '*' which allows any origin. Disabling allow_credentials for wildcard.")
    allowed_origins = ["*"]
    allow_credentials = False
    allow_origin_regex = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to YouTube Script AI API"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        reload_excludes=["*.db", "*.db-journal", "sql_app.db", "sql_app.db-journal"]
    )
