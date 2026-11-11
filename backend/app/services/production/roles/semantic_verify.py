from app.services.production.role_contracts import RoleContext, RoleResult, RoleSpec
from app.services.production.roles.base import ProductionRole


# Role delegation guard: semantic verifier role forwards to the current Phase 2.5
# method so advisory patching and rollback behavior stay unchanged.
class SemanticVerifierRole(ProductionRole):
    spec = RoleSpec(
        role_name="semantic_verifier",
        requires=("scenes",),
        produces=("quality_warnings",),
        optional=True,
        enabled_by="semantic_verifier_enabled",
    )

    # Async adapter guard: return value is the legacy edit count, not a RoleResult,
    # until verifier artifacts are moved into the role contract.
    async def run_legacy(self, *args, **kwargs) -> int:
        return await self.producer._phase25_semantic_verifier(*args, **kwargs)

    # Role contract guard: full RoleResult execution waits until semantic
    # verification output is represented as explicit artifacts.
    async def run(self, context: RoleContext) -> RoleResult:
        raise NotImplementedError("SemanticVerifierRole RoleResult execution is not extracted yet.")


__all__ = ["SemanticVerifierRole"]
