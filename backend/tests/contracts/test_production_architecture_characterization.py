import json

from app.core.repository import StubScreenplayRepository
from app.services.production import ProductionService


def _minimal_script_data() -> dict:
    return {
        "schema_version": "2.0",
        "topic_type": "fictional_original",
        "prompt_0": {
            "primary_subject_en": "Redhaired Hero",
            "continuity_lock_en": "Redhaired Hero in a stone valley",
            "negative_constraints_en": "watermark",
        },
        "overview_analysis_vi": "Tong quan.",
        "storyline_vi": "Hero vuot qua thung lung.",
        "stages_vi": "Canh 1: mo dau.",
        "progression_vi": "Tien trien ro.",
        "camera_strategy_vi": "Wide shot.",
        "continuity_locks_vi": "Hero khong doi.",
        "form_locks_vi": "Ao khoac khong doi.",
        "age_stage_locks_vi": "Truong thanh.",
        "geometry_locks_vi": "Thung lung da.",
        "risk_logic_vi": "Da lo tang dan.",
        "voice_sound_strategy_vi": "Voice ngan.",
        "characters": [{"character_name": "Hero", "description_en": "Redhaired Hero"}],
        "environment_master_prompt_en": "Ancient stone valley.",
        "environment_master_prompt_vi": "Thung lung da co.",
        "emotion_arc": [
            {
                "scene_number": 1,
                "emotion_label": "quyet tam",
                "beat_summary": "Hero buoc vao thung lung",
            }
        ],
        "scenes": [
            {
                "scene_number": 1,
                "title": "Scene 1",
                "action_detail_vi": "Hero buoc tren da.",
                "veo3_prompt_en": "Reference the approved Redhaired Hero walks through stones.",
                "voice_over_en": "The valley tests him.",
                "voice_over_vi": "Thung lung thu thach anh.",
                "scene_specific_negative_en": "watermark",
                "needs_fact_check": False,
            }
        ],
        "reference_images": {
            "character_ref_prompt_en": "Hero ref",
            "background_ref_prompt_en": "Valley ref",
            "thumbnail_ref_prompt_en": "Thumbnail ref",
        },
        "story_contract": {"main_subject_en": "Redhaired Hero"},
        "quality_warnings": [],
        "_semantic_verifier_completed": True,
        "_fact_check_completed": False,
    }


# Characterization guard: SSE framing is public API for the frontend stream,
# so refactors may move the helper but must preserve exact data framing.
def test_stream_event_keeps_existing_sse_data_frame_shape():
    service = ProductionService(api_key="test", db=None, repo=StubScreenplayRepository())

    chunk = service._stream_event({"status": "generating", "group": "metadata", "step": "phase0"})

    assert chunk.startswith("data: ")
    assert chunk.endswith("\n\n")
    payload = json.loads(chunk.removeprefix("data: ").strip())
    assert payload == {"status": "generating", "group": "metadata", "step": "phase0"}


# Characterization guard: resume compatibility must survive state-module extraction
# for both canonical v3 cache signatures and legacy v2 cache signatures.
def test_resume_signature_accepts_canonical_and_legacy_cache_shapes():
    service = ProductionService(api_key="test", db=None, repo=StubScreenplayRepository())
    suggestion = {"index": 2, "title": "Hero", "synopsis": "Hero synopsis"}
    signature = service._build_resume_signature(
        suggestion,
        style="anime",
        num_scenes=1,
        topic_type="fictional_original",
        aspect_ratio="16:9",
        scene_duration_sec=8,
        generation_mode="batch",
    )

    canonical_cached = {
        "schema_version": "3.0",
        "internal": {"cache": {"resume_signature": signature}},
    }
    legacy_signature = dict(signature)
    legacy_signature["schema_version"] = "2.0"
    legacy_cached = {"schema_version": "2.0", "_resume_signature": legacy_signature}

    assert service._is_resume_cache_compatible(canonical_cached, signature)
    assert service._is_resume_cache_compatible(legacy_cached, signature)


# Characterization guard: v3 hydration currently restores public v2 work fields
# but does not carry internal story_contract through the legacy adapter.
def test_hydrate_resume_cache_restores_v2_work_state_with_current_contract_behavior():
    service = ProductionService(api_key="test", db=None, repo=StubScreenplayRepository())
    script_data = service._new_script_data("fictional_original")
    cached = {
        "schema_version": "3.0",
        "topic": {"type": "fictional_original"},
        "production_plan": {"storyline_vi": "Hero giu contract."},
        "anchors": {"prompt_0": {"primary_subject_en": "Hero"}},
        "internal": {"story_contract": {"main_subject_en": "Hero"}},
    }

    service._hydrate_resume_cache(script_data, cached)

    assert script_data["schema_version"] == "2.0"
    assert script_data["storyline_vi"] == "Hero giu contract."
    assert script_data["prompt_0"]["primary_subject_en"] == "Hero"
    assert script_data["story_contract"] == {}


# Characterization guard: phase log schema is the observability seam used by
# later role objects, so extraction must keep current stage/schema/error fields.
def test_append_phase_log_uses_canonical_schema_version():
    repo = StubScreenplayRepository()
    service = ProductionService(api_key="test", db=None, repo=repo)

    service._append_phase_log(7, "prompt0_blueprint", ["missing field"], 12.5)

    entry = repo.projects[7]["phase_log"][0]
    assert entry["stage_role"] == "prompt0_blueprint"
    assert entry["schema_version"] == "3.0"
    assert entry["validation_errors"] == ["missing field"]
    assert entry["latency_ms"] == 12.5


# Characterization guard: saves must publish canonical v3 by default even while
# the producer internally keeps the flatter v2 work object during migration.
def test_save_script_persists_canonical_v3_shape_by_default():
    repo = StubScreenplayRepository()
    service = ProductionService(api_key="test", db=None, repo=repo)
    script_data = _minimal_script_data()

    service._save_script(9, 3, script_data, "generating_script", "fictional_original")

    saved = json.loads(repo.projects[9]["script_output"])
    assert saved["schema_version"] == "3.0"
    assert saved["topic"]["type"] == "fictional_original"
    assert saved["production_plan"]["storyline_vi"] == script_data["storyline_vi"]
    assert saved["anchors"]["prompt_0"] == script_data["prompt_0"]
    assert saved["internal"]["story_contract"] == script_data["story_contract"]
    assert saved["scenes"][0]["scene_number"] == 1
