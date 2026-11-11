from app.services.production.role_contracts import RoleContext, RoleResult, RoleSpec


# Role delegation guard: base stores the legacy producer so role adapters can
# call existing phase methods without moving or rewriting runtime logic.
class ProductionRole:
    spec: RoleSpec

    # Role delegation guard: producer is intentionally untyped here to avoid an
    # import cycle while this adapter layer remains a pure orchestration seam.
    def __init__(self, producer=None):
        self.producer = producer

    # Role contract guard: data-driven roles still expose the future runner
    # method even when stream-oriented adapters use narrower delegation methods.
    async def run(self, context: RoleContext) -> RoleResult:
        raise NotImplementedError


__all__ = ["ProductionRole"]
