# Prompt split guard: series prompts import the moved prompt source directly after
# core prompt compatibility shims have been removed.
from app.services.production.prompts.legacy import (
    SERIES_NEXT_EPISODE_PROMPT,
    SERIES_SUGGESTION_PROMPT,
)


# Prompt split guard: series prompts get a role-owned import path while endpoint
# imports remain unchanged until the application-service phase.
__all__ = [
    "SERIES_NEXT_EPISODE_PROMPT",
    "SERIES_SUGGESTION_PROMPT",
]
