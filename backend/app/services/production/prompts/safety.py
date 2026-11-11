from app.core.safety import VEO3_CONTENT_SAFETY_RULES


# Prompt split guard: safety rules stay sourced from core.safety because they are
# shared policy text, but production prompts can import through role package later.
__all__ = ["VEO3_CONTENT_SAFETY_RULES"]

