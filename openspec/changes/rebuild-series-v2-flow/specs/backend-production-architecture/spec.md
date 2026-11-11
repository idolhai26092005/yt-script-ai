## ADDED Requirements

### Requirement: Series generation uses explicit phase contracts
Series generation MUST model each major series and episode step as a named phase with explicit input artifacts, output artifacts, schema version, validation result, and stable phase name.

#### Scenario: Series phase output is inspectable
- **WHEN** a series v2 phase completes
- **THEN** the persisted phase log identifies the phase name, schema version, produced artifact keys, validation errors or warnings, latency, and cache-hit status when applicable

#### Scenario: Episode phases run in contract order
- **WHEN** episode generation starts
- **THEN** scene generation does not start until the accepted brief, episode blueprint, and emotion arc artifacts are available

### Requirement: Series V2 dependency direction is enforced
Series v2 modules MUST follow a one-way dependency direction from API adapters to series application services to series contracts/repositories to shared infrastructure helpers. Series v2 core modules MUST NOT depend on legacy series orchestration or the single-video production facade.

#### Scenario: Forbidden dependency is introduced
- **WHEN** a module under `app/services/series_v2` imports `ProductionService`, legacy series prompts, legacy series endpoint helpers, or rolling context mutation helpers
- **THEN** the import-boundary test fails with the violating module path

#### Scenario: Endpoint remains thin
- **WHEN** `/api/v1/series` handles v2 requests
- **THEN** it performs HTTP concerns and delegates business behavior to the series v2 service layer
