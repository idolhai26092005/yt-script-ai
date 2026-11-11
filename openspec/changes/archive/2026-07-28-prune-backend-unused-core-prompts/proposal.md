## Why

`backend/app/core/prompts.py` contains old transcript/chunk prompt constants that are no longer imported by runtime, tests, or scripts. Keeping unused prompt surfaces makes future prompt cleanup ambiguous and risks editing a dead file instead of the active production prompt catalog.

## What Changes

- Delete `backend/app/core/prompts.py` after static import/search evidence proves it has no callers.
- Add a lightweight dead-code guard script for banned/removed backend modules.
- Add tests for the guard so removed legacy modules do not come back accidentally.
- Keep prompt catalog, production prompt modules, validation registry, and role graph scaffold untouched because they still serve architecture contracts or tests.

## Capabilities

### New Capabilities

### Modified Capabilities
- `backend-maintenance-stability`: Add evidence-based dead-code guardrails for removed backend modules.

## Impact

- Affected files: `backend/app/core/prompts.py`, `backend/scripts/check_dead_code.py`, `backend/tests/contracts/`, `backend/README.md`, OpenSpec docs.
- Runtime behavior impact: none expected; file has no import callers.
- Risk: hidden dynamic import could exist; mitigation is full backend tests plus static guard.
