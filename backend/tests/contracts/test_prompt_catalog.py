from app.services.production.prompts.legacy import (
    BATCH_SCENE_GENERATION_TEMPLATE,
    PROMPT_0_GENERATION_TEMPLATE,
)
from app.services.production.prompts.catalog import PROMPT_CATALOG, PromptSpec, get_prompt_spec


# Catalog guard: prompt ids must resolve to moved legacy constants during
# pure-move migration so introducing metadata does not change prompt text.
def test_prompt_catalog_blueprint_and_scene_batch_metadata():
    blueprint = get_prompt_spec("blueprint.v1")
    scene_batch = get_prompt_spec("scene-batch.v1")

    assert isinstance(blueprint, PromptSpec)
    assert blueprint.owner_role == "blueprint"
    assert blueprint.expected_output_schema == "Prompt0Blueprint"
    assert blueprint.template is PROMPT_0_GENERATION_TEMPLATE
    assert scene_batch.owner_role == "scene_batch"
    assert scene_batch.expected_output_schema == "SceneBatchOutput"
    assert scene_batch.template is BATCH_SCENE_GENERATION_TEMPLATE


# Catalog guard: prompt ids should be stable and self-describing so reviewers can
# reason about prompt ownership without scanning the old monolithic prompt file.
def test_prompt_catalog_entries_keep_stable_ids_and_versions():
    assert PROMPT_CATALOG
    for prompt_id, spec in PROMPT_CATALOG.items():
        assert prompt_id == spec.prompt_id
        assert spec.version
        assert spec.owner_role
        assert spec.expected_output_schema
        assert spec.template
