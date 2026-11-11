from app.services.production.role_contracts import RoleContext, RoleResult, RoleSpec
from app.services.production.roles.base import ProductionRole


# Role delegation guard: packaging role forwards to the current Phase 3 method
# so reference prompt generation and series bridge behavior stay unchanged.
class PackagingRole(ProductionRole):
    spec = RoleSpec(
        role_name="packaging",
        requires=("scenes",),
        produces=("reference_images",),
        optional=True,
        enabled_by="packaging_enabled",
    )

    # Stream adapter guard: yielded packaging progress comes from the legacy
    # ScriptProducer method, preserving exact SSE framing.
    async def run_stream(self, *args, **kwargs):
        async for event in self.producer._phase3_packaging(*args, **kwargs):
            yield event

    # Role contract guard: full RoleResult execution waits until packaging
    # artifacts are moved out of the legacy producer method.
    async def run(self, context: RoleContext) -> RoleResult:
        raise NotImplementedError("PackagingRole RoleResult execution is not extracted yet.")


# Role scaffold guard: packaging no-op strategy can represent disabled/cached
# packaging without affecting current producer-controlled packaging logic.
class NoopPackagingRole(ProductionRole):
    spec = PackagingRole.spec

    # No-op guard: disabled optional role returns metadata only and never mutates
    # production state.
    async def run(self, context: RoleContext) -> RoleResult:
        return RoleResult(
            role_name=self.spec.role_name,
            schema_version="3.0",
            artifacts={},
            warnings=["packaging noop scaffold"],
            cache_hit=True,
        )


__all__ = ["PackagingRole", "NoopPackagingRole"]
