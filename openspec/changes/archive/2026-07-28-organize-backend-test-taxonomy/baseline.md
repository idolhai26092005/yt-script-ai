# Baseline 2026-07-28

- Root-level backend test modules: 46
- `venv/bin/pytest tests -q`: fails before collection with `ModuleNotFoundError: No module named 'app'`
- Previous verified command from earlier change: `env PYTHONPATH=. venv/bin/pytest tests -q` -> 164 passed, 4 skipped
- Goal for this change: make plain `venv/bin/pytest` work from `backend` and eliminate root-level `test_*.py` files.

## Verification

- `venv/bin/python scripts/check_test_taxonomy.py`: backend test taxonomy ok
- `venv/bin/python scripts/check_import_boundaries.py`: backend import boundaries ok
- `venv/bin/pytest -q`: 165 passed, 4 skipped
- `graphify update .` from backend: 1561 nodes, 3183 edges, 151 communities
