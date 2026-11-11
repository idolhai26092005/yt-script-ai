## ADDED Requirements

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
