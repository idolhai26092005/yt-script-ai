# Baseline 2026-07-28

## Graphify

- Scope: `backend`
- Command run before edits: `graphify update .`
- Result: 1303 nodes, 2555 edges, 136 communities
- Built from commit: `25962546`
- God nodes: `ScriptProducer` 94 edges, `ProductionService` 68 edges

## Dirty Worktree To Preserve

- Existing OpenSpec archive movement for `refactor-backend-production-architecture`
- Existing modified spec: `openspec/specs/youtube-script-ai/spec.md`
- Existing untracked backend tests: `backend/tests/test_production_architecture_characterization.py`, `backend/tests/test_prompt_catalog.py`
- Existing debug/data artifacts: `backend/debug_snapshots/`, `debug_snapshots/`, `docs/mo_ta.txt`, Vietnamese elephant-history doc
- Existing archived changes and `openspec/specs/backend-production-architecture/`

## Relevant Archived Context

- `refactor-backend-production-architecture` completed most extraction work.
- Remaining unchecked verification tasks: targeted state/support tests, validation tests, prompt tests, producer/endpoint/full targeted backend tests.
- Current cleanup must not revert that archive or delete compatibility paths without import evidence.

## Baseline Test Attempt

- Command attempted: `pytest tests/test_production_architecture_characterization.py tests/test_prompt_catalog.py tests/test_crud_series.py tests/test_producer_single_flow.py -q`
- Result: shell cannot find `pytest`
- Command attempted: `python3 -m pytest tests/test_production_architecture_characterization.py tests/test_prompt_catalog.py tests/test_crud_series.py tests/test_producer_single_flow.py -q`
- Result: `/usr/bin/python3: No module named pytest`
- Command attempted: `env PYTHONPATH=. venv/bin/pytest tests/test_production_architecture_characterization.py tests/test_prompt_catalog.py tests/test_crud_series.py tests/test_producer_single_flow.py -q`
- Result: 9 passed in 1.84s
- Follow-up: keep `PYTHONPATH=.` in backend test commands or add pytest config later.

## Debug Snapshot Quarantine

- `backend/debug_snapshots/` and `debug_snapshots/` are untracked local diagnostics.
- Cleanup action: ignore both paths instead of deleting user-local evidence.

## Final Verification In This Pass

- Targeted tests: 16 passed.
- Import boundary script: `backend import boundaries ok`.
- Full backend tests: 164 passed, 4 skipped.
- Final backend graph refresh: 1319 nodes, 2577 edges, 147 communities.
