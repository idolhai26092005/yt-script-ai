## 1. Source Audit Checker

- [x] 1.1 Extend `backend/scripts/check_dead_code.py` with static app-module reachability audit and intentional allowlist reasons.
- [x] 1.2 Add contract tests for unreferenced module failures and allowlist reason coverage.

## 2. Spec And Verification

- [x] 2.1 Sync backend maintenance spec with the unreferenced-module audit requirement.
- [x] 2.2 Run backend dead-code checker, taxonomy checker, import boundary checker, full pytest suite, and `graphify update .`.
- [x] 2.3 Archive the completed OpenSpec change.
