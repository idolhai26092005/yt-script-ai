# ADR-0001: Production Role Graph

## Context

`ScriptProducer` currently owns orchestration, cache resume, prompt assembly, LLM calls, validation routing, SSE events, persistence, semantic verification, packaging, and fact-checking. Backend graphify marks it as the highest-connected backend node.

## Decision

Adopt a production role graph. Each screenplay step becomes a role with stable `role_name`, declared inputs, declared outputs, schema version, validation result, and rollback-safe SSE adaptation through the runner.

## Consequences

Benefits:

- Smaller reviewable modules.
- Role execution order becomes declarative.
- Optional roles can use no-op strategies instead of scattered conditionals.
- Observability can be role-aware.

Costs:

- Initial compatibility layer is needed while `ProductionService` keeps the old public surface.
- Characterization tests must protect current stream/cache/save behavior before extraction.

## Reversal Plan

Keep `ProductionService` and existing producer methods as compatibility seams. If role graph extraction regresses behavior, revert the latest role delegation PR and route calls back to the current producer method.
