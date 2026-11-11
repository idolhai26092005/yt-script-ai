# Prompt split guard: scene prompts import the moved prompt source directly after
# core prompt compatibility shims have been removed.
from app.services.production.prompts.legacy import (
    BASE_NEGATIVE_PROMPT,
    BATCH_SCENE_GENERATION_TEMPLATE,
    EMOTION_ARC_BASE_PROMPT,
    SHAPE_STRUCTURES,
)


# Prompt split guard: scene/beat prompts stay aliases during pure-move phase to
# prevent LLM behavior drift while imports migrate gradually.
__all__ = [
    "BASE_NEGATIVE_PROMPT",
    "BATCH_SCENE_GENERATION_TEMPLATE",
    "EMOTION_ARC_BASE_PROMPT",
    "SHAPE_STRUCTURES",
]
