from app.services.production.role_contracts import RoleContext, RoleResult, RoleSpec
from app.services.production.roles.base import ProductionRole


# Role delegation guard: scene batch role forwards to the current Phase 2 method
# so cache replay, batching, and save cadence remain unchanged.
class SceneBatchRole(ProductionRole):
    spec = RoleSpec(
        role_name="scene_batch",
        requires=("prompt_0", "emotion_arc"),
        produces=("scenes",),
    )

    # Stream adapter guard: yielded scene events are produced by the legacy
    # ScriptProducer method, preserving exact SSE payloads.
    async def run_stream(self, *args, **kwargs):
        async for event in self.producer._phase2_batch_generate_scenes(*args, **kwargs):
            yield event

    # Role contract guard: full RoleResult execution waits until Phase 2 artifacts
    # are moved out of the legacy producer method.
    async def run(self, context: RoleContext) -> RoleResult:
        raise NotImplementedError("SceneBatchRole RoleResult execution is not extracted yet.")


__all__ = ["SceneBatchRole"]
