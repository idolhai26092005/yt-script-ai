## 1. Evidence

- [x] 1.1 Record static import and `rg` evidence for `app.core.prompts`.

## 2. Cleanup

- [x] 2.1 Delete `backend/app/core/prompts.py`.
- [x] 2.2 Add `backend/scripts/check_dead_code.py` for banned removed modules.
- [x] 2.3 Add tests for dead-code checker.
- [x] 2.4 Update backend README verification commands.

## 3. Verification

- [x] 3.1 Run dead-code checker, taxonomy checker, import boundary checker, and full backend pytest suite.
- [x] 3.2 Sync delta spec into `openspec/specs/backend-maintenance-stability/spec.md`.
- [x] 3.3 Run `graphify update .` from `backend`.
- [x] 3.4 Archive this OpenSpec change.
