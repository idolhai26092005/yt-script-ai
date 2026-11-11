# backend-production-architecture Specification

## Purpose
TBD - created by archiving change refactor-backend-production-architecture. Update Purpose after archive.
## Requirements
### Requirement: Preserve public backend behavior during refactor
The backend MUST preserve existing public API behavior while production architecture is refactored, including endpoint paths, response schema shape, SSE event keys, project cache compatibility, phase log writes, and canonical v3 script persistence.

#### Scenario: Existing production endpoints remain compatible
- **WHEN** a client calls the existing script suggestion or full script generation endpoint during any migration phase
- **THEN** the backend returns the same public response shape and SSE event keys as before the refactor

#### Scenario: Existing cached scripts remain resumable
- **WHEN** a project contains an old v2-compatible or canonical v3 cached script
- **THEN** the production service can hydrate the cache and resume without forcing full regeneration solely because modules moved

### Requirement: Production pipeline uses explicit role contracts
The production pipeline MUST model each major screenplay step as a role with explicit input requirements, output artifacts, schema version, validation result, and stable role name.

#### Scenario: Role result is inspectable
- **WHEN** a production role completes successfully
- **THEN** it returns a result containing role name, schema version, produced artifact keys, validation issues, and warnings

#### Scenario: Role graph controls execution
- **WHEN** the pipeline runner executes production
- **THEN** it determines enabled roles and order from a declarative role graph instead of scattered conditional orchestration logic

### Requirement: Backend dependency direction is enforced
Backend modules MUST follow a one-way dependency direction from API adapters to application services to production/domain contracts to infrastructure ports. Endpoint modules MUST NOT import production role internals directly, and production roles MUST NOT call SQLAlchemy sessions directly.

#### Scenario: Import boundary check detects reverse dependency
- **WHEN** a backend module imports from a higher layer or bypasses an approved port
- **THEN** the import-boundary test or linter fails with the violating module path

#### Scenario: Endpoint stays a thin adapter
- **WHEN** an endpoint handles a production request
- **THEN** it performs HTTP concerns and delegates business behavior to an application service or facade

### Requirement: Validation rules are modular and declarative
Validation logic MUST be split by contract area and registered through a declarative registry. Compatibility imports from `app.core.validation` MUST remain available until migration cleanup.

#### Scenario: Validator registry runs phase rules
- **WHEN** a production phase needs validation
- **THEN** the runner can resolve validators by phase name and receive stable `ValidationIssue` objects with severity and code

#### Scenario: Legacy validation imports keep working
- **WHEN** existing tests or runtime modules import public validators from `app.core.validation`
- **THEN** those imports continue to work through compatibility re-exports during migration

### Requirement: Prompt templates are role-owned and versioned
Prompt templates MUST be split into role-owned modules and registered in a prompt catalog with prompt id, version, owner role, and expected output schema. Compatibility imports from `app.core.production_prompts` MUST remain available until migration cleanup.

#### Scenario: Prompt catalog resolves role prompt
- **WHEN** a production role needs a prompt template
- **THEN** it resolves the prompt from the catalog by stable prompt id and version

#### Scenario: Legacy prompt imports keep working
- **WHEN** existing tests or runtime modules import public prompt constants from `app.core.production_prompts`
- **THEN** those imports continue to work through compatibility re-exports during migration

### Requirement: Refactor changes are reviewable
Each refactor PR MUST follow reviewability budgets and labels: small runtime file count, bounded changed lines, one semantic move per PR, explicit diff label, test plan, and rollback note.

#### Scenario: PR mixes move and behavior change
- **WHEN** a refactor PR both moves code and changes behavior without a regression test and `behavior-change` label
- **THEN** the PR fails review checklist

#### Scenario: Compatibility shim has removal clock
- **WHEN** a compatibility shim is introduced
- **THEN** it documents why it exists and the migration phase after which it should be removed

### Requirement: Production observability remains role-aware
The backend MUST record enough role-level observability to debug production output without logging raw prompts or provider secrets by default.

#### Scenario: Phase log includes role metadata
- **WHEN** a production role saves its phase log
- **THEN** the log includes stage role, schema version, validation errors, latency, retry count, model name when available, cache-hit status when available, and artifact keys

#### Scenario: Sensitive debug data is gated
- **WHEN** debug snapshots or raw provider payloads are requested
- **THEN** they are controlled by configuration and scrub API keys or secrets before persistence

### Requirement: Migration is test-first and graph-scoped
The backend refactor MUST add or preserve tests that prove behavior before and after each migration phase, and backend graph data MUST be refreshed with backend scope after backend code changes.

#### Scenario: Targeted tests prove a migration phase
- **WHEN** a migration phase moves runtime code
- **THEN** targeted unit, characterization, contract, or integration tests pass for the affected behavior

#### Scenario: Backend graph is refreshed after backend code changes
- **WHEN** backend runtime code is changed as part of this refactor
- **THEN** `graphify update backend` is run and the backend graph artifacts are refreshed

