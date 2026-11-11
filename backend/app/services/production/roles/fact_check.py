from app.services.production.role_contracts import RoleContext, RoleResult, RoleSpec
from app.services.production.roles.base import ProductionRole


# Role delegation guard: fact-check role forwards to the current Phase 4 method
# so sparse patch merge, chunking, and rollback behavior stay unchanged.
class FactCheckRole(ProductionRole):
    spec = RoleSpec(
        role_name="fact_check",
        requires=("scenes",),
        produces=("fact_check_notes",),
        optional=True,
        enabled_by="fact_check_enabled",
    )

    # Stream adapter guard: yielded fact-check scene events come from the legacy
    # ScriptProducer method, preserving exact SSE framing.
    async def run_stream(self, *args, **kwargs):
        async for event in self.producer._phase4_fact_check(*args, **kwargs):
            yield event

    # Role contract guard: full RoleResult execution waits until fact-check
    # artifacts are moved out of the legacy producer method.
    async def run(self, context: RoleContext) -> RoleResult:
        raise NotImplementedError("FactCheckRole RoleResult execution is not extracted yet.")


# Role scaffold guard: fact-check no-op strategy models disabled fact-check paths
# without changing current historical/scientific producer behavior.
class NoopFactCheckRole(ProductionRole):
    spec = FactCheckRole.spec

    # No-op guard: disabled optional role returns metadata only and never mutates
    # production state.
    async def run(self, context: RoleContext) -> RoleResult:
        return RoleResult(
            role_name=self.spec.role_name,
            schema_version="3.0",
            artifacts={},
            warnings=["fact_check noop scaffold"],
            cache_hit=True,
        )


__all__ = ["FactCheckRole", "NoopFactCheckRole"]
