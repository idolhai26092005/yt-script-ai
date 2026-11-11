## ADDED Requirements

### Requirement: Legacy series UI is hidden during V2 backend transition
The frontend MUST hide entry points that call the legacy series API until the rebuilt series UI targets the v2 `/api/v1/series` contract.

#### Scenario: Series navigation is hidden
- **WHEN** the frontend renders navigation during the v2 backend transition
- **THEN** the old Series page navigation item is not shown to users

#### Scenario: Series generation modes are hidden
- **WHEN** the frontend renders the production mode selector during the v2 backend transition
- **THEN** `series_short` and `series_long` are not selectable

#### Scenario: Direct series page access does not call legacy API
- **WHEN** a user reaches the old Series page state during the v2 backend transition
- **THEN** the frontend does not call legacy `/api/v1/series` endpoints
