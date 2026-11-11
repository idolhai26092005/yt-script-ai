## ADDED Requirements

### Requirement: Series V2 uses a dedicated public contract
The system MUST expose series v2 behavior through `/api/v1/series` when series flow is enabled. The v2 API MUST use schemas that identify the response as `series.v2` and MUST NOT preserve the legacy series request or response shape.

#### Scenario: Series V2 route is available
- **WHEN** `ENABLE_SERIES_FLOW` is true and a client creates a series through `/api/v1/series`
- **THEN** the backend stores a v2 series record and returns a response with `schema_version` equal to `series.v2`

#### Scenario: Legacy payload is rejected
- **WHEN** a client sends a legacy-only series payload to `/api/v1/series`
- **THEN** the backend rejects the request with a client error before starting any LLM generation

### Requirement: Series setup produces a stable bible and season map
The system MUST generate a series-level `series_bible` and `season_map` before any episode script is generated. The setup output MUST define the stable identity, world, visual constraints, central conflict, target episode count, and ordered episode slots.

#### Scenario: Series setup succeeds
- **WHEN** a valid series creation request contains title, premise, style, episode count, default scene count, scene duration, and topic type
- **THEN** the backend performs one setup LLM call and stores `series_bible` and `season_map`
- **AND** `season_map.episode_slots` contains exactly the requested number of episode slots

#### Scenario: Series setup output is malformed
- **WHEN** the setup LLM response cannot be parsed or lacks required setup artifacts
- **THEN** the backend retries with specific schema feedback
- **AND** the backend fails with a structured error if all setup attempts fail
- **AND** the backend MUST NOT store fabricated fallback episode slots as successful output

### Requirement: Episode brief gate is user-editable and does not spend an LLM call
The system MUST replace the legacy three-option episode suggestion step with a deterministic episode brief gate. The brief MUST be derived from the series bible, season map slot, prior continuity deltas, and user revisions.

#### Scenario: Pending episode brief is prepared
- **WHEN** a client requests the next pending episode brief
- **THEN** the backend returns one editable brief with title, premise, must-include items, must-avoid items, scene count, ending mode, and notes
- **AND** no LLM call is required to create the brief

#### Scenario: User edits episode brief before generation
- **WHEN** a client submits edits for a pending episode brief
- **THEN** the backend stores the edits and uses the accepted brief as the only episode premise input for generation

### Requirement: Episodes support flexible scene counts
The system MUST allow each episode to carry its own `scene_count`. The scene count MUST be validated by numeric bounds and MUST drive blueprint, emotion arc, scene generation, progress, and final output counts.

#### Scenario: Long episode uses requested scene count
- **WHEN** a user accepts an episode brief with `scene_count` equal to 50
- **THEN** the episode blueprint and emotion arc target 50 scenes
- **AND** scene generation produces scenes numbered 1 through 50

#### Scenario: Scene count is out of bounds
- **WHEN** a user submits an episode brief with a scene count outside allowed bounds
- **THEN** the backend rejects the brief before any LLM generation

### Requirement: Episode generation is phase-based and observable
The system MUST generate each episode through explicit phases with persisted phase logs. Each phase log entry MUST include role name, schema version, validation result, latency, and produced artifact keys.

#### Scenario: Episode generation emits ordered phase events
- **WHEN** an episode generation stream starts
- **THEN** the backend emits progress events for episode planning, scene batches, optional review, optional verification, packaging, continuity delta, and completion

#### Scenario: Episode phase artifact is saved
- **WHEN** a phase completes successfully
- **THEN** the backend saves the phase artifact and appends a phase log entry before moving to the next phase

### Requirement: Episode planning combines blueprint and emotion arc
The system MUST create an episode-specific blueprint and complete emotion arc before scene generation. The planning phase MUST receive the accepted episode brief, current season slot, series bible, and prior continuity deltas.

#### Scenario: Episode planning succeeds
- **WHEN** episode generation begins for a pending episode
- **THEN** the backend performs one planning LLM call that returns `episode_blueprint` and `emotion_arc`
- **AND** the `emotion_arc` contains exactly one entry per requested scene

#### Scenario: Episode planning fails structural validation
- **WHEN** the planning response has missing required fields or wrong emotion arc count
- **THEN** the backend retries with the exact structural errors
- **AND** generation stops with a structured error after retry exhaustion

### Requirement: Scene generation is batched and resumable
The system MUST generate episode scenes in contiguous batches and checkpoint successful batches. A reconnect or retry MUST reuse valid saved scenes and generate only missing scene spans.

#### Scenario: Scene batches follow requested count
- **WHEN** an episode has `scene_count` equal to 24
- **THEN** the backend generates scene batches that cover scenes 1 through 24 exactly once

#### Scenario: Generation resumes after partial save
- **WHEN** an episode already has valid saved scenes 1 through 10 and generation is restarted
- **THEN** the backend replays the saved scenes and generates only scenes 11 through the final requested scene

### Requirement: Non-final episodes preserve forward continuity
The system MUST treat non-final episode endings as handoffs to later episodes. Every non-final completed episode MUST store a structured `continuity_delta` containing final physical state, open threads, next start state, handoff strength, and any new constraints introduced by the episode.

#### Scenario: Non-final episode completes with handoff
- **WHEN** episode 2 of a 5-episode series completes
- **THEN** the backend stores a `continuity_delta` with at least one open thread and a next start state for episode 3

#### Scenario: Final episode may resolve the season
- **WHEN** the last episode completes with ending mode `season_finale`
- **THEN** the backend allows the continuity delta to close the central season conflict

### Requirement: Validation separates technical hard gates from creative review
The system MUST hard-fail only technical or structural generation failures and MUST use soft review for creative continuity quality. Soft review failures MUST be stored as review reports and MAY mark the episode `needs_review`.

#### Scenario: Technical output is invalid
- **WHEN** an LLM response is empty, unparsable, missing required schema keys, has duplicate scene numbers, wrong scene count, missing voice text, or missing anchor citation
- **THEN** the backend blocks the phase and retries or fails with a structured error

#### Scenario: Creative continuity is weak
- **WHEN** the reviewer reports that a non-final episode resolves too much or has weak handoff pressure
- **THEN** the backend retries once with targeted feedback
- **AND** if the issue remains, the backend stores the script with `needs_review` and the reviewer report instead of silently marking it clean

### Requirement: Series V2 minimizes LLM calls
The system MUST avoid unnecessary LLM calls in normal series generation. The episode brief gate MUST be deterministic, setup MUST combine bible and season map, and semantic/fact review MUST be conditional.

#### Scenario: Short non-strict episode call budget
- **WHEN** a short non-strict episode is generated without quality warnings
- **THEN** the backend uses no episode-options call and limits generation to planning, scene batch generation, and optional packaging

#### Scenario: Strict topic review is conditional
- **WHEN** an episode topic type is historical or scientific
- **THEN** the backend runs fact verification
- **AND** when the topic is not strict and technical validation has no warnings requiring review, the backend skips fact verification

### Requirement: Series V2 remains independent from legacy series and single-video orchestration
The v2 series service MUST NOT import or call the legacy series endpoint, legacy series prompts, rolling-context mutation helper, legacy compressor rolling context, or `ProductionService`.

#### Scenario: Boundary import check passes
- **WHEN** tests inspect imports under `app/services/series_v2`
- **THEN** no module imports forbidden legacy or single-video orchestration dependencies

#### Scenario: Single-video generation remains isolated
- **WHEN** a direct production request uses `series_short` or `series_long`
- **THEN** the production endpoint rejects the request before constructing `ProductionService`
