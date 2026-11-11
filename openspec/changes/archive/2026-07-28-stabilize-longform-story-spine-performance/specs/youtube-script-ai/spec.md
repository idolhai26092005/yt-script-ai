## ADDED Requirements

### Requirement: Longform stage-scoped scene generation
The system MUST keep longform scene generation aligned with the scene ranges declared by the approved blueprint/story spine. Each scene batch MUST receive only the stage context that overlaps its requested scene numbers, while preserving the public API, SSE event keys, and canonical v3 output shape.

#### Scenario: Batch receives only matching historical chapter
- **WHEN** a 60-scene historical script has stages `1-20`, `21-40`, and `41-60`
- **THEN** the scene-generation prompt for scenes `1-10` includes only the stage overlapping scenes `1-10`
- **AND** it does not include later Napoleon or Hitler stage text

#### Scenario: Routed narrative shape is persisted
- **WHEN** the backend resolves a routing rule for a historical or scientific production run
- **THEN** the live work-state and canonical v3 save include the resolved `narrative_shape`
- **AND** the canonical topic metadata does not store `narrative_shape` as `null` when a routing default exists

### Requirement: Emotion arc generation remains bounded
The system MUST avoid strict emotion-arc retry loops for stage/person mismatch rules that are better validated after concrete scene candidates exist. Emotion arc generation MAY record advisory warnings for chapter drift, but it MUST NOT add additional LLM retries for those warnings.

#### Scenario: Arc mismatch warning does not trigger extra retry
- **WHEN** an emotion arc chunk contains a lead character that appears outside the expected stage range
- **THEN** the system records a warning for observability
- **AND** it does not retry the arc chunk solely because of that warning

#### Scenario: Scene candidate mismatch blocks later
- **WHEN** a generated scene candidate places a named historical figure in a stage range assigned to a different named figure
- **THEN** Phase 2 candidate validation rejects the scene candidate before it is accepted into final output

### Requirement: Production LLM calls are observable and bounded
The system MUST bound long-running production LLM calls with phase-level timeout handling and record latency context. Timeout failures MUST surface through the existing production error flow rather than leaving the stream apparently stalled.

#### Scenario: Slow provider call times out cleanly
- **WHEN** a production LLM call exceeds the configured timeout for its phase or chunk
- **THEN** the phase fails with a structured error through the existing stream safety path
- **AND** phase logs include enough context to identify the phase and scene range involved

### Requirement: Strict fact-check completion reflects scene-level verification
For historical and scientific production runs, the system MUST keep fact-check prompts scoped to the current chunk and MUST reject malformed, unknown, or invalid patches without merging them into the screenplay. Sparse successful patches remain allowed for unchanged accurate scenes, and completed Phase 4 runs MUST expose per-scene verification status.

#### Scenario: Unknown fact-check scene patch is rejected
- **WHEN** a fact-check chunk for scenes `1-12` returns a patch for scene `31`
- **THEN** the system rejects that patch and records a quality warning
- **AND** it does not merge the patch into any scene
- **AND** the production run does not fail solely because of the off-range patch

#### Scenario: Invalid correction patch becomes review status
- **WHEN** a fact-check correction patch still violates measurable scene gates after retry
- **THEN** the system preserves the original scene content
- **AND** marks the affected scene as `needs_review`
- **AND** final code validation still hard-fails if the resulting screenplay has schema, anchor, voice, or coverage errors
