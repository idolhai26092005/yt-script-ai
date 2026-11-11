# Compatibility export guard: historical validation imports the moved validation
# source directly after core validation shims have been removed.
from app.services.production.validation.legacy import validate_historical_coverage


# Compatibility export guard: historical coverage stays a legacy validator alias
# until fact-check role extraction owns this validation surface.
__all__ = ["validate_historical_coverage"]
