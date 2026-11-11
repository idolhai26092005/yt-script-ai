## Why

Longform screenplay generation can drift away from the approved stage plan, as seen in Project 19 where early batches received all chapter context and generated Napoleon/Hitler scenes inside the Qin Shi Huang stage. Prior attempts to harden the emotion arc risked making generation appear stuck because arc chunks can retry multiple expensive LLM calls without a phase-level timeout.

## What Changes

- Persist the resolved `narrative_shape` from routing so canonical v3 snapshots and resume caches do not store `null` for strict historical content.
- Scope stage context by scene range so each longform batch receives only the applicable stage instead of every chapter header.
- Keep emotion arc validation lightweight: stage/person mismatches are recorded as warnings during arc generation and enforced later when concrete scene candidates exist.
- Add bounded LLM-call timing/timeout behavior for long-running production phases so slow provider calls surface as structured failures instead of silent stalls.
- Tighten fact-check completion semantics so malformed patches or unknown scene numbers cannot mark a strict historical run as successfully verified.
- Preserve public API, SSE event keys, canonical v3 shape, and existing cache compatibility unless a cache entry fails the new quality gates.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `youtube-script-ai`: Longform historical generation must preserve routed narrative shape, keep stage-specific scene generation aligned with scene ranges, avoid emotion-arc retry stalls, and fail strict verification cleanly when fact-check patches are invalid.

## Impact

- Affected code: `backend/app/services/production/producer.py`, `backend/app/services/production/base.py`, `backend/app/services/production/validation/legacy.py`, fact-check helpers, and related production tests.
- Affected artifacts: debug snapshots and canonical v3 saves will include non-null `topic.narrative_shape` when routing resolves one.
- Runtime compatibility: no frontend, API schema, SSE payload key, database schema, or dependency changes are planned.
