# Backend Refactor Review Checklist

Use for OpenSpec change `refactor-backend-production-architecture`.

## Diff Label

- `pure-move`: code moved/delegated, behavior unchanged.
- `compat-shim`: old import/path kept alive during migration.
- `behavior-change`: runtime behavior intentionally changes; requires regression proof.
- `contract-change`: API/SSE/schema/cache/log shape changes; requires migration note.

## Required Review Checks

- Public endpoint paths and response keys unchanged.
- SSE event keys unchanged unless labeled `contract-change`.
- `ProductionService` constructor unchanged.
- Existing imports from `app.core.validation` and `app.core.production_prompts` are removed after shim cleanup; use production package imports.
- Role/prompt/validation scaffold does not affect runtime unless task explicitly says to wire it.
- New helper block has durable comment explaining guardrail.
- No SQLAlchemy session calls inside production role/support modules.
- No endpoint imports from role internals.
- No prompt text change in pure-move PR.
- No validation rule order change in pure-move PR.
- Backend graph refreshed with `graphify update backend` after backend runtime edits.

## Manual Check Commands

```bash
backend/venv/bin/python - <<'PY'
from app.services.production import ProductionService
from app.services.production.state import new_script_data
from app.services.production.support.sse import sse_event
from app.services.production.validation.registry import get_validators
from app.services.production.prompts.catalog import get_prompt_spec
from app.services.production.orchestrator import RoleGraphRunner
print("manual import smoke ok")
PY
```

## Compatibility Shim Rule

Every shim must say:

- What old import/path it protects.
- Which migration phase can remove it.
- Why keeping it does not change behavior.

Shim cleanup requires all of these to be true:

- `rg "app.core.validation|app.core.production_prompts" backend/app backend/tests` returns no required imports.
- Replacement imports use `app.services.production.validation.*` or `app.services.production.prompts.*`.
- Manual import smoke covers the new role-owned path.
- The final targeted backend test task for the affected surface is ready to run.
