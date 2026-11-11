## ADDED Requirements

### Requirement: Removed backend modules stay removed
Backend cleanup MUST prevent known dead modules from being reintroduced after deletion.

#### Scenario: Dead module file exists
- **WHEN** a banned dead module file exists in `backend/app`
- **THEN** the backend dead-code checker fails and reports the module path

#### Scenario: Dead module import exists
- **WHEN** a backend Python file imports a banned dead module
- **THEN** the backend dead-code checker fails and reports the importer path
