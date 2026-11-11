import pytest
from app.schemas.script_production import CharacterPrompt, SceneScript, ScriptOutput

def test_schemas_have_bilingual_fields():
    # CharacterPrompt fields
    assert "description_vi" in CharacterPrompt.model_fields
    assert "key_identifiers_vi" in CharacterPrompt.model_fields
    
    # SceneScript fields
    assert "veo3_prompt_vi" in SceneScript.model_fields
    
    # ScriptOutput fields
    assert "environment_master_prompt_vi" in ScriptOutput.model_fields
    assert "continuity_board" in ScriptOutput.model_fields
