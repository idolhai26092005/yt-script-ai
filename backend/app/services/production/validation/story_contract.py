# Compatibility export guard: story-contract validators import the moved
# validation source directly after core validation shims have been removed.
from app.services.production.validation.legacy import (
    detect_story_contract_batch_drift,
    validate_story_contract_issues,
)


# Compatibility export guard: story-contract validators get a role-specific path
# while implementation stays byte-for-byte legacy during pure-move migration.
__all__ = [
    "detect_story_contract_batch_drift",
    "validate_story_contract_issues",
]
