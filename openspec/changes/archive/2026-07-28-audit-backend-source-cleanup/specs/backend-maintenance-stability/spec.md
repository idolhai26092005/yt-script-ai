## ADDED Requirements

### Requirement: Unreferenced backend app modules are audited
Backend cleanup MUST fail when a `backend/app` Python module has no internal app importers unless the module is explicitly allowlisted with a reason that explains the retained contract or removal condition.

#### Scenario: New unreferenced module lacks reason
- **WHEN** a `backend/app` module has no internal `app.*` importers
- **AND** the module is not in the intentional unreferenced-module allowlist
- **THEN** the backend dead-code checker fails and reports the module path

#### Scenario: Intentional scaffold is documented
- **WHEN** a `backend/app` module is retained as a public contract, architecture scaffold, or migration-safe compatibility point
- **THEN** the backend dead-code checker allows it only when the allowlist stores a non-empty reason
