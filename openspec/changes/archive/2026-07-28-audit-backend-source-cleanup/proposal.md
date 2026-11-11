## Why

Backend cleanup already removed obvious dead code, but a few app modules can remain unreferenced by runtime imports because they are public contracts, architecture scaffolds, or migration-adjacent helpers. The cleanup needs a repeatable audit so future work does not confuse intentional scaffolding with forgotten dead code.

## What Changes

- Extend the backend dead-code checker to report unreferenced `backend/app` modules unless each one is explicitly allowlisted with a durable reason.
- Add contract tests for the checker so removed modules stay deleted and intentional scaffolds stay documented.
- Update the backend maintenance spec with an auditable unreferenced-module requirement.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `backend-maintenance-stability`: adds a source-audit requirement for unreferenced backend app modules.

## Impact

- Affected files: `backend/scripts/check_dead_code.py`, `backend/tests/contracts/test_dead_code_guard.py`, `openspec/specs/backend-maintenance-stability/spec.md`.
- Runtime/API impact: none; checker is static and only runs when invoked by tests or developer commands.
- Dependency impact: none; uses Python standard library only.
