# Prompt split guard: fact-check prompts import the moved prompt source directly
# after core prompt compatibility shims have been removed.
from app.services.production.prompts.legacy import (
    HISTORICAL_FACT_CHECK_PROMPT,
    HISTORICAL_SCIENTIFIC_HARD_RULES,
)


# Prompt split guard: fact-check prompts remain aliases so historical/scientific
# validation behavior does not change during module extraction.
__all__ = [
    "HISTORICAL_FACT_CHECK_PROMPT",
    "HISTORICAL_SCIENTIFIC_HARD_RULES",
]
