# Prompt split guard: semantic verifier imports the moved prompt source directly
# after core prompt compatibility shims have been removed.
from app.services.production.prompts.legacy import SEMANTIC_VERIFIER_PROMPT


# Prompt split guard: semantic verifier prompt remains byte-for-byte legacy text
# until verifier role extraction changes call sites explicitly.
__all__ = ["SEMANTIC_VERIFIER_PROMPT"]
