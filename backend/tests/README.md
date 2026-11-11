# Backend Test Suite

Tests are grouped by the behavior layer they protect:

- `api/`: FastAPI endpoint adapters, SSE helpers, runtime route guards, request dependencies.
- `contracts/`: schema, prompt, validation, import-boundary, and architecture contracts.
- `db/`: SQLAlchemy models, CRUD helpers, JSON columns, locks, and Alembic/database behavior.
- `regression/`: snapshot or golden-output regression tests.
- `services/gemini/`: provider routing and Gemini/Groq integration unit tests.
- `services/production/`: production pipeline, producer, compressor, observability, semantic verification.
- `topics/`: trending topic domain behavior.

Keep `conftest.py` at suite root. Do not add root-level `test_*.py` files; use the closest taxonomy folder.
