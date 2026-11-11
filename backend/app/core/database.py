import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# Detect if running under pytest
is_testing = "pytest" in sys.modules or os.getenv("TESTING") == "True"

if is_testing:
    SQLALCHEMY_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:////tmp/yt_script_ai_test.db")
else:
    SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# PostgreSQL từ Supabase dùng postgres:// nhưng SQLAlchemy cần postgresql://
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")

engine_args = {}
if is_sqlite:
    engine_args["connect_args"] = {"check_same_thread": False}
else:
    engine_args["pool_size"] = 3
    engine_args["max_overflow"] = 5
    engine_args["pool_recycle"] = 300
    engine_args["pool_pre_ping"] = True
    engine_args["connect_args"] = {"connect_timeout": 10}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    **engine_args
)

if is_sqlite:
    from sqlalchemy.engine import Engine
    from sqlalchemy import event
    
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Helper for JSON columns supporting both PostgreSQL (JSONB) and SQLite (JSON/Text)
from sqlalchemy import JSON, Column
from sqlalchemy.dialects.postgresql import JSONB

def json_column(*args, **kwargs):
    """
    Returns a Column that uses JSONB on PostgreSQL and JSON on SQLite.
    Handles serialization/deserialization transparently.
    """
    return Column(JSONB().with_variant(JSON, "sqlite"), *args, **kwargs)
