# ADR-0003: Prompt Catalog

## Context

`app/core/production_prompts.py` contains prompt templates and constants for multiple roles and content surfaces. Large prompt diffs are hard to review, version, and map to runtime owners.

## Decision

Move production prompts into role-owned prompt modules and register them through a prompt catalog with stable prompt id, version, owner role, and expected output schema. The temporary `app.core.production_prompts` compatibility re-export was removed after runtime and test imports migrated.

## Consequences

Benefits:

- Prompt diffs become smaller and role-scoped.
- Prompt metadata makes tests and reviews more precise.
- Future prompt versioning can happen without changing orchestration logic.

Costs:

- Catalog metadata must be kept in sync with prompt modules.
- Legacy prompt text remains in `services.production.prompts.legacy` until deeper role extraction is safe.

## Reversal Plan

Keep existing constants reachable from `services.production.prompts.legacy`. If catalog rollout fails, role code can keep importing legacy constants while prompt modules are revised.
