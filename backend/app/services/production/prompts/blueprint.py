# Prompt split guard: blueprint imports the moved prompt source directly after
# core prompt compatibility shims have been removed.
from app.services.production.prompts.legacy import PROMPT_0_GENERATION_TEMPLATE


# Prompt split guard: role-owned module aliases the moved legacy constant so
# prompt text stays byte-for-byte unchanged.
__all__ = ["PROMPT_0_GENERATION_TEMPLATE"]
