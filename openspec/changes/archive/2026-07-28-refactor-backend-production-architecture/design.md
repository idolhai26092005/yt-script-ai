## Context

Backend production code is currently concentrated in a small set of large modules. Backend-scoped graphify output from 2026-07-28 shows `ScriptProducer` as the top god node with 79 edges and `ProductionService` with 55 edges. Line-count evidence shows `producer.py` at 2603 lines, `validation.py` at 1090 lines, and `production_prompts.py` at 672 lines.

The production pipeline already has important contracts: role-like phases, repository abstraction, schema v2/v3 adapters, validation severity, SSE streaming, phase logs, and cache resume. The refactor must preserve these contracts while making code easier to review and extend.

## Goals / Non-Goals

**Goals:**

- Split production backend into reviewable modules with clear dependency direction.
- Preserve public FastAPI endpoints, response schemas, SSE event keys, cache compatibility, and canonical v3 persistence.
- Convert phase orchestration into a declarative role graph with explicit input/output contracts.
- Split validation and prompt code into registries and role-owned modules.
- Add PR, import-boundary, complexity, ADR/RFC, and test standards so future changes remain reviewable.

**Non-Goals:**

- No database schema migration for this refactor.
- No frontend behavior change.
- No LLM prompt behavior change during pure move phases.
- No new runtime dependency unless a later ADR proves it is necessary.
- No rewrite of the whole producer in one PR.

## Decisions

### Decision 1: Use strangler migration over big rewrite

Create new modules around the current producer, move one responsibility at a time, and keep compatibility re-exports until callers migrate.

Alternative considered: rewrite `ScriptProducer` directly into new role classes. Rejected because it would mix move and behavior change, making review and rollback hard.

### Decision 2: Keep `ProductionService` as public facade first

`ProductionService` remains the stable constructor and public import while it delegates to new application services and role runner internally.

Alternative considered: replace callers immediately with new orchestrator classes. Rejected because tests and endpoints import `ProductionService` widely.

### Decision 3: Model the pipeline as declarative role graph

Each role exposes `role_name`, `requires`, `produces`, and `run(context) -> RoleResult`. The runner handles ordering, phase logs, retry policy, and SSE adaptation.

Alternative considered: keep method-based linear phases. Rejected because adding or disabling a role still requires editing orchestration code.

### Decision 4: Split validation by contract and registry

Move contracts/adapters/rules into `services/production/validation/` and keep `app/core/validation.py` as compatibility re-export during migration.

Alternative considered: keep validators in `core/validation.py` and only group functions by comments. Rejected because import surface and review burden remain too large.

### Decision 5: Split prompts into prompt catalog

Move prompt templates into role-owned modules and register them in `PROMPT_CATALOG` with id, version, owner role, and expected output schema.

Alternative considered: keep constants in one prompt file. Rejected because prompt diffs remain difficult to review and version.

### Decision 6: Enforce dependency direction with tests first

Start with an AST-based pytest or lightweight import-boundary check before adding optional lint dependencies.

Alternative considered: add a new third-party import linter immediately. Rejected because the refactor can start without new dependency risk.

### Decision 7: Add ADRs only for architecture decisions

Use ADRs for role graph, validation registry, prompt catalog, and import boundaries. Do not require ADRs for small pure moves.

Alternative considered: require ADR for every PR. Rejected because it creates process noise.

## Risks / Trade-offs

- Big pure moves can hide behavior changes -> keep PR size budget, characterization tests, and diff labels.
- Compatibility shims can become permanent -> add compatibility clock and removal phase.
- Role graph abstraction can become too generic -> keep role interface minimal and driven by current pipeline contracts.
- Validation registry can obscure rule order -> registry entries must include phase and stable rule code.
- Prompt catalog can fragment context -> each prompt spec must declare owner role and expected output schema.
- Import-boundary tests can block legitimate shared helpers -> allow exceptions only through ADR or explicit allowlist.

## Migration Plan

1. Add characterization tests and ADR-0001 before runtime moves.
2. Extract producer state/cache/SSE/scene support modules with behavior unchanged.
3. Split validation package and keep compatibility re-export.
4. Split prompt catalog and keep compatibility re-export.
5. Introduce role objects behind `ProductionService`.
6. Thin endpoints into application services.
7. Remove stale shims after imports migrate.
8. After each backend code change, run targeted tests and `graphify update backend`.

Rollback strategy: each PR must preserve compatibility imports and public API. If a phase fails, revert the latest small PR or switch facade delegation back to the previous producer method.

## Open Questions

- Should import-boundary enforcement remain a custom pytest or become a dedicated tool later?
- Which golden screenplay samples should become regression fixtures?
- What exact line-count and complexity gate should CI enforce first without creating noisy failures?
