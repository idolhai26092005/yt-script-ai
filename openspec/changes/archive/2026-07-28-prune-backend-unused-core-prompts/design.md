## Context

Static AST import scan found `app.core.prompts` as an unreferenced backend module. `rg` across `backend/app`, `backend/tests`, and `backend/scripts` found no import or constant usage from that module. Active production prompts live under `app/services/production/prompts/`.

## Goals / Non-Goals

**Goals:**
- Remove a proven unused prompt module.
- Add an enforceable guard against reintroducing that dead import surface.
- Preserve all active prompt/validation/role contract modules.

**Non-Goals:**
- No prompt text changes.
- No production pipeline behavior changes.
- No deletion of series schemas/models/migrations.
- No removal of architecture scaffolds that still document target contracts.

## Decisions

### Decision 1: Delete only caller-free source

`app.core.prompts` has no direct imports and no constant references. It can be deleted safely. Candidate modules such as prompt catalog, validation registry, and orchestrator stay because they have tests/spec commitments or future architecture value.

Alternative: remove every module without runtime imports. Rejected because some modules are intentional contract scaffolds and deleting them would reduce architecture clarity.

### Decision 2: Guard with static banned-module checker

`scripts/check_dead_code.py` checks that removed modules do not exist and are not imported by backend Python files.

Alternative: add vulture/ruff dependency. Rejected because no new dependency is needed for one known dead module.

## Risks / Trade-offs

- Dynamic import blind spot -> full test suite and direct `rg` reduce risk; no evidence dynamic imports this module.
- Small cleanup compared to total source size -> acceptable because objective requires evidence-based deletion, not risky bulk removal.
