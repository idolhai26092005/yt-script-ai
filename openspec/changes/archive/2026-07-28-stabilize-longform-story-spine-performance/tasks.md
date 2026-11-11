## 1. Routing And Stage Context

- [x] 1.1 Persist the resolved `narrative_shape` into `script_data` after routing and after compatible cache hydration.
- [x] 1.2 Add a range-overlap stage-context helper based on `story_spine.stage_ranges`.
- [x] 1.3 Replace `_extract_stage_context()` usage so each scene batch receives only overlapping stage text.
- [x] 1.4 Add a Project 19 regression test proving batches `1-10`, `21-30`, and `41-50` do not receive unrelated chapter text.

## 2. Bounded Arc And LLM Performance

- [x] 2.1 Add a production LLM timeout helper that records phase name, scene range, model, elapsed time, and timeout status.
- [x] 2.2 Route phase-level Gemini calls through the timeout helper without changing public method signatures.
- [x] 2.3 Keep stage/person mismatch checks advisory during emotion arc generation and ensure they do not trigger extra arc retries.
- [x] 2.4 Add tests proving arc mismatch warnings do not retry or block the arc chunk.

## 3. Scene Candidate Gates

- [x] 3.1 Add deterministic scene-stage mismatch validation for named historical figure stages after concrete scene candidates are generated.
- [x] 3.2 Wire the new validator into Phase 2 candidate validation as a blocking issue.
- [x] 3.3 Allow neutral summary/bridge scenes only when they do not place historical figures in the wrong stage or shared physical space.
- [x] 3.4 Add tests proving wrong-stage scene candidates block before merge.

## 4. Strict Fact-Check Completion

- [x] 4.1 Make unknown scene patches and malformed fact-check patches fail the affected chunk after retry.
- [x] 4.2 Keep `_fact_check_completed=false` when any strict historical/scientific fact-check chunk fails.
- [x] 4.3 Add tests for a chunk `1-12` returning scene `31` and verify the strict gate fails.
- [x] 4.4 Confirm sparse successful patches still mark unchanged accurate scenes as checked.

## 5. Verification

- [x] 5.1 Run targeted validation and longform tests.
- [x] 5.2 Run resume cache and semantic verifier tests.
- [x] 5.3 Run script producer/SSE tests covering historical generation.
- [x] 5.4 Inspect generated debug snapshots for non-null `topic.narrative_shape` and range-scoped stage context.

## 6. Generic Phase 4 Recovery

- [x] 6.1 Scope fact-check prompt payloads to chunk-local emotion arc, allowed scene numbers, and overlapping story-spine stages.
- [x] 6.2 Reject malformed or off-range fact-check patches without failing the whole chunk.
- [x] 6.3 Preserve baseline scenes and mark known invalid correction patches as `needs_review` after retry.
- [x] 6.4 Verify sparse success, invalid rewrite, unknown patch, API error, and post-merge hard-gate behavior.
