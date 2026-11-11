# Package import guard: keep ProductionService as the public package export while
# avoiding eager facade imports during production package initialization.
def __getattr__(name: str):
    if name == "ProductionService":
        from app.services.production.facade import ProductionService

        return ProductionService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Package export guard: static import users still see the same public facade name
# through Python's module attribute resolution.
__all__ = ["ProductionService"]
