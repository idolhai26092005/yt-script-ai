# Baseline 2026-07-28

- `rg` for `app.core.prompts` and its six prompt constants across `backend/app`, `backend/tests`, `backend/scripts` returns only `backend/app/core/prompts.py`.
- AST import scan excluding the target file returns `no callers` for `app.core.prompts`.
- Cleanup target: delete `backend/app/core/prompts.py`; keep active production prompts under `app/services/production/prompts/`.

## Verification

- `venv/bin/python scripts/check_dead_code.py`: backend dead-code ok
- `venv/bin/python scripts/check_test_taxonomy.py`: backend test taxonomy ok
- `venv/bin/python scripts/check_import_boundaries.py`: backend import boundaries ok
- `venv/bin/pytest -q`: 166 passed, 4 skipped
- `graphify update .` from backend: 1568 nodes, 3191 edges, 160 communities
