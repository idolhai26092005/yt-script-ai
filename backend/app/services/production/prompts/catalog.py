from dataclasses import dataclass
from typing import Mapping

# Prompt catalog guard: import through role-owned prompt modules so catalog
# ownership follows the production package after core shim cleanup.
from app.services.production.prompts.blueprint import PROMPT_0_GENERATION_TEMPLATE
from app.services.production.prompts.compression import CONTEXT_COMPRESSION_PROMPT
from app.services.production.prompts.fact_check import HISTORICAL_FACT_CHECK_PROMPT
from app.services.production.prompts.packaging import (
    POST_GENERATION_SUGGESTION_PROMPT,
    REFERENCE_IMAGES_PROMPT,
)
from app.services.production.prompts.scenes import (
    BATCH_SCENE_GENERATION_TEMPLATE,
    EMOTION_ARC_BASE_PROMPT,
)
from app.services.production.prompts.series import (
    SERIES_NEXT_EPISODE_PROMPT,
    SERIES_SUGGESTION_PROMPT,
)
from app.services.production.prompts.suggestions import (
    SYSTEM_PROMPT_GENERATE_SUGGESTIONS,
    SYSTEM_PROMPT_TOPIC_SUGGESTIONS,
)
from app.services.production.prompts.verifier import SEMANTIC_VERIFIER_PROMPT


# Prompt catalog guard: prompt metadata is introduced before prompt text moves so
# review tooling can adopt stable ids without changing LLM behavior.
@dataclass(frozen=True)
class PromptSpec:
    prompt_id: str
    version: str
    owner_role: str
    template: str
    expected_output_schema: str


# Prompt catalog guard: every entry points at role-owned aliases backed by the
# moved legacy text, keeping prompt bytes unchanged during pure extraction.
PROMPT_CATALOG: Mapping[str, PromptSpec] = {
    "suggestions.v1": PromptSpec(
        prompt_id="suggestions.v1",
        version="1",
        owner_role="idea_suggester",
        template=SYSTEM_PROMPT_GENERATE_SUGGESTIONS,
        expected_output_schema="ScriptSuggestion[]",
    ),
    "topic-suggestions.v1": PromptSpec(
        prompt_id="topic-suggestions.v1",
        version="1",
        owner_role="topic_suggester",
        template=SYSTEM_PROMPT_TOPIC_SUGGESTIONS,
        expected_output_schema="str",
    ),
    "blueprint.v1": PromptSpec(
        prompt_id="blueprint.v1",
        version="1",
        owner_role="blueprint",
        template=PROMPT_0_GENERATION_TEMPLATE,
        expected_output_schema="Prompt0Blueprint",
    ),
    "emotion-arc.v1": PromptSpec(
        prompt_id="emotion-arc.v1",
        version="1",
        owner_role="emotion_arc",
        template=EMOTION_ARC_BASE_PROMPT,
        expected_output_schema="EmotionArcEntry[]",
    ),
    "scene-batch.v1": PromptSpec(
        prompt_id="scene-batch.v1",
        version="1",
        owner_role="scene_batch",
        template=BATCH_SCENE_GENERATION_TEMPLATE,
        expected_output_schema="SceneBatchOutput",
    ),
    "semantic-verifier.v1": PromptSpec(
        prompt_id="semantic-verifier.v1",
        version="1",
        owner_role="semantic_verifier",
        template=SEMANTIC_VERIFIER_PROMPT,
        expected_output_schema="SemanticVerifierOutput",
    ),
    "packaging.v1": PromptSpec(
        prompt_id="packaging.v1",
        version="1",
        owner_role="packaging",
        template=REFERENCE_IMAGES_PROMPT,
        expected_output_schema="ReferenceImages",
    ),
    "fact-check.v1": PromptSpec(
        prompt_id="fact-check.v1",
        version="1",
        owner_role="fact_check",
        template=HISTORICAL_FACT_CHECK_PROMPT,
        expected_output_schema="FactCheckPatchSet",
    ),
    "series-suggestion.v1": PromptSpec(
        prompt_id="series-suggestion.v1",
        version="1",
        owner_role="series",
        template=SERIES_SUGGESTION_PROMPT,
        expected_output_schema="SeriesSuggestion[]",
    ),
    "series-next-episode.v1": PromptSpec(
        prompt_id="series-next-episode.v1",
        version="1",
        owner_role="series",
        template=SERIES_NEXT_EPISODE_PROMPT,
        expected_output_schema="NextEpisodeSuggestion",
    ),
    "post-generation-suggestion.v1": PromptSpec(
        prompt_id="post-generation-suggestion.v1",
        version="1",
        owner_role="post_generation_suggestion",
        template=POST_GENERATION_SUGGESTION_PROMPT,
        expected_output_schema="PostGenerationSuggestion[]",
    ),
    "context-compression.v1": PromptSpec(
        prompt_id="context-compression.v1",
        version="1",
        owner_role="context_compressor",
        template=CONTEXT_COMPRESSION_PROMPT,
        expected_output_schema="CompressedContext",
    ),
}


# Prompt lookup guard: central lookup keeps future role code from importing raw
# constants directly while preserving exact prompt text today.
def get_prompt_spec(prompt_id: str) -> PromptSpec:
    return PROMPT_CATALOG[prompt_id]


__all__ = [
    "PROMPT_CATALOG",
    "PromptSpec",
    "get_prompt_spec",
]
