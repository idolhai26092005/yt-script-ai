from dataclasses import dataclass, field
from typing import Any

# Role contract guard: role result metadata imports validation contracts from the
# production package after core validation shims have been removed.
from app.services.production.validation.contracts import ValidationIssue
from app.services.production.ports import Clock, LLMClient, ScreenplayRepository, Sleeper


# Role contract guard: result metadata is introduced before orchestration changes
# so future roles can be reviewed against a stable, explicit output surface.
@dataclass(frozen=True)
class RoleResult:
    role_name: str
    schema_version: str
    artifacts: dict[str, Any]
    validation_issues: list[ValidationIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    retry_count: int = 0
    cache_hit: bool = False


# Role graph guard: role specs describe dependencies as data before any runner
# begins executing them, keeping this step behavior-free.
@dataclass(frozen=True)
class RoleSpec:
    role_name: str
    requires: tuple[str, ...]
    produces: tuple[str, ...]
    optional: bool = False
    enabled_by: str | None = None


# Role context guard: future role objects receive dependencies explicitly rather
# than reaching through ScriptProducer internals or concrete infrastructure.
@dataclass
class RoleContext:
    state: dict[str, Any]
    repo: ScreenplayRepository
    llm: LLMClient
    clock: Clock
    sleeper: Sleeper
    project_id: int
    model_name: str
    settings: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "RoleContext",
    "RoleResult",
    "RoleSpec",
]
