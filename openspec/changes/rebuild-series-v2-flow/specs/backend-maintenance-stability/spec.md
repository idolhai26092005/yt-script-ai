## MODIFIED Requirements

### Requirement: Series flow is feature-gated
The backend MUST be able to disable series creation, episode brief editing, episode generation, and legacy series compatibility paths without removing database schema or affecting single and longform generation. When enabled, `/api/v1/series` MUST mount the v2 series implementation, not the legacy beta implementation.

#### Scenario: Series router disabled
- **WHEN** `ENABLE_SERIES_FLOW` is false
- **THEN** `/api/v1/series` routes are not mounted
- **AND** `/api/v1/production` routes remain mounted

#### Scenario: Series router enabled mounts v2
- **WHEN** `ENABLE_SERIES_FLOW` is true
- **THEN** `/api/v1/series` routes are mounted using the v2 series implementation
- **AND** legacy series endpoint orchestration is not imported by the router

#### Scenario: Series modes blocked from production endpoint
- **WHEN** a production script request uses `series_short` or `series_long`
- **THEN** the backend rejects the request before calling the production pipeline
- **AND** the rejection explains that series generation must use `/api/v1/series`

#### Scenario: Legacy tables remain available for rollback
- **WHEN** the v2 series migration is applied
- **THEN** existing `series`, `episodes`, and `projects` table columns are not dropped or rewritten
