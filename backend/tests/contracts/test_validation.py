from app.services.production.validation.legacy import (
    validate_scene,
    validate_script,
    normalize_scene,
    normalize_script,
    validate_blueprint_required,
    validate_emotion_arc_quality,
    validate_scene_generation_quality,
    validate_historical_coverage,
    validate_story_spine_quality,
    validate_story_contract_issues,
    detect_story_contract_batch_drift,
    validate_emotion_arc_state_machine,
    validate_scene_generation_issues,
    blocking_messages,
)
from app.core.utils import to_canonical_v3, to_legacy_v2
from app.services.production.base import build_story_spine, stage_context_for_range

def test_validate_scene_missing_voice_over():
    # 4.3: validate_scene returns error when voice_over_en is missing/empty
    valid_anchor = {"continuity_prompt_en": "approved context"}
    scene = {
        "voice_over_en": "",  # Empty
        "veo3_prompt_en": "Reference the approved shot description",
        "needs_fact_check": False
    }
    errors = validate_scene(normalize_scene(scene), valid_anchor)
    assert "missing voice_over_en" in errors

def test_validate_scene_missing_anchor_citation():
    # 4.4: validate_scene returns error when veo3_prompt_en doesn't start with "Reference the approved"
    valid_anchor = {"continuity_prompt_en": "approved context"}
    scene = {
        "voice_over_en": "Cinematic voice narration",
        "veo3_prompt_en": "A close up shot of a character",  # Doesn't start with prefix
        "needs_fact_check": False
    }
    errors = validate_scene(normalize_scene(scene), valid_anchor)
    assert "missing continuity anchor citation (must start with 'Reference the approved')" in errors

def test_validate_scene_missing_fact_check_note():
    # 4.5: validate_scene returns error when needs_fact_check=True and fact_check_note_vi is missing
    valid_anchor = {"continuity_prompt_en": "approved context"}
    scene = {
        "voice_over_en": "Cinematic voice narration",
        "veo3_prompt_en": "Reference the approved shot description",
        "needs_fact_check": True,
        "fact_check_note_vi": ""  # Missing
    }
    errors = validate_scene(normalize_scene(scene), valid_anchor)
    assert "needs_fact_check=true but missing fact_check_note_vi" in errors

def test_validate_scene_valid():
    # 4.6: validate_scene returns empty list for a fully valid scene dict
    valid_anchor = {"continuity_prompt_en": "approved context"}
    scene = {
        "voice_over_en": "Cinematic voice narration",
        "veo3_prompt_en": "Reference the approved shot description",
        "needs_fact_check": True,
        "fact_check_note_vi": "Ghi chú kiểm định"
    }
    errors = validate_scene(normalize_scene(scene), valid_anchor)
    assert errors == []

def test_validate_scene_empty_anchor_is_error():
    scene = {
        "voice_over_en": "Cinematic voice narration",
        "veo3_prompt_en": "Reference the approved shot description",
        "needs_fact_check": False
    }
    errors = validate_scene(normalize_scene(scene), {"continuity_prompt_en": ""})
    assert "continuity anchor is empty" in errors

def test_validate_blueprint_required_rejects_empty_prompt0():
    script_data = {
        "prompt_0": {},
        "characters": [{"character_name": "Hero"}],
        "environment_master_prompt_en": "Forest",
    }
    errors = validate_blueprint_required(script_data)
    assert any("prompt_0 is empty" in e for e in errors)

def test_validate_emotion_arc_quality_rejects_fallback_rows():
    arc = [{
        "scene_number": 1,
        "emotion_label": "kịch tính",
        "beat_summary": "Diễn biến cảnh 1",
        "physical_state_end": "Sẵn sàng cho cảnh tiếp theo",
        "camera_complexity": "medium",
    }]
    errors = validate_emotion_arc_quality(arc, 1)
    assert any("fallback placeholder" in e for e in errors)

def test_validate_scene_generation_quality_rejects_fallback_scene():
    script_data = {
        "prompt_0": {
            "primary_subject_en": "Kael, young hunter",
            "continuity_lock_en": "Kael keeps obsidian spear",
        },
        "continuity_prompt_en": "Kael keeps obsidian spear",
        "characters": [{"character_name": "Kael", "key_identifiers_en": "obsidian spear"}],
        "scenes": [{
            "scene_number": 1,
            "veo3_prompt_en": "Reference the approved Prompt 0 continuity board, cinematic shot, voice: \"The story continues.\"",
            "voice_over_en": "The story continues.",
            "needs_fact_check": False,
            "generation_failed": True,
        }],
    }
    errors = validate_scene_generation_quality(script_data)
    assert any("generated fallback scene" in e for e in errors)
    assert any("template/fallback text" in e for e in errors)


def test_scene_generation_issue_severity_keeps_fallback_blocking():
    script_data = {
        "prompt_0": {
            "primary_subject_en": "Kael, young hunter",
            "continuity_lock_en": "Kael keeps obsidian spear",
        },
        "continuity_prompt_en": "Kael keeps obsidian spear",
        "characters": [{"character_name": "Kael", "key_identifiers_en": "obsidian spear"}],
        "scenes": [{
            "scene_number": 1,
            "veo3_prompt_en": "Reference the approved Prompt 0 continuity board, cinematic shot, voice: \"The story continues.\"",
            "voice_over_en": "The story continues.",
            "needs_fact_check": False,
            "generation_failed": True,
        }],
    }

    issues = validate_scene_generation_issues(script_data)

    assert any(issue.severity == "BLOCK" and "fallback scene" in issue.message for issue in issues)
    assert blocking_messages(issues)


def test_scene_generation_issue_severity_downgrades_semantic_regex_to_warning():
    script_data = {
        "prompt_0": {
            "primary_subject_en": "Arthur firefighter",
            "continuity_lock_en": "Arthur's jacket accumulates more soot after visible exposure.",
        },
        "continuity_prompt_en": "Arthur's jacket accumulates more soot after visible exposure.",
        "characters": [{"character_name": "Arthur", "key_identifiers_en": "firefighter gear"}],
        "scenes": [{
            "scene_number": 1,
            "action_detail_vi": "Arthur ngồi trên xe và tiếp cận hiện trường.",
            "veo3_prompt_en": "Reference the approved Prompt 0 continuity board, Arthur rides toward smoke in firefighter gear with soot-stained fabric continuity, voice: \"Duty begins here.\"",
            "voice_over_en": "Duty begins here.",
            "needs_fact_check": False,
        }],
    }

    issues = validate_scene_generation_issues(script_data)

    assert any("soot/smoke" in issue.message and issue.severity == "WARN" for issue in issues)
    assert not blocking_messages(issues)

def test_validate_story_state_machine_rejects_resolution_before_assigned_range():
    def scene(num: int, action: str) -> dict:
        return {
            "scene_number": num,
            "action_detail_vi": action,
            "veo3_prompt_en": "Reference the approved Kael hunter continuity board, cinematic shot.",
            "voice_over_en": "The hunt continues.",
            "needs_fact_check": False,
        }

    script_data = {
        "prompt_0": {
            "primary_subject_en": "Kael, young hunter",
            "continuity_lock_en": "Kael keeps obsidian spear",
        },
        "continuity_prompt_en": "Kael keeps obsidian spear",
        "characters": [{"character_name": "Kael", "key_identifiers_en": "obsidian spear"}],
        "story_spine": {
            "version": "1.2",
            "total_scenes": 80,
            "steps": [{"step": 10, "scene_start": 73, "scene_end": 80, "trigger": "resolution"}],
            "allowed_once_triggers": ["resolution"],
        },
        "scenes": [
            scene(i, f"Kael tiếp tục vượt vùng băng ở cảnh {i}.")
            for i in range(1, 20)
        ] + [
            scene(20, "Kael tháo mũ dưới bình minh sau khi thoát khỏi vùng nguy hiểm."),
        ],
    }
    errors = validate_scene_generation_quality(script_data)
    assert any("appears outside its assigned scene range 73-80" in e for e in errors)


def test_story_spine_v12_uses_stage_ranges_for_triggers():
    prompt_0 = {
        "action_story_logic_en": (
            "1. Fire alarm rings. 2. Thomas climbs truck. 3. Arrive at inferno. "
            "4. Smoke barrier entry. 5. Finding survivor. 6. Successful extraction. "
            "7. Exhaustion in street."
        )
    }
    stages_vi = (
        "Giai đoạn 1 - Báo động (Cảnh 1-10): mở ca trực.\n"
        "Giai đoạn 2 - Tiếp cận (Cảnh 11-25): đi tới hiện trường.\n"
        "Giai đoạn 3 - Mắc kẹt (Cảnh 26-45): bị khói chặn.\n"
        "Giai đoạn 4 - Giải cứu (Cảnh 46-65): kéo nạn nhân ra.\n"
        "Giai đoạn 5 - Sống sót (Cảnh 66-80): kết thúc nhiệm vụ."
    )
    spine = build_story_spine(prompt_0, stages_vi, 80)

    assert spine["version"] == "1.2"
    assert not validate_story_spine_quality({"story_spine": spine})
    resolution = next(step for step in spine["steps"] if step.get("trigger") == "resolution")
    assert (resolution["scene_start"], resolution["scene_end"]) == (66, 80)


def test_story_spine_hard_triggers_stay_general_not_domain_specific():
    prompt_0 = {
        "action_story_logic_en": (
            "1. Fire alarm rings. 2. Thomas departs from station. 3. Arrive at inferno. "
            "4. Smoke barrier entry. 5. Finding survivor. 6. Successful rescue. "
            "7. Final resolution."
        )
    }
    stages_vi = (
        "Giai đoạn 1 - Báo động (Cảnh 1-10). "
        "Giai đoạn 2 - Tiếp cận (Cảnh 11-25). "
        "Giai đoạn 3 - Mắc kẹt (Cảnh 26-45). "
        "Giai đoạn 4 - Hành động chính (Cảnh 46-65). "
        "Giai đoạn 5 - Sống sót (Cảnh 66-80)."
    )

    spine = build_story_spine(prompt_0, stages_vi, 80)

    assert set(spine["allowed_once_triggers"]) <= {"alarm", "resolution"}
    assert "discovery" not in spine["allowed_once_triggers"]
    assert "entry" not in spine["allowed_once_triggers"]
    assert "rescue" not in spine["allowed_once_triggers"]


def test_story_spine_parses_project26_parenthesized_ranges_without_scene_word():
    prompt_0 = {
        "action_story_logic_en": (
            "1. Tribal scouting of Mammoth trail. "
            "2. Discovery of trap-avoidance behavior. "
            "3. First failed ambush. "
            "4. Realization of entity intelligence. "
            "5. Peaceful coexistence established."
        )
    }
    stages_vi = (
        "Giai đoạn 1 – Dẫn dắt (1-20): Thiết lập môi trường và mục tiêu. "
        "Giai đoạn 2 – Đối đầu (21-40): Những cạm bẫy bị con vật vô hiệu hóa. "
        "Giai đoạn 3 – Bước ngoặt (41-60): Thay đổi tư duy chiến thuật. "
        "Giai đoạn 4 – Hòa hợp (61-80): Con vật hướng dẫn bộ lạc."
    )

    spine = build_story_spine(prompt_0, stages_vi, 80)

    assert [s["scene_start"] for s in spine["stage_ranges"]] == [1, 21, 41, 61]
    assert [s["scene_end"] for s in spine["stage_ranges"]] == [20, 40, 60, 80]
    assert spine["stage_ranges"][0].get("source") != "fallback"
    assert spine["stage_ranges"][-1]["trigger"] == "resolution"
    assert not validate_story_spine_quality({"story_spine": spine})


def test_story_spine_parses_semicolon_separated_parenthesized_ranges():
    prompt_0 = {
        "action_story_logic_en": (
            "1. Arrival. 2. Entry. 3. Search. 4. Rescue. 5. Exit."
        )
    }
    stages_vi = (
        "Giai đoạn 1: Tiếp cận (1-10) - Thiết lập hiện trường; "
        "Giai đoạn 2: Tiến sâu (11-20) - Đối mặt chướng ngại vật; "
        "Giai đoạn 3: Cao trào (21-40) - Đám cháy dữ dội; "
        "Giai đoạn 4: Giải cứu (41-50) - Vượt qua giới hạn; "
        "Giai đoạn 5: Thoát hiểm (51-60) - Kết thúc."
    )

    spine = build_story_spine(prompt_0, stages_vi, 60)

    assert [s["scene_start"] for s in spine["stage_ranges"]] == [1, 11, 21, 41, 51]
    assert [s["scene_end"] for s in spine["stage_ranges"]] == [10, 20, 40, 50, 60]
    assert not spine["coverage_errors"]
    assert not validate_story_spine_quality({"story_spine": spine})


def test_story_spine_parses_scene_to_range_format():
    prompt_0 = {"action_story_logic_en": "1. Setup. 2. Conflict. 3. Resolution."}
    stages_vi = "Stage 1 Scene 1 to 10: setup. Stage 2 Scenes 11 to 20: conflict."

    spine = build_story_spine(prompt_0, stages_vi, 20)

    assert [s["scene_start"] for s in spine["stage_ranges"]] == [1, 11]
    assert [s["scene_end"] for s in spine["stage_ranges"]] == [10, 20]
    assert not spine["coverage_errors"]


def test_project19_stage_context_is_range_scoped():
    # Longform stage regression: one-line multi-stage plans must not leak every
    # historical chapter into every scene batch.
    stages_vi = (
        "Giai đoạn 1 – Tần Thủy Hoàng (Cảnh 1-20): Thiết lập tầm nhìn. "
        "Giai đoạn 2 – Napoleon (Cảnh 21-40): Sự trỗi dậy từ cách mạng. "
        "Giai đoạn 3 – Hitler (Cảnh 41-60): Sụp đổ hoàn toàn."
    )
    prompt_0 = {"action_story_logic_en": "1. Vision. 2. Ascent. 3. Cost. 4. Legacy."}
    spine = build_story_spine(prompt_0, stages_vi, 60)

    first = stage_context_for_range(spine, 1, 10)
    middle = stage_context_for_range(spine, 21, 30)
    final = stage_context_for_range(spine, 41, 50)

    assert "Tần Thủy Hoàng" in first
    assert "Napoleon" not in first
    assert "Hitler" not in first
    assert "Napoleon" in middle
    assert "Tần Thủy Hoàng" not in middle
    assert "Hitler" in final
    assert "Napoleon" not in final


def test_historical_scene_stage_mismatch_blocks_wrong_named_figure():
    # Stage/person gate lives after concrete scene generation so arc generation
    # stays bounded while wrong-chapter scene text is rejected before merge.
    stages_vi = (
        "Giai đoạn 1 – Tần Thủy Hoàng (Cảnh 1-20): Thiết lập tầm nhìn. "
        "Giai đoạn 2 – Napoleon (Cảnh 21-40): Sự trỗi dậy."
    )
    spine = build_story_spine({"action_story_logic_en": "1. Vision. 2. Cost."}, stages_vi, 40)
    script_data = {
        "topic_type": "historical",
        "prompt_0": {
            "primary_subject_en": "Qin Shi Huang and Napoleon",
            "continuity_lock_en": "Approved board",
        },
        "continuity_prompt_en": "Approved board",
        "characters": [
            {"character_name": "Qin Shi Huang", "key_identifiers_en": "black robes"},
            {"character_name": "Napoleon", "key_identifiers_en": "bicorne hat"},
        ],
        "environment_master_prompt_en": "Historical chambers",
        "story_spine": spine,
        "emotion_arc": [{"scene_number": 1, "scene_lead_character": "Napoleon"}],
        "scenes": [{
            "scene_number": 1,
            "action_detail_vi": "Napoleon đứng trước bản đồ châu Âu.",
            "veo3_prompt_en": "Reference the approved Prompt 0 continuity board, Napoleon studies Europe, voice: \"Ambition sharpens the map.\"",
            "voice_over_en": "Ambition sharpens the map.",
            "scene_specific_negative_en": "No modern devices",
            "needs_fact_check": False,
        }],
    }

    issues = validate_scene_generation_issues(script_data)

    assert any(issue.code == "stage_character_mismatch" and issue.severity == "BLOCK" for issue in issues)
    assert blocking_messages(issues)


def test_historical_neutral_bridge_scene_is_allowed_inside_named_stage():
    # Neutral bridge guard: summary shots can pass if they avoid wrong named
    # figures and do not create a shared cross-era physical scene.
    stages_vi = "Giai đoạn 1 – Tần Thủy Hoàng (Cảnh 1-20): Thiết lập tầm nhìn."
    spine = build_story_spine({"action_story_logic_en": "1. Vision."}, stages_vi, 20)
    script_data = {
        "topic_type": "historical",
        "prompt_0": {
            "primary_subject_en": "Qin Shi Huang",
            "continuity_lock_en": "Approved board",
        },
        "continuity_prompt_en": "Approved board",
        "characters": [{"character_name": "Qin Shi Huang", "key_identifiers_en": "black robes"}],
        "environment_master_prompt_en": "Ancient archive",
        "story_spine": spine,
        "emotion_arc": [{"scene_number": 1, "scene_lead_character": "None"}],
        "scenes": [{
            "scene_number": 1,
            "action_detail_vi": "Trang sử mở ra trong ánh sáng lạnh, giới thiệu sức nặng quyền lực.",
            "veo3_prompt_en": "Reference the approved Prompt 0 continuity board, empty parchment in ancient archive, voice: \"Power begins as a question.\"",
            "voice_over_en": "Power begins as a question.",
            "scene_specific_negative_en": "No modern devices",
            "needs_fact_check": False,
        }],
    }

    issues = validate_scene_generation_issues(script_data)

    assert not any(issue.code == "stage_character_mismatch" for issue in issues)


def test_story_spine_falls_back_to_full_range_when_coverage_has_gap():
    prompt_0 = {"action_story_logic_en": "1. Setup. 2. Conflict. 3. Resolution."}
    stages_vi = "Giai đoạn 1 (1-10): mở đầu."

    spine = build_story_spine(prompt_0, stages_vi, 60)

    assert spine["stage_ranges"] == [{
        "scene_start": 1,
        "scene_end": 60,
        "label": "Full continuous journey",
        "trigger": None,
        "source": "coverage_fallback",
    }]
    assert any("leave gap 11-60" in err for err in spine["coverage_errors"])


# Durable topic-contract regression: Project-9-style side-threat takeover must
# become a soft warning from the generated contract, not a mammoth/wolf hard rule.
def test_story_contract_warns_when_side_threat_overtakes_central_subject():
    script_data = {
        "story_contract": {
            "main_subject_en": "Giant Ancient Mammoth",
            "main_subject_vi": "Voi ma mút cổ đại khổng lồ",
            "protagonist_en": "Kaelen and the hunting tribe",
            "protagonist_vi": "Kaelen và bộ lạc săn bắn",
            "central_opponent_or_force_en": "Giant Ancient Mammoth intelligence",
            "central_opponent_or_force_vi": "trí khôn của voi ma mút",
            "core_goal_en": "learn that strength alone cannot defeat the mammoth",
            "core_goal_vi": "học rằng sức mạnh không đủ để thắng voi ma mút",
            "must_remain_visible_terms": ["Mammoth", "mammoth intelligence", "hunt"],
            "allowed_side_threats": ["wolves", "sói", "blizzard"],
            "forbidden_takeover_rule": "Wolves may pressure the tribe but must not replace the mammoth conflict.",
        },
        "storyline_vi": "Kaelen dẫn bộ lạc săn voi ma mút và học rằng sức mạnh không đủ.",
        "stages_vi": (
            "Giai đoạn 1 (Cảnh 1-15): bộ lạc lần dấu sói. "
            "Giai đoạn 2 (Cảnh 16-30): bầy sói phục kích. "
            "Giai đoạn 3 (Cảnh 31-45): Kaelen đối đầu sói đầu đàn."
        ),
    }

    issues = validate_story_contract_issues(script_data)

    assert any(issue.code == "central_contract_takeover_risk" for issue in issues)
    assert all(issue.severity != "BLOCK" for issue in issues)


# Durable topic-contract regression: allowed obstacles remain valid when the
# central subject/opponent is still present in the same batch.
def test_story_contract_batch_drift_allows_side_threat_when_central_stays_visible():
    script_data = {
        "story_contract": {
            "main_subject_en": "Giant Ancient Mammoth",
            "central_opponent_or_force_en": "Mammoth intelligence",
            "core_goal_en": "outwit the mammoth",
            "must_remain_visible_terms": ["Mammoth", "mammoth trail"],
            "allowed_side_threats": ["wolves"],
        }
    }
    scenes = [
        {
            "scene_number": 11,
            "action_detail_vi": "Kaelen thấy voi ma mút đổi hướng để tránh bầy sói.",
            "veo3_prompt_en": "Reference the approved Prompt 0 continuity board, mammoth trail crossing wolf tracks, voice: \"The hunt learns back.\"",
            "voice_over_en": "The hunt learns back.",
        }
    ]

    assert detect_story_contract_batch_drift(script_data, scenes) is None


# Durable topic-contract regression: batch drift is detected from contract terms
# only, so topic adherence can trigger verifier without domain regex.
def test_story_contract_batch_drift_warns_when_central_disappears():
    script_data = {
        "story_contract": {
            "main_subject_en": "Giant Ancient Mammoth",
            "central_opponent_or_force_en": "Mammoth intelligence",
            "core_goal_en": "outwit the mammoth",
            "must_remain_visible_terms": ["Mammoth"],
            "allowed_side_threats": ["wolves"],
        }
    }
    scenes = [
        {
            "scene_number": 21,
            "action_detail_vi": "Kaelen dựng bẫy chống bầy sói giữa khe băng.",
            "veo3_prompt_en": "Reference the approved Prompt 0 continuity board, wolves circle the ice pass, voice: \"Teeth replace the storm.\"",
            "voice_over_en": "Teeth replace the storm.",
        }
    ]

    warning = detect_story_contract_batch_drift(script_data, scenes)

    assert warning and "central_contract_drift" in warning


# Durable schema regression: story_contract is internal V3 quality context and
# must not leak into the legacy UI adapter until the frontend intentionally adopts it.
def test_story_contract_persists_internal_v3_without_legacy_leak():
    script_data = {
        "topic_type": "fictional_original",
        "prompt_0": {"continuity_lock_en": "Keep Kael stable."},
        "story_contract": {"main_subject_en": "Giant Ancient Mammoth"},
        "quality_warnings": [],
        "scenes": [],
    }

    v3 = to_canonical_v3(script_data)
    legacy = to_legacy_v2(v3)

    assert v3["internal"]["story_contract"]["main_subject_en"] == "Giant Ancient Mammoth"
    assert "story_contract" not in legacy


def test_emotion_arc_state_machine_rejects_macro_loop_before_scenes():
    prompt_0 = {
        "action_story_logic_en": (
            "1. Fire alarm rings. 2. Thomas climbs truck. 3. Arrive at inferno. "
            "4. Smoke barrier entry. 5. Finding survivor. 6. Successful extraction. "
            "7. Exhaustion in street."
        )
    }
    spine = build_story_spine(
        prompt_0,
        "Giai đoạn 1 - Báo động (Cảnh 1-10). Giai đoạn 2 - Tiếp cận (Cảnh 11-25). "
        "Giai đoạn 3 - Mắc kẹt (Cảnh 26-45). Giai đoạn 4 - Giải cứu (Cảnh 46-65). "
        "Giai đoạn 5 - Sống sót (Cảnh 66-80).",
        80,
    )
    arc = [
        {
            "scene_number": i,
            "emotion_label": "căng thẳng",
            "beat_summary": "Thomas tiếp tục tiến sâu vào đám cháy.",
            "physical_state_end": f"Thomas ở vị trí {i}",
            "camera_complexity": "medium",
        }
        for i in range(1, 81)
    ]
    arc[1]["beat_summary"] = "Chuông báo cháy vang lên, Thomas bật dậy."
    arc[20]["beat_summary"] = "Chuông báo cháy lại vang lên như một nhiệm vụ mới."

    errors = validate_emotion_arc_state_machine(arc, spine)

    assert any("Emotion arc state trigger 'alarm' repeats" in e for e in errors)


def test_emotion_arc_state_machine_ignores_discovery_as_hard_trigger():
    prompt_0 = {
        "action_story_logic_en": (
            "1. Discovery of Mammoth tracks. 2. Tracking through blizzard. "
            "3. First failed ambush. 4. Tactical triumph. 5. Respectful resolution."
        )
    }
    spine = build_story_spine(
        prompt_0,
        "Giai đoạn 1 - Tiếp cận (Cảnh 1-20): Bộ lạc phát hiện dấu vết. "
        "Giai đoạn 2 - Đối đầu (Cảnh 21-40): Những trận đụng độ thất bại. "
        "Giai đoạn 3 - Thay đổi (Cảnh 41-60): Kael nghiên cứu hành vi. "
        "Giai đoạn 4 - Chung cuộc (Cảnh 61-80): Trận chiến quyết định.",
        80,
    )
    arc = [
        {
            "scene_number": i,
            "emotion_label": "căng thẳng",
            "beat_summary": f"Kael tiếp tục lần theo dấu vết ở cảnh {i}.",
            "physical_state_end": f"Kael dừng ở vị trí {i}.",
            "camera_complexity": "medium",
        }
        for i in range(1, 81)
    ]
    arc[0]["beat_summary"] = "Kael phát hiện dấu chân voi ma mút đầu tiên."
    arc[6]["beat_summary"] = "Kael tìm thấy dấu tuyết mới trong cùng cuộc truy dấu."

    assert "discovery" not in spine.get("allowed_once_triggers", [])
    assert validate_emotion_arc_state_machine(arc, spine) == []

    arc[29]["beat_summary"] = "Kael phát hiện dấu chân như thể cuộc truy dấu bắt đầu lại."
    assert validate_emotion_arc_state_machine(arc, spine) == []


def test_emotion_arc_state_machine_does_not_treat_tactical_discovery_as_first_discovery():
    prompt_0 = {
        "action_story_logic_en": (
            "1. Discovery of Mammoth tracks. 2. Tribal assembly. 3. Initial ambush fail. "
            "4. Mammoth outmaneuvers hunters. 5. Trap preparation. 6. Respectful resolution."
        )
    }
    spine = build_story_spine(
        prompt_0,
        "Giai đoạn 1 (Cảnh 1-20): Hành trình tìm kiếm. "
        "Giai đoạn 2 (Cảnh 21-40): Cuộc đụng độ đầu tiên và thất bại. "
        "Giai đoạn 3 (Cảnh 41-60): Chiến thuật mới trong hang băng. "
        "Giai đoạn 4 (Cảnh 61-80): Đỉnh điểm và sự tôn trọng.",
        80,
    )
    arc = [
        {
            "scene_number": i,
            "emotion_label": "căng thẳng",
            "beat_summary": f"Kaelen tiếp tục đối đầu ở cảnh {i}.",
            "physical_state_end": f"Kaelen giữ vị trí sau cảnh {i}.",
            "camera_complexity": "medium",
        }
        for i in range(1, 81)
    ]
    arc[20]["beat_summary"] = "Kaelen phát hiện bẫy gỗ bị con vật phá hủy có chủ đích."

    errors = validate_emotion_arc_state_machine(arc, spine)

    assert not any("discovery' appears outside" in e for e in errors)

    arc[36]["beat_summary"] = "Kaelen đặt tay lên ngực như một lời chào cuối cùng đến vùng băng giá."
    errors = validate_emotion_arc_state_machine(arc, spine)
    assert any("resolution' appears outside its assigned scene range 61-80" in e for e in errors)


def test_story_state_machine_allows_resolution_span_inside_final_stage():
    def scene(num: int, action: str) -> dict:
        return {
            "scene_number": num,
            "action_detail_vi": action,
            "veo3_prompt_en": "Reference the approved Kael continuity board, realistic style, voice: \"The ice grows quiet.\"",
            "voice_over_en": "The ice grows quiet.",
            "needs_fact_check": False,
        }

    script_data = {
        "prompt_0": {
            "primary_subject_en": "Kael hunter",
            "continuity_lock_en": "Kael keeps mammoth-hide cloak",
            "action_story_logic_en": "1. Hunt. 2. Final standoff. 3. Resolution.",
        },
        "continuity_prompt_en": "Kael keeps mammoth-hide cloak",
        "characters": [{"character_name": "Kael", "key_identifiers_en": "mammoth-hide cloak"}],
        "story_spine": {
            "version": "1.2",
            "total_scenes": 80,
            "steps": [{"step": 3, "scene_start": 61, "scene_end": 80, "trigger": "resolution"}],
            "stage_ranges": [{"scene_start": 61, "scene_end": 80, "trigger": "resolution"}],
            "allowed_once_triggers": ["resolution"],
        },
        "scenes": [scene(i, f"Kael tiến qua cảnh {i}.") for i in range(1, 81)],
    }
    script_data["scenes"][65]["action_detail_vi"] = "Kael bỏ lại cây giáo để kết thúc cuộc săn."
    script_data["scenes"][78]["action_detail_vi"] = "Kael đứng bình yên trong vùng băng."

    assert validate_scene_generation_quality(script_data) == []

    script_data["scenes"][19]["action_detail_vi"] = "Kael tháo mũ dưới bình minh như nhiệm vụ đã kết thúc."
    errors = validate_scene_generation_quality(script_data)
    assert any("appears outside its assigned scene range 61-80" in e for e in errors)


def test_emotion_arc_state_machine_rejects_project25_soft_endings_before_final_stage():
    prompt_0 = {
        "action_story_logic_en": (
            "1. Tribal camp assembly. 2. Tracking the Mammoth prints. "
            "3. First visual contact. 4. Failed initial trap. "
            "5. Final showdown. 6. Resolution and departure."
        )
    }
    spine = build_story_spine(
        prompt_0,
        "Giai đoạn 1 - Xuất phát (Cảnh 1-20). "
        "Giai đoạn 2 - Dò tìm (Cảnh 21-40). "
        "Giai đoạn 3 - Đối đầu (Cảnh 41-60). "
        "Giai đoạn 4 - Tỉnh ngộ & Kết thúc (Cảnh 61-80).",
        80,
    )
    arc = [
        {
            "scene_number": i,
            "emotion_label": "căng thẳng",
            "beat_summary": f"Kael tiếp tục cuộc săn ở cảnh {i}.",
            "physical_state_end": f"Kael giữ vị trí sau cảnh {i}.",
            "camera_complexity": "medium",
        }
        for i in range(1, 81)
    ]
    arc[19]["beat_summary"] = "Ánh hoàng hôn bao phủ vùng đất băng giá, để lại Kael đứng trầm mặc."
    arc[35]["beat_summary"] = "Kael chấp nhận thất bại trong việc săn lùng và chọn hòa hợp."
    arc[39]["beat_summary"] = "Kael đặt tay lên ngực như một lời chào cuối cùng đến vùng đất băng giá."
    arc[59]["beat_summary"] = "Kael quay lưng lại, rời khỏi khu vực trong sự tĩnh lặng."

    errors = validate_emotion_arc_state_machine(arc, spine)

    assert any("resolution' appears outside its assigned scene range 61-80" in e for e in errors)


def test_validate_story_state_machine_rejects_macro_loop_when_spine_missing():
    def scene(num: int, action: str) -> dict:
        return {
            "scene_number": num,
            "action_detail_vi": action,
            "veo3_prompt_en": "Reference the approved Thomas firefighter continuity board, cinematic shot.",
            "voice_over_en": "Duty never rests.",
            "needs_fact_check": False,
        }

    actions = {
        2: "Chuông báo cháy vang lên, Thomas lao ra xe cứu hỏa.",
        20: "Thomas ngồi nghỉ dưới ánh bình minh sau khi nạn nhân đã an toàn.",
        21: "Chuông báo cháy lại vang lên, Thomas siết dây đai để bắt đầu ca mới.",
    }
    script_data = {
        "prompt_0": {
            "primary_subject_en": "Thomas firefighter",
            "continuity_lock_en": "Thomas keeps soot-covered firefighter uniform",
        },
        "continuity_prompt_en": "Thomas keeps soot-covered firefighter uniform",
        "characters": [{"character_name": "Thomas", "key_identifiers_en": "firefighter uniform"}],
        "scenes": [
            scene(i, actions.get(i, f"Thomas tiếp tục nhiệm vụ cứu hỏa cảnh {i}."))
            for i in range(1, 26)
        ],
    }
    errors = validate_scene_generation_quality(script_data)
    assert any("Story state trigger 'alarm' repeats" in e for e in errors)

def test_validate_historical_coverage_requires_every_scene_labeled():
    # Durable sparse fact-check regression: missing per-scene labels are no longer
    # blockers until the verification phase itself has failed to complete.
    script_data = {
        "topic_type": "historical",
        "scenes": [{
            "scene_number": 1,
            "historical_basis_vi": "",
            "verifiability_level": None,
            "needs_fact_check": False,
        }],
    }
    errors = validate_historical_coverage(script_data)
    assert errors == ["historical/scientific verification phase not completed"]

def test_validate_scene_accumulate_errors():
    # 4.7: validate_scene accumulates multiple errors in one call
    valid_anchor = {"continuity_prompt_en": "approved context"}
    scene = {
        "voice_over_en": "",  # Error 1
        "veo3_prompt_en": "Bad prompt prefix",  # Error 2
        "needs_fact_check": True,
        "fact_check_note_vi": ""  # Error 3
    }
    errors = validate_scene(normalize_scene(scene), valid_anchor)
    assert len(errors) == 3
    assert "missing voice_over_en" in errors
    assert "missing continuity anchor citation (must start with 'Reference the approved')" in errors
    assert "needs_fact_check=true but missing fact_check_note_vi" in errors

def test_validate_script_mismatched_counts():
    # 4.8: validate_script returns error on emotion_arc/scenes count mismatch
    script_data = {
        "emotion_arc": [{"scene_number": 1}],
        "scenes": [{"scene_number": 1}, {"scene_number": 2}],  # Count mismatch
        "characters": [{"character_name": "Hero"}],
        "environment_master_prompt_en": "A beautiful forest"
    }
    errors = validate_script(normalize_script(script_data))
    assert "emotion_arc count does not match scenes count" in errors

def test_validate_script_empty_characters():
    # 4.9: validate_script returns error on empty characters list
    script_data = {
        "emotion_arc": [{"scene_number": 1}],
        "scenes": [{"scene_number": 1}],
        "characters": [],  # Empty
        "environment_master_prompt_en": "A beautiful forest"
    }
    errors = validate_script(normalize_script(script_data))
    assert "characters list is empty" in errors

def test_validate_script_missing_environment_prompt():
    # 4.10: validate_script returns error on missing environment_master_prompt_en
    script_data = {
        "emotion_arc": [{"scene_number": 1}],
        "scenes": [{"scene_number": 1}],
        "characters": [{"character_name": "Hero"}],
        "environment_master_prompt_en": ""  # Falsy
    }
    errors = validate_script(normalize_script(script_data))
    assert "missing environment_master_prompt_en" in errors

def test_validate_script_valid():
    # 4.11: validate_script returns empty list for valid script dict
    script_data = {
        "emotion_arc": [{"scene_number": 1}],
        "scenes": [{"scene_number": 1}],
        "characters": [{"character_name": "Hero"}],
        "environment_master_prompt_en": "A beautiful forest"
    }
    errors = validate_script(normalize_script(script_data))
    assert errors == []



import json
import pytest
from unittest.mock import AsyncMock, patch
from app.core.database import SessionLocal, Base, engine
from app.models.project import Project
from app.models.api_key import APIKey
from app.crud.project import create_project
from app.crud.api_key import create_api_key
from app.schemas.api_key import APIKeyCreate
from app.services.production import ProductionService

@pytest.mark.asyncio
async def test_schema_version_present():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        key_in = APIKeyCreate(owner="Test Validation Owner", quota_limit=5)
        _, api_key = create_api_key(db, key_in)

        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Test Schema Version",
            input_type="manual",
            input_content="Check version in script",
            style="anime",
            num_scenes=1
        )

        service = ProductionService(api_key="test_key", groq_api_key=None, db=db, api_key_id=api_key.id)
        service.batch_mode = True

        mock_meta = json.dumps({
            "prompt_0": {
                "primary_subject_en": "Subject lock",
                "hard_visual_lock_en": "Visual lock",
                "setting_lock_en": "Setting lock",
                "character_lock": [{"name": "Hero", "description_en": "Hero desc"}],
                "camera_lock_en": "Camera lock",
                "voice_sound_lock_en": "Voice lock",
                "action_story_logic_en": "Logic lock",
                "scene_function_rules_en": "Rules lock",
                "continuity_lock_en": "Continuity lock",
                "internal_logic_en": "Internal logic",
                "negative_constraints_en": "Negative constraints"
            },
            "overview_analysis_vi": "Phân tích",
            "storyline_vi": "Cốt truyện",
            "stages_vi": "Giai đoạn 1",
            "progression_vi": "Tiến trình",
            "camera_strategy_vi": "Chiến lược",
            "continuity_locks_vi": "Khóa liên tục",
            "form_locks_vi": "Khóa cứng",
            "age_stage_locks_vi": "Khóa tuổi",
            "geometry_locks_vi": "Khóa hình học",
            "risk_logic_vi": "Rủi ro",
            "voice_sound_strategy_vi": "Âm thanh",
            "characters": [{"character_name": "Hero", "description_en": "Hero desc", "key_identifiers_en": "hero"}],
            "environment_master_prompt_en": "Forest"
        })
        mock_arc = json.dumps({
            "emotion_arc": [{"scene_number": 1, "emotion_label": "căng thẳng", "beat_summary": "Khởi đầu", "physical_state_end": "Đứng", "camera_complexity": "low", "scene_lead_character": "Hero"}]
        })
        mock_scene = json.dumps({
            "scenes": [{
                "scene_number": 1,
                "title": "Scene 1 [00:00 - 00:08]",
                "action_detail_vi": "Hero xuất hiện",
                "veo3_prompt_en": "Reference the approved Hero, realistic style, voice: \"The story begins.\"",
                "voice_over_en": "The story begins.",
                "needs_fact_check": False,
                "fact_check_note_vi": None,
                "historical_basis_vi": None
            }]
        })
        mock_global = json.dumps({
            "background_ref_prompt_en": "Forest background",
            "thumbnail_ref_prompt_en": "Epic hero thumbnail"
        })

        with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [
                mock_meta,
                mock_arc,
                mock_scene,
                mock_global
            ]

            events = []
            async for ev in service.generate_full_script_stream(
                suggestion={"index": 0, "title": "T", "synopsis": "S", "topic_type": "fictional_original"},
                style="anime",
                num_scenes=1,
                project_id=project.id,
                db=db,
                batch_mode=True
            ):
                events.append(ev)

            db.refresh(project)
            script_out = json.loads(project.script_output)
            assert script_out.get("schema_version") == "3.0"

    finally:
        db.close()


@pytest.mark.asyncio
async def test_validation_retry_loop_triggered():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        service = ProductionService(api_key="test_key", groq_api_key=None, db=db)
        script_data = {
            "schema_version": "2.0",
            "continuity_board": {
                "continuity_prompt_en": "Approved style info",
                "continuity_prompt_vi": "Thông tin phong cách đã duyệt"
            },
            "scenes": [{
                "scene_number": 1,
                "title": "Scene 1 [00:00 - 00:08]",
                "action_detail_vi": "Cũ",
                "veo3_prompt_en": "Cũ",
                "voice_over_en": "Cũ"
            }]
        }

        # First response returns invalid veo3_prompt_en (doesn't start with "Reference the approved")
        invalid_factcheck = json.dumps({
            "scenes": [{
                "scene_number": 1,
                "action_detail_vi": "Mới",
                "veo3_prompt_en": "Caesar in Rome",  # Invalid!
                "voice_over_en": "Giọng thuyết minh",
                "historical_basis_vi": "Cơ sở lịch sử",
                "verifiability_level": "general_consensus",
            }]
        })

        # Second response returns valid
        valid_factcheck = json.dumps({
            "scenes": [{
                "scene_number": 1,
                "action_detail_vi": "Mới",
                "veo3_prompt_en": "Reference the approved Caesar in Rome",  # Valid!
                "voice_over_en": "Giọng thuyết minh",
                "historical_basis_vi": "Cơ sở lịch sử",
                "verifiability_level": "general_consensus",
            }]
        })

        with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [invalid_factcheck, valid_factcheck]

            res, _ = await service._fact_check_chunk(
                chunk=script_data["scenes"],
                style="anime",
                model_name="gemini-3.1-flash-lite",
                script_data=script_data,
                is_historical_or_scientific=True
            )

            assert mock_call.call_count == 2
            # Check that the second call prompt injected validation errors from previous attempt
            second_call_prompt = mock_call.call_args_list[1][1]["prompt"]
            assert "=== VALIDATION ERRORS FROM PREVIOUS ATTEMPT ===" in second_call_prompt
            assert "Scene 1: missing continuity anchor citation" in second_call_prompt
            assert res[0]["veo3_prompt_en"] == "Reference the approved Caesar in Rome"

    finally:
        db.close()


@pytest.mark.asyncio
async def test_fact_check_chunk_prompt_is_range_scoped_and_rejects_unknown_scene():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        service = ProductionService(api_key="test_key", groq_api_key=None, db=db)
        script_data = {
            "schema_version": "2.0",
            "topic_type": "historical",
            "continuity_board": {"continuity_prompt_en": "Approved style info", "continuity_prompt_vi": ""},
            "continuity_prompt_en": "Approved style info",
            "story_spine": {
                "stage_ranges": [
                    {"scene_start": 1, "scene_end": 2, "label": "Start"},
                    {"scene_start": 3, "scene_end": 4, "label": "Later"},
                ]
            },
            "emotion_arc": [
                {"scene_number": 1, "beat_summary": "One"},
                {"scene_number": 2, "beat_summary": "Two"},
                {"scene_number": 3, "beat_summary": "Three"},
            ],
            "scenes": [
                {
                    "scene_number": 1,
                    "title": "Scene 1 [00:00 - 00:08]",
                    "action_detail_vi": "Cảnh một",
                    "veo3_prompt_en": "Reference the approved scene one",
                    "voice_over_en": "Scene one.",
                },
                {
                    "scene_number": 2,
                    "title": "Scene 2 [00:08 - 00:16]",
                    "action_detail_vi": "Cảnh hai",
                    "veo3_prompt_en": "Reference the approved scene two",
                    "voice_over_en": "Scene two.",
                },
            ],
        }
        unknown_patch = json.dumps({
            "verification_patches": [{
                "scene_number": 31,
                "status": "corrected",
                "action_vi": "Sai chunk",
            }]
        })

        with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = unknown_patch

            res, meta = await service._fact_check_chunk(
                chunk=script_data["scenes"],
                style="anime",
                model_name="gemini-3.1-flash-lite",
                script_data=script_data,
                is_historical_or_scientific=True,
            )

        prompt = mock_call.call_args.kwargs["prompt"]
        assert '"scene_number_allowed": [1, 2]' in prompt
        assert '"scene_number": 3' not in prompt
        assert '"scene_number": 31' not in prompt
        assert res == []
        assert "fact_check_unknown_scene_patch" in meta["_fact_check_warnings"][0]
    finally:
        db.close()


@pytest.mark.asyncio
async def test_fact_check_metadata_only_patch_does_not_require_scene_rewrite():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        service = ProductionService(api_key="test_key", groq_api_key=None, db=db)
        script_data = {
            "schema_version": "2.0",
            "topic_type": "historical",
            "continuity_board": {"continuity_prompt_en": "Approved style info", "continuity_prompt_vi": ""},
            "continuity_prompt_en": "Approved style info",
            "scenes": [{
                "scene_number": 1,
                "title": "Scene 1 [00:00 - 00:08]",
                "action_detail_vi": "Cũ",
                "veo3_prompt_en": "Reference the approved old scene",
                "voice_over_en": "Old line.",
            }],
            "emotion_arc": [{"scene_number": 1, "beat_summary": "Old"}],
        }
        metadata_patch = json.dumps({
            "verification_patches": [{
                "scene_number": 1,
                "status": "needs_review",
                "level": "general_consensus",
                "basis_vi": "Cần kiểm tra thêm.",
                "notes_vi": ["Không chắc chi tiết này có sử liệu cụ thể."],
                "risk_flags": ["unverifiable_generalization"],
            }]
        })

        with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = metadata_patch

            res, meta = await service._fact_check_chunk(
                chunk=script_data["scenes"],
                style="anime",
                model_name="gemini-3.1-flash-lite",
                script_data=script_data,
                is_historical_or_scientific=True,
            )

        assert mock_call.call_count == 1
        assert meta == {}
        assert res[0]["action_detail_vi"] == "Cũ"
        assert res[0]["verification_status"] == "needs_review"
        assert res[0]["fact_check_note_vi"]
    finally:
        db.close()


@pytest.mark.asyncio
async def test_validation_retry_loop_exceeded():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        service = ProductionService(api_key="test_key", groq_api_key=None, db=db)
        script_data = {
            "schema_version": "2.0",
            "continuity_board": {
                "continuity_prompt_en": "Approved style info",
                "continuity_prompt_vi": "Thông tin phong cách đã duyệt"
            },
            "scenes": [{
                "scene_number": 1,
                "title": "Scene 1 [00:00 - 00:08]",
                "action_detail_vi": "Cũ",
                "veo3_prompt_en": "Cũ",
                "voice_over_en": "Cũ"
            }]
        }

        # Keep returning invalid responses
        invalid_factcheck = json.dumps({
            "scenes": [{
                "scene_number": 1,
                "action_detail_vi": "Mới",
                "veo3_prompt_en": "Caesar in Rome",  # Invalid!
                "voice_over_en": "Giọng thuyết minh",
                "historical_basis_vi": "Cơ sở lịch sử",
                "verifiability_level": "general_consensus",
            }]
        })

        with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [invalid_factcheck] * 10

            res, _ = await service._fact_check_chunk(
                chunk=script_data["scenes"],
                style="anime",
                model_name="gemini-3.1-flash-lite",
                script_data=script_data,
                is_historical_or_scientific=True
            )

            # Sparse fact-check keeps one retry so bad chunks fail softly without long stalls.
            assert mock_call.call_count == 2
            assert res[0]["action_detail_vi"] == "Cũ"
            assert res[0]["verification_status"] == "needs_review"
            assert "missing continuity anchor citation" in res[0]["fact_check_note_vi"]

    finally:
        db.close()


def test_validate_scene_word_limit():
    valid_anchor = {"continuity_prompt_en": "approved context"}
    scene = {
        "voice_over_en": "Cinematic voice narration",
        "veo3_prompt_en": "Reference the approved " + "word " * 80,  # 84 words
        "needs_fact_check": False
    }
    errors = validate_scene(normalize_scene(scene), valid_anchor)
    assert any("veo3_prompt_en exceeds 80 words" in e for e in errors)


@pytest.mark.asyncio
async def test_pipeline_observability_and_snapshots():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    import os, shutil
    # Clean up old debug snapshots if any
    snapshot_dir = os.path.join(os.getcwd(), "debug_snapshots")
    if os.path.exists(snapshot_dir):
        shutil.rmtree(snapshot_dir)
        
    try:
        db.query(Project).delete()
        db.query(APIKey).delete()
        db.commit()

        key_in = APIKeyCreate(owner="Test Obs Owner", quota_limit=5)
        _, api_key = create_api_key(db, key_in)

        project = create_project(
            db=db,
            api_key_id=api_key.id,
            title="Test Observability Snapshots",
            input_type="manual",
            input_content="Obs",
            style="anime",
            num_scenes=1
        )

        service = ProductionService(api_key="test_key", groq_api_key=None, db=db, api_key_id=api_key.id)
        service.batch_mode = True

        mock_meta = json.dumps({
            "prompt_0": {
                "primary_subject_en": "Subject lock",
                "hard_visual_lock_en": "Visual lock",
                "setting_lock_en": "Setting lock",
                "character_lock": [{"name": "Hero", "description_en": "Hero desc"}],
                "camera_lock_en": "Camera lock",
                "voice_sound_lock_en": "Voice lock",
                "action_story_logic_en": "Logic lock",
                "scene_function_rules_en": "Rules lock",
                "continuity_lock_en": "Continuity lock",
                "internal_logic_en": "Internal logic",
                "negative_constraints_en": "Negative constraints"
            },
            "overview_analysis_vi": "Phân tích",
            "storyline_vi": "Cốt truyện",
            "stages_vi": "Giai đoạn 1",
            "progression_vi": "Tiến trình",
            "camera_strategy_vi": "Chiến lược",
            "continuity_locks_vi": "Khóa liên tục",
            "form_locks_vi": "Khóa cứng",
            "age_stage_locks_vi": "Khóa tuổi",
            "geometry_locks_vi": "Khóa hình học",
            "risk_logic_vi": "Rủi ro",
            "voice_sound_strategy_vi": "Âm thanh",
            "characters": [{"character_name": "Hero", "description_en": "Hero desc", "key_identifiers_en": "hero"}],
            "environment_master_prompt_en": "Forest"
        })
        mock_arc = json.dumps({
            "emotion_arc": [{"scene_number": 1, "emotion_label": "căng thẳng", "beat_summary": "Khởi đầu", "physical_state_end": "Đứng", "camera_complexity": "low", "scene_lead_character": "Hero"}]
        })
        mock_scene = json.dumps({
            "scenes": [{
                "scene_number": 1,
                "title": "Scene 1 [00:00 - 00:08]",
                "action_detail_vi": "Hero xuất hiện",
                "veo3_prompt_en": "Reference the approved Hero, realistic style, voice: \"The story begins.\"",
                "voice_over_en": "The story begins.",
                "needs_fact_check": False,
                "fact_check_note_vi": None,
                "historical_basis_vi": None
            }]
        })
        mock_global = json.dumps({
            "background_ref_prompt_en": "Forest background",
            "thumbnail_ref_prompt_en": "Epic hero thumbnail"
        })

        with patch.object(service, "_call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [
                mock_meta,
                mock_arc,
                mock_scene,
                mock_global
            ]

            events = []
            async for ev in service.generate_full_script_stream(
                suggestion={"index": 0, "title": "T", "synopsis": "S", "topic_type": "fictional_original"},
                style="anime",
                num_scenes=1,
                project_id=project.id,
                db=db,
                batch_mode=True
            ):
                events.append(ev)

            # Check that phase logs are saved in DB
            db.refresh(project)
            assert project.phase_log is not None
            assert len(project.phase_log) > 0
            
            # Check debug snapshots are saved on disk
            assert os.path.exists(snapshot_dir)
            files = os.listdir(snapshot_dir)
            assert len(files) > 0
            assert any("phase_0_prompt0_blueprint" in f for f in files)
            assert any("phase_1_emotion_arc" in f for f in files)
            assert any("phase_2_scenes" in f for f in files)
            assert any("phase_3_packaging" in f for f in files)

    finally:
        # Clean up
        if os.path.exists(snapshot_dir):
            shutil.rmtree(snapshot_dir)
        db.close()


def test_sync_emotion_arc_with_scenes():
    from app.services.production.base import sync_emotion_arc_with_scenes
    
    script_data = {
        "emotion_arc": [
            {"scene_number": 1, "emotion_label": "Tò mò", "beat_summary": "Original beat summary 1"},
            {"scene_number": 2, "emotion_label": "Quyết tâm", "beat_summary": "Original beat summary 2"},
            {"scene_number": 3, "emotion_label": "Bình yên", "beat_summary": "Original beat summary 3"},
        ],
        "scenes": [
            {"scene_number": 1, "action_detail_vi": "New action detail 1"},
            {"scene_number": 2, "action_detail_vi": "New action detail 2"},
        ]
    }
    
    sync_emotion_arc_with_scenes(script_data)
    
    assert script_data["emotion_arc"][0]["beat_summary"] == "New action detail 1"
    assert script_data["emotion_arc"][1]["beat_summary"] == "New action detail 2"
    assert script_data["emotion_arc"][2]["beat_summary"] == "Original beat summary 3"
