# backend-maintenance-stability Specification

## Purpose
Backend maintenance guardrails for cleanup, test isolation, deploy-safe database migration behavior, and temporary series-flow isolation.

## Requirements
### Requirement: Series flow is feature-gated
The backend MUST be able to disable series creation, episode suggestion, and episode generation without removing database schema or affecting single and longform generation.

#### Scenario: Series router disabled
- **WHEN** `ENABLE_SERIES_FLOW` is false
- **THEN** `/api/v1/series` routes are not mounted
- **AND** `/api/v1/production` routes remain mounted

#### Scenario: Series modes blocked from production endpoint
- **WHEN** a production script request uses `series_short` or `series_long` while series flow is disabled
- **THEN** the backend rejects the request before calling the production pipeline
- **AND** the rejection explains that series flow is temporarily disabled

### Requirement: Database migration behavior is deploy-safe
The backend MUST keep Alembic as the schema migration mechanism and MUST NOT drop existing production tables or columns during cleanup.

#### Scenario: Startup migration can be configured
- **WHEN** `AUTO_RUN_MIGRATIONS` is false
- **THEN** app startup skips automatic Alembic upgrade
- **AND** manual or platform-managed migrations can run separately

#### Scenario: Production SQLite remains blocked
- **WHEN** `ENV=production` and `DATABASE_URL` points to SQLite outside pytest
- **THEN** startup fails before serving requests

### Requirement: Backend tests use isolated database state
Backend tests MUST use a shared test database harness so tests do not depend on the developer SQLite file or production database URL.

#### Scenario: Test database URL is isolated
- **WHEN** pytest starts
- **THEN** the test configuration points SQLAlchemy at a test database
- **AND** tests can create/drop metadata without touching production configuration

### Requirement: Cleanup is evidence-based
The backend MUST remove or quarantine dead code, debug artifacts, and stale tests only when direct search or replacement tests prove they are unused or obsolete.

#### Scenario: Ambiguous code is preserved with guardrail
- **WHEN** a legacy helper still has runtime imports or migration value
- **THEN** cleanup keeps it and documents the removal condition instead of deleting it

#### Scenario: Debug snapshots are not committed as runtime state
- **WHEN** debug snapshots are generated for local diagnosis
- **THEN** they remain gated by configuration and are not required for automated tests

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

### Requirement: Removed backend modules stay removed
Backend cleanup MUST prevent known dead modules from being reintroduced after deletion.

#### Scenario: Dead module file exists
- **WHEN** a banned dead module file exists in `backend/app`
- **THEN** the backend dead-code checker fails and reports the module path

#### Scenario: Dead module import exists
- **WHEN** a backend Python file imports a banned dead module
- **THEN** the backend dead-code checker fails and reports the importer path

### Requirement: Unreferenced backend app modules are audited
Backend cleanup MUST fail when a `backend/app` Python module has no internal app importers unless the module is explicitly allowlisted with a reason that explains the retained contract or removal condition.

#### Scenario: New unreferenced module lacks reason
- **WHEN** a `backend/app` module has no internal `app.*` importers
- **AND** the module is not in the intentional unreferenced-module allowlist
- **THEN** the backend dead-code checker fails and reports the module path

#### Scenario: Intentional scaffold is documented
- **WHEN** a `backend/app` module is retained as a public contract, architecture scaffold, or migration-safe compatibility point
- **THEN** the backend dead-code checker allows it only when the allowlist stores a non-empty reason
