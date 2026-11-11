import os
import subprocess
import sys


# Runtime import guard: subprocess exercises `main.py` startup flags the same way
# Render starts the app, while keeping test env isolated from developer settings.
def run_backend_import(extra_env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": ".",
            "ADMIN_SECRET": "test-admin-secret",
            "ENV": "development",
            "DATABASE_URL": "sqlite:////tmp/yt_script_ai_runtime_test.db",
            "AUTO_RUN_MIGRATIONS": "false",
        }
    )
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", "import main"],
        cwd=os.getcwd(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


# Migration skip guard proves platform-managed migrations can be used without
# forcing an Alembic connection during app import.
def test_auto_run_migrations_false_skips_startup_alembic():
    result = run_backend_import({})

    assert result.returncode == 0
    assert "Alembic auto migration skipped" in result.stdout


# Production DB guard keeps accidental SQLite deploys blocked even if migrations
# are disabled, preserving the existing Supabase/PostgreSQL requirement.
def test_production_sqlite_rejected_even_when_auto_migration_disabled():
    result = run_backend_import({"ENV": "production"})

    assert result.returncode != 0
    assert "production ENV requires a PostgreSQL/Supabase DATABASE_URL" in result.stderr
