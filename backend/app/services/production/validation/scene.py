# Compatibility export guard: scene validators import the moved validation source
# directly after core validation shims have been removed.
from app.services.production.validation.legacy import (
    scene_state_triggers,
    validate_scene_generation_issues,
    validate_scene_generation_quality,
    validate_scene_stage_alignment,
    validate_scene_issues,
    validate_scene_lead_character,
)


# Compatibility export guard: scene validators are grouped by domain without
# changing rule implementation, order, severity, or retry behavior.
__all__ = [
    "scene_state_triggers",
    "validate_scene_generation_issues",
    "validate_scene_generation_quality",
    "validate_scene_stage_alignment",
    "validate_scene_issues",
    "validate_scene_lead_character",
]
