from typing import Literal, TypedDict


SCHEMA_VERSION = "series.v2"
PHASE_SETUP = "series_setup"
PHASE_BRIEF = "episode_brief"
PHASE_PLANNING = "episode_planning"
PHASE_SCENES = "episode_scenes"
PHASE_REVIEW = "continuity_review"
PHASE_FACT_CHECK = "fact_check"
PHASE_PACKAGING = "packaging"
PHASE_CONTINUITY = "continuity_delta"
PHASE_FINAL = "final_persist"

STATUS_ACTIVE = "active"
STATUS_PENDING = "pending"
STATUS_GENERATING = "generating"
STATUS_COMPLETED = "completed"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_FAILED = "failed"

ENDING_OPEN_LOOP = "open_loop"
ENDING_SOFT_CLIFFHANGER = "soft_cliffhanger"
ENDING_HARD_CLIFFHANGER = "hard_cliffhanger"
ENDING_SEASON_FINALE = "season_finale"

STRICT_TOPIC_TYPES = {"historical", "scientific"}
MIN_SCENE_COUNT = 4
MAX_SCENE_COUNT = 200
SCENE_BATCH_SIZE = 10

EndingMode = Literal["open_loop", "soft_cliffhanger", "hard_cliffhanger", "season_finale"]


# Artifact contract guard: phase logs use a compact typed surface so tests can
# assert observability without reading provider prompts or raw secrets.
class PhaseLogEntry(TypedDict, total=False):
    phase: str
    role: str
    schema_version: str
    validation_status: str
    artifact_keys: list[str]
    validation_errors: list[str]
    warnings: list[str]
    latency_ms: float
    cache_hit: bool


# Continuity contract guard: non-final episodes pass structured handoff state
# forward instead of relying on prose summaries that caused legacy drift.
class ContinuityDelta(TypedDict, total=False):
    last_physical_state: str
    open_threads: list[str]
    new_constraints: list[str]
    next_start_state: str
    handoff_strength: str
    cliffhanger_fact: str
