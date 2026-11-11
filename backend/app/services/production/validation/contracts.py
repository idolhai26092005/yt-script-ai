# Compatibility export guard: validation contracts import the moved validation
# source directly after core validation shims have been removed.
from app.services.production.validation.legacy import (
    BLOCK,
    RETRY,
    WARN,
    SceneContract,
    ScriptContract,
    ValidationIssue,
)


# Compatibility export guard: validation contracts stay sourced from the moved
# legacy implementation until deeper rule extraction lands.
# Remove in Phase F after runtime/tests import production.validation directly.
__all__ = [
    "BLOCK",
    "RETRY",
    "WARN",
    "SceneContract",
    "ScriptContract",
    "ValidationIssue",
]
