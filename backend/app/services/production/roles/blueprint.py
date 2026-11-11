from app.services.production.role_contracts import RoleContext, RoleResult, RoleSpec
from app.services.production.roles.base import ProductionRole


# Role delegation guard: blueprint role forwards to the current Phase 0 method
# so orchestration can depend on a role without changing prompt/gate behavior.
class BlueprintRole(ProductionRole):
    spec = RoleSpec(
        role_name="blueprint",
        requires=("request",),
        produces=("prompt_0", "story_contract", "production_plan"),
    )

    # Stream adapter guard: this method yields the exact legacy SSE strings from
    # ScriptProducer._phase0_prompt0_and_blueprint.
    async def run_stream(
        self,
        suggestion,
        style,
        num_scenes,
        scene_duration_sec,
        is_historical,
        model_name,
        script_data,
        project_id,
        topic_type,
        context_from_previous=None,
    ):
        async for event in self.producer._phase0_prompt0_and_blueprint(
            suggestion,
            style,
            num_scenes,
            scene_duration_sec,
            is_historical,
            model_name,
            script_data,
            project_id,
            topic_type,
            context_from_previous=context_from_previous,
        ):
            yield event

    # Role contract guard: full RoleResult execution waits until Phase 0 output
    # artifacts are moved out of the legacy producer method.
    async def run(self, context: RoleContext) -> RoleResult:
        raise NotImplementedError("BlueprintRole RoleResult execution is not extracted yet.")


__all__ = ["BlueprintRole"]
