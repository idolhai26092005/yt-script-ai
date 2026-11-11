# Compatibility export guard: emotion-arc validators import the moved validation
# source directly after core validation shims have been removed.
from app.services.production.validation.legacy import (
    emotion_arc_state_triggers,
    validate_emotion_arc_constraints,
    validate_emotion_arc_quality,
    validate_emotion_arc_state_machine,
)


# Compatibility export guard: emotion-arc validators expose the future module path
# while preserving current validation behavior exactly.
__all__ = [
    "emotion_arc_state_triggers",
    "validate_emotion_arc_constraints",
    "validate_emotion_arc_quality",
    "validate_emotion_arc_state_machine",
]
