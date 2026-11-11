from app.services.production.role_contracts import RoleContext, RoleResult, RoleSpec
from app.services.production.roles.base import ProductionRole


# Role delegation guard: emotion arc role forwards to the current Phase 1 method
# so chunking, retry, and validation behavior stay unchanged.
class EmotionArcRole(ProductionRole):
    spec = RoleSpec(
        role_name="emotion_arc",
        requires=("prompt_0", "story_spine"),
        produces=("emotion_arc",),
    )

    # Stream adapter guard: kwargs mirror the legacy generator signature so
    # chunked and non-chunked call sites can delegate without branching changes.
    async def run_stream(self, *args, **kwargs):
        async for event in self.producer._phase1_generate_emotion_arc(*args, **kwargs):
            yield event

    # Role contract guard: full RoleResult execution waits until Phase 1 artifacts
    # are moved out of the legacy producer method.
    async def run(self, context: RoleContext) -> RoleResult:
        raise NotImplementedError("EmotionArcRole RoleResult execution is not extracted yet.")


__all__ = ["EmotionArcRole"]
