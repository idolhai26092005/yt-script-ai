# Prompt split guard: compression imports the moved prompt source directly after
# core prompt compatibility shims have been removed.
from app.services.production.prompts.legacy import CONTEXT_COMPRESSION_PROMPT


# Prompt split guard: compression prompt gets role-owned path while prompt text
# remains byte-for-byte legacy content.
__all__ = ["CONTEXT_COMPRESSION_PROMPT"]
