# Compatibility export guard: adapters import the moved validation source directly
# after core validation shims have been removed.
from app.services.production.validation.legacy import (
    normalize_scene,
    normalize_script,
)


# Compatibility export guard: adapters remain aliases to the moved legacy module
# so contract tests can adopt the new path before logic physically moves.
# Phase F is complete for core shim cleanup; keep this alias while deeper rule
# extraction remains byte-for-byte legacy.
__all__ = [
    "normalize_scene",
    "normalize_script",
]
