## Context

The legacy series flow is disabled by default and lives mostly inside `app/api/v1/endpoints/series.py`. It creates a weak outline, stores it in legacy `series.series_outline`, generates episode suggestions with `ContextCompressor`, mutates the selected suggestion with rolling context, then calls `ProductionService.generate_full_script_stream`. This creates three recurring failures:

- Series behavior leaks into the single-video pipeline through `context_from_previous`, `series_bridge_vi`, legacy project reuse, and producer-side visual locks.
- Episode continuity is summarized after the fact, not planned as a first-class contract, so later episodes often restart, close too early, or ignore the previous ending state.
- The old route mixes API concerns, database writes, LLM calls, streaming, and cleanup, making it hard to test and hard to change without regressions.

The new flow replaces the legacy `/api/v1/series` behavior with v2. Legacy database tables remain for rollback and data preservation, but the runtime code path is rebuilt around dedicated series artifacts.

## Goals / Non-Goals

**Goals:**

- Build an independent series pipeline that does not call `ProductionService` or legacy series prompt/compressor code.
- Keep `/api/v1/series` as the public path while changing the contract to v2.
- Let users edit an episode brief before generation instead of forcing an LLM-generated list of 3 options.
- Support flexible `scene_count` per episode, including long episodes, with the same practical bounds as the current production pipeline.
- Reduce LLM calls by merging compatible planning phases and making optional review calls conditional.
- Make continuity between episodes explicit through structured handoff fields, not prose-only rolling summaries.
- Keep hard code validation narrow: structural/schema/runtime failures only. Use LLM review for creative continuity quality and mark weak outputs as `needs_review` instead of blocking all completion.
- Preserve deploy safety with add-only migrations and frontend hiding of the old series UI.

**Non-Goals:**

- Rebuild the frontend series UI in this change.
- Migrate legacy `series` and `episodes` rows into v2 tables.
- Delete legacy tables during the first v2 rollout.
- Refactor the single/longform `ProductionService` pipeline.
- Guarantee perfect creative quality through code-only validators.

## Decisions

### 1. Replace `/api/v1/series` with v2, do not add `/series-v2`

The old contract is already disabled and the frontend will be rebuilt later. Keeping the route path reduces future UI churn and avoids maintaining two parallel series APIs.

Alternative considered: expose `/api/v1/series-v2` beside `/api/v1/series`. Rejected because it keeps legacy naming alive, adds route/config surface, and does not help the current frontend, which must be hidden either way.

### 2. Add v2 tables instead of mutating legacy tables

Add `series_v2` and `series_episode_v2`. The old tables remain untouched. This keeps Supabase/Render migrations add-only, fast, and rollback-safe.

`series_v2` stores stable series-level artifacts:

- `api_key_id`
- `title`
- `premise`
- `style`
- `topic_type`
- `reality_binding_level`
- `default_scene_count`
- `scene_duration_sec`
- `target_episode_count`
- `status`
- `series_bible`
- `season_map`
- `created_at`
- `updated_at`

`series_episode_v2` stores per-episode artifacts:

- `series_id`
- `episode_number`
- `status`
- `title`
- `brief`
- `user_revision`
- `scene_count`
- `ending_mode`
- `episode_blueprint`
- `emotion_arc`
- `scenes`
- `review_report`
- `continuity_delta`
- `script_output`
- `phase_log`
- `created_at`
- `updated_at`

Use JSON/JSONB through the existing `json_column` helper. Use string statuses instead of DB enums for SQLite/Postgres portability.

### 3. Do not create Project rows for series episodes

Series v2 episodes save script output directly into `series_episode_v2.script_output`. This avoids coupling to project resume signatures, project CRUD, legacy `generation_mode`, and project deletion behavior.

Alternative considered: keep creating `Project` rows for episode scripts. Rejected because it reproduces the old coupling and makes series cleanup/reset risky.

### 4. Series setup uses one LLM call for Bible + Season Map

`S1 Series Bible + S2 Season Map` run in one call at series creation. The output must include stable visual/story contracts and all episode slots.

Returned artifact:

- `series_bible`: world rules, cast locks, visual anchor, style/tone, central conflict, reality constraints, forbidden drift.
- `season_map`: ordered `episode_slots[]`, each with episode goal, pressure increase, required reveal, required unresolved thread, intended next-start state, and allowed `ending_mode`.

This saves one call and gives every future episode a season-level source of truth.

### 5. Remove LLM-generated episode options

The old "3 suggestions" phase is removed. A pending episode exposes an `Episode Brief Gate` generated deterministically from `series_bible + season_map + prior continuity_delta`. The user may edit:

- `title`
- `premise`
- `must_include`
- `must_avoid`
- `scene_count`
- `ending_mode`
- `notes`

Generation begins only after the brief is accepted. This gives user control without spending a call on option generation.

### 6. Episode planning combines Blueprint + Emotion Arc

For each episode, one LLM call produces:

- `episode_blueprint`: episode-specific Prompt 0 extension, story contract, stage ranges, visual/audio constraints, handoff target, next-start promise.
- `emotion_arc`: exactly one beat per scene, with physical state end and scene lead.

This phase receives `series_bible`, the current `episode_slot`, the accepted `brief`, and recent structured `continuity_delta` records. It does not receive free-form rolling prose as its only context.

### 7. Scene generation remains batched and checkpointed

Scenes are generated in batches of up to 10. Each batch receives:

- compact approved series bible
- episode blueprint
- batch-local stage range
- batch-local emotion arc
- previous saved scene handoff
- unresolved thread target for the episode
- batch position rules

Each batch saves after successful structural validation. Reconnect/resume can replay saved scenes and generate only missing spans.

### 8. Non-final episodes use explicit ending modes

Supported ending modes:

- `open_loop`: the episode stops mid-problem with a clear next action.
- `soft_cliffhanger`: the episode resolves a local beat but exposes a stronger unresolved question.
- `hard_cliffhanger`: the final scene introduces immediate danger/reveal that must start the next episode.
- `season_finale`: only valid for the last episode or a user-marked finale.

Non-final episodes must return a `continuity_delta` with `next_start_state`, `open_threads`, and `handoff_strength`. Code does not reject creative wording by regex. The reviewer judges whether the ending is too closed.

### 9. Validation is narrow hard gate + soft quality review

Hard code gates:

- JSON parse succeeds.
- Required schema keys exist.
- `scene_count` matches.
- Scene numbers are unique and sequential.
- Required fields for scene rendering exist.
- `veo3_prompt_en` cites the approved anchor.
- `voice_over_en` exists.
- Empty LLM output is rejected.

Soft review:

- continuity strength
- whether a non-final episode closes too much
- episode-to-season-map alignment
- repeated scene intent
- character/world drift
- hook quality
- setup/payoff clarity

If soft review fails, retry once with targeted feedback. If still weak, save with `status=needs_review` and the review report. Do not silently accept poor continuity as completed.

### 10. LLM call budget

Series creation:

- 1 call: `series_bible + season_map`

Each episode:

- 1 call: `episode_blueprint + emotion_arc`
- `ceil(scene_count / 10)` calls: scene batches
- 0 or 1 call: continuity reviewer, only when non-final or when warnings exist
- 0 or N calls: fact-check chunks, only for strict historical/scientific content
- 0 or 1 call: packaging, configurable; can be deferred

Default behavior should keep a short episode at 2-3 calls and a 30-scene long episode at 4-5 calls before optional strict fact-check.

### 11. Service boundaries

Create `app/services/series_v2/`:

- `contracts.py`: typed artifact contracts and constants.
- `state.py`: v2 state factory and phase log helpers.
- `prompts.py`: versioned prompt templates owned by series v2.
- `repository.py`: database reads/writes for v2 only.
- `validators.py`: hard structural validators and soft review response validators.
- `generator.py`: orchestrates the v2 phase flow and streams SSE events.

The API endpoint stays a thin adapter: auth, request parsing, rate limit, dependency injection, streaming response.

Boundary tests must fail if `app/services/series_v2/` imports:

- `app.services.production.ProductionService`
- `app.api.v1.endpoints.series` legacy behavior
- `SERIES_SUGGESTION_PROMPT`
- `SERIES_NEXT_EPISODE_PROMPT`
- `ContextCompressor.build_rolling_context`
- `apply_rolling_context_to_suggestion`

Small helper imports from production support/base/validation are allowed only when they are stateless utilities.

## Risks / Trade-offs

- Breaking existing frontend calls → Hide series UI in this change and rebuild the UI against v2 later.
- New tables create duplicate series concepts → Keep legacy tables read-only/unused and document removal after v2 stabilizes.
- Soft review may allow weak but structurally valid scripts → Save `needs_review` with explicit review report instead of pretending completion.
- One-call blueprint+arc may be too large for very long episodes → Keep retry path and allow future split if prompt size/quality metrics prove it necessary.
- Avoiding Project rows removes current project detail UI reuse → Accepted because project coupling is the main source of legacy series debt.
- Fewer hard validators reduce deterministic rejection → Keep only technical hard gates and capture quality concerns in structured review artifacts.

## Migration Plan

1. Create OpenSpec artifacts and tests first.
2. Add v2 models and add-only migration.
3. Add v2 schemas, repository, service contracts, prompts, validators, and generator.
4. Replace `/api/v1/series` route implementation with v2 adapter behind `ENABLE_SERIES_FLOW`.
5. Hide current frontend series entry points.
6. Run backend tests through `backend/venv/bin/pytest`.
7. Run frontend build/lint when dependencies are available.
8. Run `graphify update .` after implementation.

Rollback:

- Disable `ENABLE_SERIES_FLOW` to unmount the v2 route.
- Legacy tables remain intact.
- The add-only migration can be downgraded by dropping only v2 tables if needed.

## Open Questions

- Exact frontend v2 UX is deferred.
- Packaging can be immediate or deferred in a later UI-backed optimization; this design keeps it configurable.
