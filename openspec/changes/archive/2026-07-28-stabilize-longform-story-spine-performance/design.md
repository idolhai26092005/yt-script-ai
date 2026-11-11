## Context

Project 19 exposed a longform pipeline failure pattern: the blueprint declared three 20-scene historical chapters, but scene generation drifted across chapters because each batch could receive all stage headers. The same run also persisted `topic.narrative_shape` as `null`, carried a semantic warning into packaging, and showed fact-check state inconsistencies between snapshots.

The risky part is performance. Emotion arc generation already runs in 20-scene chunks with up to three LLM attempts per chunk, plus an extra retry when an arc is too flat. Moving strict chapter validation into the arc phase can multiply retries before any concrete scene text exists, making the stream appear stuck at the arc step.

## Goals / Non-Goals

**Goals:**

- Keep longform historical batches aligned with the stage range assigned by the blueprint/story spine.
- Persist routed narrative metadata into canonical v3 saves.
- Avoid adding strict arc-phase retry loops that increase latency or create apparent hangs.
- Bound slow LLM provider calls with observable timeout/latency information.
- Make strict historical fact-check failures explicit and non-successful.

**Non-Goals:**

- No public API, SSE payload key, frontend, database schema, or dependency change.
- No full rewrite of the producer or role graph.
- No global full-script fact-check redesign in this change.
- No attempt to make the LLM rewrite an already-bad emotion arc through unlimited retries.

## Decisions

### Decision 1: Persist routing once at orchestration start

Set `script_data["narrative_shape"]` from the resolved routing rule immediately after `resolve_routing()` and after cache hydration. Historical/scientific topics use the routing default; soft topics continue to honor suggestion shape fallback.

Alternative considered: infer shape again inside `to_canonical_v3()`. Rejected because persistence should reflect the live work-state contract and should be visible to validators before save.

### Decision 2: Scope stage context from `story_spine.stage_ranges`

Replace the string-scanning stage extractor with a helper that returns only stage ranges overlapping the requested scene span. For Project 19, scenes 1-10 receive only the Qin Shi Huang stage, scenes 21-30 only Napoleon, and scenes 41-50 only Hitler.

Alternative considered: improve prompt wording while still passing all stages. Rejected because it keeps irrelevant chapter text in the prompt and wastes tokens.

### Decision 3: Keep arc validation advisory for chapter mismatch

Emotion arc chunk validation may log stage/lead mismatch warnings but MUST NOT trigger additional LLM retries for that rule. The hard gate runs during scene candidate validation, where concrete `action_detail_vi`, `veo3_prompt_en`, and lead character evidence exist.

Alternative considered: hard-block arc chunks. Rejected because it caused the likely “stuck at arc” behavior: three chunks times multiple LLM calls before any scene can be reused.

### Decision 4: Add phase-level LLM timeout wrapper

Wrap production LLM calls with a bounded timeout helper that logs phase name, chunk/range, model, elapsed time, and timeout status. Timeout should fail the current phase cleanly through existing gate/error SSE handling.

Alternative considered: rely on provider SDK/network timeout. Rejected because current code does not provide a clear phase-level timeout contract or user-visible failure point.

### Decision 5: Fact-check invalid patches are rejected at patch granularity

If a fact-check chunk returns unknown scene numbers, malformed patches, or invalid correction patches after retry, the backend must reject only those patches, preserve the last valid scene baseline, and mark affected known scenes as `needs_review` when the fact-check attempt targeted them. `_fact_check_completed=true` means the Phase 4 role finished; per-scene `verification_status` distinguishes `checked`, `corrected`, and `needs_review`.

Alternative considered: fail the whole chunk after retry. Rejected after Project 20 because chunk-local fact-check prompts still contained full-script emotion arc context, making off-range patches likely and causing safe baseline scenes to abort the run.

## Risks / Trade-offs

- Stricter scene-stage checks may reject usable creative cross-cutting scenes → allow neutral summary/bridge scenes only when they do not place named figures in the wrong stage or shared physical space.
- Timeout values that are too low may fail valid slow provider calls → choose a conservative default and make it configurable in code constants.
- Cache entries created before this change may fail new quality gates → regenerate affected phases instead of silently accepting stale drift.
- Fact-check patch-level recovery can finish a run with `needs_review` scenes → prefer transparent per-scene review over aborting a safe baseline or pretending all scenes are checked.

## Migration Plan

1. Add unit tests for Project 19 stage-context extraction and routed narrative shape persistence.
2. Add the LLM timeout helper and use it from production phase calls without changing public signatures.
3. Move stage/person hard checks into scene candidate validation and leave arc mismatch as warnings.
4. Make fact-check prompts chunk-local and reject bad patches without failing safe baseline scenes.
5. Run targeted backend tests for validation, longform production, resume cache, semantic verifier, script producer, and SSE.
6. Rollback by removing the new validators/timeout wrapper and restoring the previous stage extractor; public API rollback is not required because no API contract changes are introduced.

## Open Questions

- Final timeout value should be selected during implementation based on observed Gemini latency in local runs.
- Existing old snapshots with `narrative_shape=null` can remain historical artifacts; runtime cache migration only needs to hydrate future runs correctly.
