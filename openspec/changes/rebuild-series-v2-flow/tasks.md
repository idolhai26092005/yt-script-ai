## 1. Guardrails First

- [x] 1.1 Add failing API tests for `/api/v1/series` disabled when `ENABLE_SERIES_FLOW=false` and mounted as v2 when true.
- [x] 1.2 Add import-boundary test that forbids `app/services/series_v2` from importing `ProductionService`, legacy series prompts, legacy series endpoint helpers, `ContextCompressor.build_rolling_context`, or `apply_rolling_context_to_suggestion`.
- [x] 1.3 Add schema contract tests for v2 create request, episode brief update request, series response, episode response, stream event payloads, and rejection of legacy-only payloads.
- [x] 1.4 Add service tests with fake LLM responses for setup, episode planning, scene batch generation, soft review, and continuity delta persistence.

## 2. Database And Models

- [x] 2.1 Add SQLAlchemy models for `SeriesV2` and `SeriesEpisodeV2` using `json_column` for artifacts and string statuses for portability.
- [x] 2.2 Register v2 models in `app/models/__init__.py` so metadata and tests discover them.
- [x] 2.3 Add Alembic migration that creates only `series_v2` and `series_episode_v2` tables plus indexes/unique constraints.
- [x] 2.4 Add migration tests proving upgrade creates v2 tables and does not drop or rewrite legacy `series`, `episodes`, or `projects` fields.

## 3. Series V2 Contracts

- [x] 3.1 Add `app/schemas/series_v2.py` with create, brief, episode, generation, review, and response schemas carrying `schema_version="series.v2"`.
- [x] 3.2 Add `app/services/series_v2/contracts.py` with artifact constants, phase names, status values, ending modes, and typed artifact shapes.
- [x] 3.3 Add `app/services/series_v2/state.py` for state factory, phase log entries, scene-count bounds, and deterministic episode brief construction.
- [x] 3.4 Add `app/services/series_v2/repository.py` for create/list/detail/update operations over v2 tables only.

## 4. Prompts And Validation

- [x] 4.1 Add `app/services/series_v2/prompts.py` with versioned prompts for setup, episode planning, scene batches, soft continuity review, optional fact verification, and optional packaging.
- [x] 4.2 Ensure every new prompt asks for raw JSON only, positive-first visual constraints, anchor citation, concise audio layer, and explicit episode handoff artifacts.
- [x] 4.3 Add hard validators for parseability, required keys, scene count, sequential scene numbers, required scene fields, voice text, and anchor citation.
- [x] 4.4 Add soft review response validation that requires `handoff_strength`, `open_threads`, `next_start_state`, and reviewer notes without regex-blocking creative wording.
- [x] 4.5 Add one retry path per LLM phase that injects exact structural or reviewer feedback and fails structured after retry exhaustion.

## 5. Generation Service

- [x] 5.1 Add `SeriesV2Generator` using shared Gemini retry/fallback and timeout handling without calling `ProductionService`.
- [x] 5.2 Implement setup phase: one call creates `series_bible` and `season_map`, validates exact episode slot count, and persists artifacts.
- [x] 5.3 Implement episode brief gate: deterministic brief from `series_bible`, current slot, prior `continuity_delta`, defaults, and user edits; no LLM call.
- [x] 5.4 Implement episode planning phase: one call creates `episode_blueprint` and full `emotion_arc` for the accepted scene count.
- [x] 5.5 Implement scene batch phase with batch size 10, previous saved scene handoff, per-batch checkpoint save, and resume for missing spans.
- [x] 5.6 Implement optional soft reviewer: run for non-final episodes or warnings, retry once on weak handoff, and save `needs_review` if still weak.
- [x] 5.7 Implement optional strict fact verification only for historical/scientific topics, using chunked patches and validation-before-merge.
- [x] 5.8 Implement continuity delta finalization with `last_physical_state`, `open_threads`, `new_constraints`, `next_start_state`, `handoff_strength`, and `cliffhanger_fact`.
- [x] 5.9 Implement final persistence, status transitions, quota increment after successful generation, and structured SSE `error` events through shared stream safety.

## 6. API And Frontend Transition

- [x] 6.1 Replace legacy `app/api/v1/endpoints/series.py` implementation with a thin v2 adapter over the series v2 service.
- [x] 6.2 Update router behavior so `ENABLE_SERIES_FLOW=true` mounts v2 `/series` and false unmounts it.
- [x] 6.3 Keep direct `/production/script/generate` rejection for `series_short` and `series_long`, with message pointing to `/api/v1/series`.
- [x] 6.4 Hide frontend Series navigation, old series modes, and direct calls to legacy `/series` until the rebuilt UI is implemented.
- [x] 6.5 Update or remove legacy series tests so they protect isolation only, while behavior tests target v2.

## 7. Verification

- [x] 7.1 Run `backend/venv/bin/pytest` from `backend`.
- [x] 7.2 Run frontend build and lint when frontend dependencies are available.
- [x] 7.3 Run `openspec status --change "rebuild-series-v2-flow"` and confirm artifacts remain apply-ready.
- [x] 7.4 Run `graphify update .` after implementation code changes.
- [x] 7.5 Review `git diff` for accidental legacy table drops, frontend dead calls, and forbidden imports before commit.
