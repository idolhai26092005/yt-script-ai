from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Registry guard: import through the moved validation source so registry ownership
# follows the production package after core shim cleanup.
from app.services.production.validation.legacy import (
    blocking_messages,
    normalize_script,
    retryable_messages,
    validate_blueprint_required,
    validate_emotion_arc_constraints,
    validate_emotion_arc_quality,
    validate_historical_coverage,
    validate_scene_generation_issues,
    validate_script,
    validate_state_invariants,
    validate_story_contract_issues,
)
from app.services.production.validation.contracts import ValidationIssue


Validator = Callable[[dict[str, Any]], list[str] | list[ValidationIssue]]


# Registry guard: phase validator metadata lands before producer call sites move,
# preserving current order while giving future roles stable rule codes to target.
@dataclass(frozen=True)
class ValidatorSpec:
    code: str
    phase: str
    validator: Validator


# Registry guard: these wrapper functions call legacy validators exactly as
# producer.py does today; role runner adoption can swap call sites later.
def validate_phase0_blueprint(script_data: dict[str, Any]) -> list[str]:
    return (
        validate_blueprint_required(script_data)
        + retryable_messages(validate_story_contract_issues(script_data))
    )


# Registry guard: complete validation keeps current measurable script gates in
# one declarative list without changing runtime behavior yet.
def validate_complete_script(script_data: dict[str, Any]) -> list[str]:
    return (
        validate_script(normalize_script(script_data))
        + blocking_messages(validate_scene_generation_issues(script_data))
        + validate_historical_coverage(script_data)
    )


# Registry guard: state invariants stay callable through a phase wrapper so
# later roles can inject locked blueprint without depending on ScriptProducer.
def validate_state(script_data: dict[str, Any]) -> list[str]:
    return validate_state_invariants(script_data, None)


VALIDATOR_REGISTRY: dict[str, tuple[ValidatorSpec, ...]] = {
    "phase0_blueprint": (
        ValidatorSpec("blueprint_required", "phase0_blueprint", validate_blueprint_required),
        ValidatorSpec("story_contract", "phase0_blueprint", validate_story_contract_issues),
    ),
    "emotion_arc": (
        ValidatorSpec("emotion_arc_quality", "emotion_arc", lambda data: validate_emotion_arc_quality(data.get("emotion_arc", []), len(data.get("emotion_arc", []) or []))),
        ValidatorSpec("emotion_arc_constraints", "emotion_arc", validate_emotion_arc_constraints),
    ),
    "scene_batch": (
        ValidatorSpec("scene_generation_issues", "scene_batch", validate_scene_generation_issues),
    ),
    "complete": (
        ValidatorSpec("script_contract", "complete", validate_complete_script),
    ),
}


# Registry lookup guard: callers receive immutable tuples so runtime code cannot
# mutate global validator order while role graph migration is in progress.
def get_validators(phase: str) -> tuple[ValidatorSpec, ...]:
    return VALIDATOR_REGISTRY.get(phase, ())


__all__ = [
    "VALIDATOR_REGISTRY",
    "Validator",
    "ValidatorSpec",
    "get_validators",
    "validate_complete_script",
    "validate_phase0_blueprint",
    "validate_state",
]
