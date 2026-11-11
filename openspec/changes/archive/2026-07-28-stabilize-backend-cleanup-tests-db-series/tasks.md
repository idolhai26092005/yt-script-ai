## 1. Baseline And Scope Guard

- [x] 1.1 Record current Graphify/backend map, dirty worktree state, and existing OpenSpec archive context before edits.
- [x] 1.2 Run a focused baseline test sample for production, DB, and series behavior to expose current failures.

## 2. Series Isolation

- [x] 2.1 Add `ENABLE_SERIES_FLOW` setting and document it in `backend/.env.example`.
- [x] 2.2 Gate `/series` router mounting in `backend/app/api/v1/router.py` without deleting series code or DB models.
- [x] 2.3 Reject `series_short` and `series_long` on `/production/script/generate` when series flow is disabled.
- [x] 2.4 Add tests proving series-disabled routing does not affect production routes.

## 3. Database Safety

- [x] 3.1 Add `AUTO_RUN_MIGRATIONS` setting and preserve current default startup behavior.
- [x] 3.2 Update startup migration code to honor `AUTO_RUN_MIGRATIONS=false` while keeping production SQLite guard.
- [x] 3.3 Add tests for migration skip behavior and production SQLite rejection.

## 4. Test Harness Cleanup

- [x] 4.1 Add shared backend pytest fixtures for isolated SQLite DB setup/teardown.
- [x] 4.2 Move or rewrite DB-facing smoke tests onto the shared fixture.
- [x] 4.3 Quarantine or remove stale snapshot/debug tests only after replacement coverage exists.

## 5. Dead Code And Verification

- [x] 5.1 Remove low-risk dead imports/helpers found by direct search after tests cover replacement behavior.
- [x] 5.2 Run targeted backend tests for config, router, DB, production request guards, and import boundaries.
- [x] 5.3 Run `graphify update .` from `backend` and verify graph artifacts refresh.
