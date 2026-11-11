# Prompt split guard: packaging prompts import the moved prompt source directly
# after core prompt compatibility shims have been removed.
from app.services.production.prompts.legacy import (
    POST_GENERATION_SUGGESTION_PROMPT,
    REFERENCE_IMAGES_PROMPT,
)


# Prompt split guard: packaging/post-generation prompts are exported by role path
# without changing legacy imports or prompt text.
__all__ = [
    "POST_GENERATION_SUGGESTION_PROMPT",
    "REFERENCE_IMAGES_PROMPT",
]
