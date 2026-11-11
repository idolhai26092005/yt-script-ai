## Context

Graphify backend refresh on 2026-07-28 shows `ScriptProducer` and `ProductionService` remain top hubs. The archived backend architecture change already split role, prompt, validation, and support modules, but several verification tasks were left unchecked. Current tests have no shared `conftest.py`; many files create metadata and sessions directly against the module-level engine. Series runtime remains mounted in `app/api/v1/router.py` and frontend still references `/series`, but user request says series generation must be isolated and temporarily disabled so single generation is not affected.

## Goals / Non-Goals

**Goals:**
- Keep single/longform generation behavior stable.
- Make series disabled by backend config without deleting data model or Alembic history.
- Give tests one isolated DB harness and clear smoke/contract/integration grouping.
- Preserve Render/Vercel/Supabase deploy path with reversible migration config.
- Remove only dead code/debug artifacts proven unused or replaced.

**Non-Goals:**
- No database table/column drop in this pass.
- No frontend redesign.
- No prompt behavior change for single generation.
- No full rewrite of `ScriptProducer`.
- No removal of compatibility shims unless imports prove unused.

## Decisions

### Decision 1: Disable series with feature flag, not deletion

Add `ENABLE_SERIES_FLOW` in settings. Router includes `/series` only when enabled. Production endpoints reject `series_short`/`series_long` modes when disabled so accidental direct calls cannot enter the single pipeline.

Alternative: delete series router/models/migrations now. Rejected because Supabase production may already have data and frontend still references series routes.

### Decision 2: Keep DB cleanup reversible

Add `AUTO_RUN_MIGRATIONS` with default preserving current deploy behavior. Alembic remains the only schema migration path; runtime cleanup only changes config guardrails and test isolation.

Alternative: alter/drop series tables immediately. Rejected because rollback and production data risk are too high for less than 10% benefit.

### Decision 3: Build shared pytest DB fixture before pruning tests

Create a central test harness that sets a test DB URL before backend modules are imported where possible and provides session cleanup. Then move or rewrite tests around behavior groups. Only after baseline passes should stale snapshot/debug tests be removed.

Alternative: mass-delete current tests first. Rejected because it hides regressions in production pipeline.

### Decision 4: Prefer low-risk dead-code cleanup

Remove debug artifacts and obsolete imports only when `rg` shows no runtime caller or replacement exists. For ambiguous legacy adapters, keep and document removal clock.

## Risks / Trade-offs

- Series disabled may surface frontend 404/400 where UI still exposes series mode -> backend returns explicit disabled response; frontend can be adjusted later.
- Startup migration flag could be misconfigured -> default keeps current behavior, `.env.example` documents production-safe choices.
- Test harness import order may expose hidden global engine coupling -> fix with minimal fixture/import changes, not DB engine rewrite.
- Keeping series DB tables leaves some schema noise -> acceptable because data safety beats cosmetic cleanup.

## Migration Plan

1. Add config flags and route/endpoint guards.
2. Add shared test DB fixture and first tests for series-disabled behavior and migration config.
3. Prune or quarantine only confirmed stale debug/snapshot tests.
4. Run targeted tests: config/router/production request, CRUD DB smoke, import boundary, archived architecture checks if available.
5. Run `graphify update .` from `backend`.
6. Rollback: set `ENABLE_SERIES_FLOW=true` to restore series router; set `AUTO_RUN_MIGRATIONS=true` to preserve old startup migration behavior.
