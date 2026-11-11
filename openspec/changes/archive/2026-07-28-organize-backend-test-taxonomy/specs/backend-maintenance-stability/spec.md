## ADDED Requirements

### Requirement: Backend tests are organized by taxonomy
Backend automated tests MUST live under named taxonomy folders that describe the behavior layer they protect, and root-level `test_*.py` files MUST NOT be added.

#### Scenario: Taxonomy checker catches flat tests
- **WHEN** a `test_*.py` file exists directly under `backend/tests/`
- **THEN** the backend taxonomy checker fails and reports the flat test path

#### Scenario: Full backend suite remains runnable
- **WHEN** a developer runs pytest from `backend`
- **THEN** pytest discovers all taxonomy folders without requiring a manual `PYTHONPATH` prefix

### Requirement: Test moves preserve coverage
Moving tests into taxonomy folders MUST preserve the existing backend behavioral coverage.

#### Scenario: Full suite passes after move
- **WHEN** the test taxonomy migration is complete
- **THEN** the full backend pytest suite passes with the same or greater number of runnable tests as the baseline
