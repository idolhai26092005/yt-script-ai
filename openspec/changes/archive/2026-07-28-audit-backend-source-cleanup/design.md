## Context

The backend now has a dead-code checker for modules already proven unused and deleted. Remaining ambiguity is different: some modules can be unreferenced by runtime imports while still serving as public helper contracts, architecture placeholders, or migration-safe compatibility points.

## Goals / Non-Goals

**Goals:**
- Detect unreferenced `backend/app` modules with a deterministic static scan.
- Require every intentional exception to live in code with a reason.
- Keep the check cheap enough for local development and CI.

**Non-Goals:**
- No runtime import execution.
- No database or API behavior changes.
- No deletion of architecture scaffolds without separate evidence and tests.

## Decisions

- Use AST import scanning over `backend/app/**/*.py`.
  - Rationale: standard library only, deterministic, no environment or DB startup side effects.
  - Alternative: import modules dynamically; rejected because imports can execute settings, database, or provider code.
- Treat only `app` internal imports as references.
  - Rationale: this audit is about source module reachability inside runtime code, not test-only coverage.
  - Alternative: count test imports; rejected because tests can accidentally keep dead helpers alive.
- Use an explicit allowlist for intentional unreferenced modules.
  - Rationale: ambiguity stays visible and reviewable instead of being silently accepted.
  - Alternative: fail on every unreferenced module; rejected because planned architecture scaffolds would be deleted prematurely.

## Risks / Trade-offs

- False positives for dynamic imports -> keep allowlist with reasons and revisit when wiring changes.
- False negatives for symbol-level dead code -> this pass audits module reachability only; deeper symbol pruning can be separate.
- Allowlist drift -> tests assert reasons exist and checker fails when an unlisted module appears.
