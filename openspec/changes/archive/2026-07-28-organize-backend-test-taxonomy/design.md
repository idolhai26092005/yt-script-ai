## Context

The current backend suite has 46 `test_*.py` files directly under `backend/tests/`. A shared `conftest.py` exists now, but test execution still relies on explicit `PYTHONPATH=.` unless configured. The cleanup goal asks for a more systematic test layout before deeper dead-code removal.

## Goals / Non-Goals

**Goals:**
- Make test intent visible from filesystem path.
- Preserve all existing test behavior while moving files.
- Make `venv/bin/pytest` work from `backend` without extra environment prefix.
- Add a cheap local checker for taxonomy drift.

**Non-Goals:**
- No runtime code rewrite.
- No deletion of test coverage in this pass.
- No new dependency.
- No frontend test restructure.

## Decisions

### Decision 1: Physical test folders over marker-only taxonomy

Move files into folders because path taxonomy is visible in `find`, pytest output, and code review. Markers can be added later if CI needs selection by marker.

Alternative: keep flat files and add README. Rejected because it does not satisfy the cleanup goal strongly enough.

### Decision 2: Keep `tests/conftest.py` at suite root

Root fixture remains shared by all nested packages. Subdirectories do not need `__init__.py` because tests use absolute `app.*` imports.

Alternative: per-folder conftest. Rejected because current fixture surface is small and shared.

### Decision 3: Taxonomy checker is path-based

Add `scripts/check_test_taxonomy.py` to fail when root-level `test_*.py` files appear or when unexpected test folders are introduced.

Alternative: custom pytest plugin. Rejected because it adds complexity and runtime hook risk.

## Risks / Trade-offs

- Snapshot tests may rely on `__file__` depth -> fix to compute project root robustly.
- Moving many files inflates diff -> acceptable because content stays unchanged and full test suite proves behavior.
- Existing commands targeting old paths break -> README documents new suite-wide command; targeted commands can use new paths.
