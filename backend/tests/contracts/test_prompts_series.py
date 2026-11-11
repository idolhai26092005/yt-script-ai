import pytest
from app.services.production.prompts.legacy import (
    SERIES_SUGGESTION_PROMPT,
    SERIES_NEXT_EPISODE_PROMPT,
    POST_GENERATION_SUGGESTION_PROMPT,
    CONTEXT_COMPRESSION_PROMPT
)

def test_series_suggestion_prompt_formatting():
    formatted = SERIES_SUGGESTION_PROMPT.format(
        title="Dinosaur Hunt",
        big_idea="Survival",
        generation_mode="series_short",
        num_episodes=5
    )
    assert "Dinosaur Hunt" in formatted
    assert "Survival" in formatted
    assert "series_short" in formatted

def test_series_next_episode_prompt_formatting():
    formatted = SERIES_NEXT_EPISODE_PROMPT.format(
        episode_number=2,
        series_title="Ancient Earth",
        big_idea="Ice Age",
        style="3D CGI",
        outline_concept="Mammoth search",
        context_str="{}",
        user_feedback_prompt="Make it scary"
    )
    assert "2" in formatted
    assert "Ancient Earth" in formatted
    assert "Ice Age" in formatted
    assert "3D CGI" in formatted
    assert "Mammoth search" in formatted
    assert "Make it scary" in formatted

def test_post_generation_suggestion_prompt_formatting():
    formatted = POST_GENERATION_SUGGESTION_PROMPT.format(
        script_json='{"scenes": []}'
    )
    assert '{"scenes": []}' in formatted

def test_context_compression_prompt_formatting():
    formatted = CONTEXT_COMPRESSION_PROMPT.format(
        episode_num=3,
        script_json='{"scenes": []}'
    )
    assert "3" in formatted
    assert '{"scenes": []}' in formatted
