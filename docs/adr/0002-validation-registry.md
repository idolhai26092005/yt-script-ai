# ADR-0002: Validation Registry

## Context

`app/core/validation.py` mixes contract dataclasses, schema adapters, story contract checks, scene checks, emotion arc checks, state machine checks, constraint checks, and historical coverage. Callers import a large module for narrow validation needs.

## Decision

Move validation into `backend/app/services/production/validation/` by concern: contracts, adapters, scene, story contract, emotion arc, constraints, and registry. The temporary `app.core.validation` compatibility re-export was removed after runtime and test imports migrated.

## Consequences

Benefits:

- Validators become easier to review by domain.
- Role runner can resolve phase validators declaratively.
- Stable `ValidationIssue.code` values improve retry feedback and phase logs.

Costs:

- Legacy implementation remains in `services.production.validation.legacy` until deeper rule extraction is safe.
- Rule order must be explicit in the registry to avoid hidden behavior changes.

## Reversal Plan

Because the byte-preserving implementation lives in `services.production.validation.legacy`, validator imports can be pointed back to that source file if package extraction causes regressions.
