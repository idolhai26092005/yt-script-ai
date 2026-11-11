## 1. Baseline

- [x] 1.1 Record current backend test file count and full-suite result before moving files.

## 2. Test Taxonomy

- [x] 2.1 Add `backend/pytest.ini` with stable pythonpath and discovery settings.
- [x] 2.2 Add `backend/tests/README.md` describing taxonomy folders and ownership.
- [x] 2.3 Move root test modules into taxonomy folders without changing test intent.
- [x] 2.4 Fix any moved test path assumptions revealed by full-suite run.

## 3. Enforcement

- [x] 3.1 Add `backend/scripts/check_test_taxonomy.py` to reject root-level `test_*.py` files and unknown taxonomy folders.
- [x] 3.2 Add a taxonomy checker test.
- [x] 3.3 Update backend README test instructions.

## 4. Verification And Archive

- [x] 4.1 Run taxonomy checker, import boundary checker, and full backend pytest suite.
- [x] 4.2 Sync delta spec into `openspec/specs/backend-maintenance-stability/spec.md`.
- [x] 4.3 Run `graphify update .` from `backend`.
- [x] 4.4 Archive this OpenSpec change.
