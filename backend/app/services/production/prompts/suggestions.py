# Prompt split guard: suggestion prompts import the moved prompt source directly
# after core prompt compatibility shims have been removed.
from app.services.production.prompts.legacy import (
    SYSTEM_PROMPT_GENERATE_SUGGESTIONS,
    SYSTEM_PROMPT_TOPIC_SUGGESTIONS,
)


# Prompt split guard: suggestion prompts remain aliases during catalog rollout
# so creative suggestion behavior is not changed by architecture work.
__all__ = [
    "SYSTEM_PROMPT_GENERATE_SUGGESTIONS",
    "SYSTEM_PROMPT_TOPIC_SUGGESTIONS",
]
