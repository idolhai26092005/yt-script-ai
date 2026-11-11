## Why

Backend production pipeline has accumulated long, high-coupling files that are hard to review, modify, and extend safely. Current graph evidence shows `ScriptProducer` as the largest god node, so future screenplay roles, validators, and prompt changes need clearer module boundaries before more features are added.

## What Changes

- Introduce a role-graph architecture for the screenplay production pipeline while preserving existing public API, SSE payload shape, cache compatibility, and canonical v3 save behavior.
- Split production responsibilities into state, ports, roles, prompt catalog, validation package, and support modules through a strangler migration.
- Add reviewability standards: import boundaries, PR size budget, ADR/RFC flow, compatibility shims, complexity gates, and review checklist.
- Add declarative registries for role execution, validation rules, prompt selection, and optional/no-op strategies.
- Add characterization, contract, and integration tests around current behavior before moving runtime code.
- No breaking public API changes are planned.

## Capabilities

### New Capabilities

- `backend-production-architecture`: Defines maintainable backend architecture rules for the production pipeline, including role graph orchestration, validation registry, prompt catalog, import boundaries, observability, and migration guardrails.

### Modified Capabilities

- None. The existing `youtube-script-ai` user-facing requirements remain unchanged; this change refactors internal architecture only.

## Impact

- Affected code: `backend/app/services/production/producer.py`, `backend/app/services/production/base.py`, `backend/app/core/validation.py`, `backend/app/core/production_prompts.py`, `backend/app/api/v1/endpoints/script_production.py`, `backend/app/api/v1/endpoints/series.py`, and related tests.
- Affected docs: `docs/backend-refactor-proposal.md`, future ADRs under `docs/adr/`, and OpenSpec artifacts under this change.
- Runtime compatibility: existing endpoints, response schemas, SSE event keys, project cache, phase log, repository abstraction, and frontend integration must stay stable during migration.
- Dependencies: no new runtime dependency required. Optional import-boundary enforcement may be implemented with an AST-based pytest first; third-party lint tooling is optional later.
