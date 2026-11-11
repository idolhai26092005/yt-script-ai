import re
import logging
from app.services.gemini.base import BaseGeminiService

logger = logging.getLogger("uvicorn.error")

MAX_VEO_PROMPT_WORDS = 80  # Tăng từ 50 → 80 để match format mẫu (embedded voice line)
STREAM_DELAY = 0.05
MAX_BATCH_PROMPT_CHARS = 30000


def _trim_text(value: str, limit: int = 360) -> str:
    value = re.sub(r"\s+", " ", (value or "").strip())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def build_prompt_0_text(prompt_0: dict) -> str:
    """
    Converts a prompt_0 dict into a readable text block for embedding
    in batch scene generation prompts (like the voi.txt sample format).
    """
    if not prompt_0:
        return "No Prompt 0 available."

    lines = ["Prompt 0", "Identity / Species Lock", ""]

    if s := prompt_0.get("primary_subject_en"):
        lines.append(f"Primary Subject: {s}")

    if s := prompt_0.get("hard_visual_lock_en"):
        lines += ["", "Hard Visual / Form Lock:", s]

    if s := prompt_0.get("setting_lock_en"):
        lines += ["", "Setting / Habitat / World Lock:", s]

    for char in prompt_0.get("character_lock", []):
        name = char.get("name", "Character")
        desc = char.get("description_en", "")
        if name and desc:
            lines += ["", f"Character Lock — {name}:", desc]

    if s := prompt_0.get("camera_lock_en"):
        lines += ["", "Camera Lock:", s]

    if s := prompt_0.get("voice_sound_lock_en"):
        lines += ["", "Voice / Sound Lock:", s]

    if s := prompt_0.get("action_story_logic_en"):
        lines += ["", "Action / Story Logic:", s]

    if s := prompt_0.get("scene_function_rules_en"):
        lines += ["", "Scene Function Rules:", s]

    if s := prompt_0.get("continuity_lock_en"):
        lines += ["", "Continuity Lock:", s]

    if s := prompt_0.get("internal_logic_en"):
        lines += ["", "Internal Logic:", s]

    if s := prompt_0.get("negative_constraints_en"):
        lines += ["", "Negative Constraints:", s]

    return "\n".join(lines)


def build_compact_prompt_0_text(prompt_0: dict, priority_character_names: list[str] | None = None) -> str:
    """
    Token-bounded Prompt 0 for batch generation. Keeps only identity,
    visual, continuity, story-logic, and negative locks.
    """
    if not prompt_0:
        return "No Prompt 0 available."

    lines = ["Prompt 0 Compact"]
    compact_fields = [
        ("Identity", prompt_0.get("primary_subject_en"), 320),
        ("Visual", prompt_0.get("hard_visual_lock_en"), 260),
        ("World", prompt_0.get("setting_lock_en"), 260),
        ("Camera", prompt_0.get("camera_lock_en"), 180),
        ("Story Logic", prompt_0.get("action_story_logic_en"), 360),
        ("Continuity", prompt_0.get("continuity_lock_en"), 260),
        ("Internal Logic", prompt_0.get("internal_logic_en"), 220),
        ("Negative", prompt_0.get("negative_constraints_en"), 220),
    ]
    for label, value, limit in compact_fields:
        if value:
            lines.append(f"{label}: {_trim_text(str(value), limit)}")

    priority = [name.lower() for name in (priority_character_names or []) if name]
    raw_chars = list(prompt_0.get("character_lock", []) or [])
    if priority:
        raw_chars.sort(key=lambda c: 0 if str(c.get("name", "")).lower() in priority else 1)

    chars = []
    for char in raw_chars:
        name = char.get("name", "Character")
        desc = _trim_text(char.get("description_en", ""), 220)
        if name and desc:
            chars.append(f"{name}: {desc}")
    if chars:
        lines.append("Characters: " + " | ".join(chars[:8]))

    return "\n".join(lines)


def parse_action_story_steps(action_story_logic_en: str) -> list[dict]:
    text = action_story_logic_en or ""
    matches = list(re.finditer(r"(?:^|\s)(\d+)[.)]\s*(.*?)(?=(?:\s+\d+[.)]\s*)|$)", text, re.DOTALL))
    if matches:
        return [
            {"step": int(m.group(1)), "label": _trim_text(m.group(2).strip(" .;:"), 140)}
            for m in matches
            if m.group(2).strip(" .;:")
        ]

    parts = [p.strip(" .;:") for p in re.split(r"[.;]\s*|,\s*", text) if p.strip(" .;:")]
    return [{"step": idx + 1, "label": _trim_text(part, 140)} for idx, part in enumerate(parts)]


def _trigger_for_text(text: str) -> str | None:
    lower = (text or "").lower()
    trigger_patterns = [
        ("alarm", [r"\balarms?\b", r"chuông báo", r"còi báo", r"báo động"]),
        ("resolution", [
            r"\bresolve", r"\bresolution\b", r"\bending\b", r"kết thúc", r"hồi kết",
            r"hòa hợp", r"hoà hợp", r"chung sống", r"cùng tồn tại",
            r"peaceful coexistence", r"\bcoexistence\b", r"mutual respect",
            r"sống sót", r"\bbình yên\b", r"bình minh.*(nghỉ|sống sót|yên|sau)",
            r"tháo mũ", r"cởi mũ", r"\bexhaustion.*(street|after|final)",
            r"\bsurvival.*(after|final)",
            r"hoàng hôn.*(trầm mặc|tĩnh|bao phủ|yếu)",
            r"đứng lặng.*(thiên nhiên|không gian)",
            r"lời chào cuối", r"không bao giờ trở lại",
            r"chọn hòa hợp", r"chấp nhận thất bại",
            r"từ bỏ ý định", r"không còn.*(sát khí|áp lực|kẻ thù)",
            r"\brời khỏi\b", r"\brời đi\b", r"\bquay về\b", r"\btrở về\b",
        ]),
    ]
    for trigger, patterns in trigger_patterns:
        if any(re.search(pattern, lower) for pattern in patterns):
            return trigger
    return None


def _parse_stage_ranges(stages_vi: str, num_scenes: int) -> tuple[list[dict], list[str]]:
    stage_ranges = []
    coverage_errors = []
    stage_text = re.sub(r"\s+", " ", stages_vi or "").strip()
    if not stage_text:
        return [{
            "scene_start": 1,
            "scene_end": num_scenes,
            "label": "Full continuous journey",
            "trigger": None,
            "source": "fallback",
        }], coverage_errors

    # Split on separators only when they introduce another stage/range. This
    # keeps normal sentence punctuation inside descriptions from truncating the
    # current stage while preventing one match from swallowing all later stages.
    block_pattern = re.compile(
        r"(?:^|[;\n.]\s*)"
        r"("
        r"(?:(?:Giai\s*đoạn|Stage)\s*\d+[^;\n.]*?)?"
        r"(?:"
        r"\(\s*(?:(?:Cảnh|Scene|Scenes)\s*)?\d+\s*(?:[-–]|to|đến)\s*\d+\s*\)"
        r"|"
        r"(?:Cảnh|Scene|Scenes)\s*\d+\s*(?:[-–]|to|đến)\s*\d+"
        r")"
        r"[^;\n.]*"
        r")",
        re.IGNORECASE,
    )
    range_pattern = re.compile(
        r"(?:"
        r"\(\s*(?:(?:Cảnh|Scene|Scenes)\s*)?(\d+)\s*(?:[-–]|to|đến)\s*(\d+)\s*\)"
        r"|"
        r"(?:Cảnh|Scene|Scenes)\s*(\d+)\s*(?:[-–]|to|đến)\s*(\d+)"
        r")",
        re.IGNORECASE,
    )

    for block_match in block_pattern.finditer(stage_text):
        block = block_match.group(1).strip(" ;.")
        range_match = range_pattern.search(block)
        if not range_match:
            continue
        start_raw = range_match.group(1) or range_match.group(3)
        end_raw = range_match.group(2) or range_match.group(4)
        start = max(1, int(start_raw))
        end = min(num_scenes, int(end_raw))
        if start > end:
            coverage_errors.append(f"Invalid stage range {start_raw}-{end_raw}")
            continue
        label = _trim_text(re.sub(r"\s+", " ", block).strip(" :–-"), 120)
        stage_ranges.append({
            "scene_start": start,
            "scene_end": end,
            "label": label or f"Scenes {start}-{end}",
            "trigger": _trigger_for_text(label or ""),
        })

    stage_ranges.sort(key=lambda s: (s["scene_start"], s["scene_end"]))
    if not stage_ranges:
        return [{
            "scene_start": 1,
            "scene_end": num_scenes,
            "label": "Full continuous journey",
            "trigger": None,
            "source": "fallback",
        }], coverage_errors

    expected = 1
    for stage in stage_ranges:
        start = stage["scene_start"]
        end = stage["scene_end"]
        if start < expected:
            coverage_errors.append(f"Stage ranges overlap before scene {expected}: {start}-{end}")
        if start > expected:
            coverage_errors.append(f"Stage ranges leave gap {expected}-{start - 1}")
        expected = max(expected, end + 1)
    if expected <= num_scenes:
        coverage_errors.append(f"Stage ranges leave gap {expected}-{num_scenes}")

    return stage_ranges, coverage_errors


def _stage_for_step(step: dict, idx: int, total_steps: int, stage_ranges: list[dict]) -> dict:
    trigger = step.get("trigger")
    if trigger:
        for stage in stage_ranges:
            if stage.get("trigger") == trigger:
                return stage
    stage_idx = min(len(stage_ranges) - 1, int(idx * len(stage_ranges) / max(total_steps, 1)))
    return stage_ranges[stage_idx]


# Durable longform-stage guard: scene batches must receive only overlapping
# stage text so later chapters cannot leak into early Project-19-style batches.
def stage_context_for_range(story_spine: dict, batch_start: int, batch_end: int) -> str:
    stage_ranges = story_spine.get("stage_ranges") or []
    active = [
        stage for stage in stage_ranges
        if int(stage.get("scene_start") or 0) <= batch_end
        and int(stage.get("scene_end") or 0) >= batch_start
    ]
    if not active:
        return f"Scenes {batch_start}-{batch_end} of the story."

    lines = ["=== ACTIVE STAGE CONTEXT (range-scoped) ==="]
    for stage in active:
        start = int(stage.get("scene_start") or batch_start)
        end = int(stage.get("scene_end") or batch_end)
        label = _trim_text(str(stage.get("label") or f"Scenes {start}-{end}"), 220)
        lines.append(f"- Scenes {start}-{end}: {label}")
    lines.append("Rule: use only the active stage(s) above for this batch.")
    lines.append("=== END ACTIVE STAGE CONTEXT ===")
    return "\n".join(lines)


def build_story_spine(prompt_0: dict, stages_vi: str, num_scenes: int) -> dict:
    """
    Builds a compact one-journey state machine from Prompt 0. No LLM call.
    """
    steps = parse_action_story_steps(prompt_0.get("action_story_logic_en", ""))
    if not steps:
        steps = [
            {"step": 1, "label": "setup"},
            {"step": 2, "label": "escalation"},
            {"step": 3, "label": "climax"},
            {"step": 4, "label": "resolution"},
        ]

    stage_ranges, coverage_errors = _parse_stage_ranges(stages_vi, num_scenes)
    if any("leave gap" in err or "missing" in err for err in coverage_errors):
        stage_ranges = [{
            "scene_start": 1,
            "scene_end": num_scenes,
            "label": "Full continuous journey",
            "trigger": None,
            "source": "coverage_fallback",
        }]
    total_steps = max(len(steps), 1)
    for idx, step in enumerate(steps):
        step["trigger"] = _trigger_for_text(step.get("label", ""))
        stage = _stage_for_step(step, idx, total_steps, stage_ranges)
        step["scene_start"] = stage["scene_start"]
        step["scene_end"] = stage["scene_end"]
        step["stage_label"] = stage.get("label", "")
        step["allowed_once"] = bool(step["trigger"])

    once_triggers = []
    for step in steps:
        trigger = step.get("trigger")
        if trigger and trigger not in once_triggers:
            once_triggers.append(trigger)

    return {
        "version": "1.2",
        "mode": "single_journey",
        "total_scenes": num_scenes,
        "steps": steps,
        "stage_ranges": stage_ranges,
        "coverage_errors": coverage_errors,
        "allowed_once_triggers": once_triggers,
    }


def story_spine_context(story_spine: dict, batch_start: int, batch_end: int, used_triggers: list[str] | None = None) -> str:
    steps = story_spine.get("steps") or []
    active = [
        s for s in steps
        if s.get("scene_start", 0) <= batch_end and s.get("scene_end", 0) >= batch_start
    ]
    if not active and steps:
        active = [min(steps, key=lambda s: abs((s.get("scene_start", 1) + s.get("scene_end", 1)) // 2 - batch_start))]

    completed = [
        s.get("trigger")
        for s in steps
        if s.get("trigger") and s.get("scene_end", 0) < batch_start
    ]
    for trigger in used_triggers or []:
        if trigger not in completed:
            completed.append(trigger)

    lines = ["=== STORY SPINE STATE (compact, one journey only) ==="]
    lines.append(f"Mode: {story_spine.get('mode', 'single_journey')}; batch: scenes {batch_start}-{batch_end}")
    if completed:
        lines.append("Completed hard triggers: " + ", ".join(completed))
    else:
        lines.append("Completed hard triggers: none")
    for s in active[:4]:
        trigger = s.get("trigger") or "none"
        lines.append(
            f"Step {s.get('step')} [{s.get('scene_start')}-{s.get('scene_end')}], "
            f"trigger={trigger}: {_trim_text(s.get('label', ''), 160)}"
        )
    lines.append("Rule: do not reuse completed hard triggers; do not create a second mini-story cycle.")
    lines.append("=== END STORY SPINE STATE ===")
    return "\n".join(lines)


def future_targets_context(story_spine: dict, batch_start: int, batch_end: int) -> str:
    """Compact spoiler map: later payoffs are reserved, not available to current batch."""
    total = int(story_spine.get("total_scenes") or batch_end)
    future_stages = [
        s for s in story_spine.get("stage_ranges") or []
        if int(s.get("scene_end") or total) > batch_end
    ]
    future_steps = [
        s for s in story_spine.get("steps") or []
        if int(s.get("scene_end") or total) > batch_end
    ]
    if not future_stages and not future_steps:
        return (
            "=== FUTURE TARGETS (reserved payoffs) ===\n"
            f"Current batch scenes {batch_start}-{batch_end} is at the end of the journey.\n"
            "Rule: deliver only the final payoff that belongs to this range.\n"
            "=== END FUTURE TARGETS ==="
        )

    lines = ["=== FUTURE TARGETS (reserved payoffs) ==="]
    lines.append(f"Current batch scenes {batch_start}-{batch_end}; total scenes {total}.")
    if future_stages:
        lines.append("Later stage targets:")
        for s in future_stages[:4]:
            trigger = s.get("trigger") or "none"
            lines.append(
                f"- Scenes {s.get('scene_start')}-{s.get('scene_end')}, "
                f"trigger={trigger}: {_trim_text(s.get('label', ''), 140)}"
            )
    reserved_steps = []
    for s in future_steps:
        label = _trim_text(s.get("label", ""), 100)
        if label:
            reserved_steps.append(f"{s.get('scene_start')}-{s.get('scene_end')}: {label}")
        if len(reserved_steps) >= 5:
            break
    if reserved_steps:
        lines.append("Reserved future payoffs:")
        lines.extend(f"- {step}" for step in reserved_steps)
    lines.append(
        "Rule: current batch may foreshadow these targets, but MUST NOT resolve, complete, "
        "or spend any listed future payoff before its scene range."
    )
    lines.append("=== END FUTURE TARGETS ===")
    return "\n".join(lines)


def merge_scenes_data(orig_scenes: list, updated_scenes: list) -> list:
    """
    Merge fields from updated_scenes into orig_scenes based on scene_number.
    Returns the full list of orig_scenes with updated scenes overwritten.
    """
    up_by_num = {s["scene_number"]: s for s in updated_scenes if "scene_number" in s}
    merged = []
    for orig_s in orig_scenes:
        num = orig_s.get("scene_number")
        if num in up_by_num:
            up_s = up_by_num[num]
            merged_s = orig_s.copy()
            for key, val in up_s.items():
                merged_s[key] = val
            merged.append(merged_s)
        else:
            merged.append(orig_s)
    return merged


def sync_emotion_arc_with_scenes(script_data: dict) -> None:
    """
    Synchronizes script_data["emotion_arc"] with script_data["scenes"] after merge operations.

    Fix 4: After fact-check, updates both beat_summary AND physical_state_end for scenes that were
    modified (needs_fact_check=True). physical_state_end is derived from the last sentence of
    action_detail_vi to reflect the corrected physical state.
    """
    scenes_by_num = {s["scene_number"]: s for s in script_data.get("scenes", []) if "scene_number" in s}
    for entry in script_data.get("emotion_arc", []):
        num = entry.get("scene_number")
        if num not in scenes_by_num:
            continue

        scene = scenes_by_num[num]
        action_vi = scene.get("action_detail_vi") or ""

        # Always sync beat_summary
        if action_vi:
            entry["beat_summary"] = action_vi

        # Fix 4: If the scene was fact-checked or semantic-verified and modified, derive new physical_state_end
        # from the last sentence of action_detail_vi (most likely describes end-of-scene state)
        if (scene.get("needs_fact_check") or scene.get("_semantic_verified_edit")) and action_vi:
            sentences = [s.strip() for s in action_vi.replace(".", ".\n").split("\n") if s.strip()]
            if sentences:
                # Use the last non-trivial sentence as the new physical state anchor
                last_sentence = sentences[-1].rstrip(".")
                if len(last_sentence) > 10:  # Only update if meaningful
                    entry["physical_state_end"] = last_sentence


def extract_voice_from_prompt(veo3_prompt_en: str) -> str:
    """
    Extracts the embedded voice narration from a veo3_prompt_en string.
    Looks for the pattern: voice: "..." or voice: '...'
    """
    if not veo3_prompt_en:
        return ""
    match = re.search(r'voice:\s*["\']([^"\']+)["\']', veo3_prompt_en, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def scene_handoff_state(scene: dict | None, fallback: str = "") -> str:
    """
    Builds the physical continuity handoff from the actual saved scene, not from
    the planned arc. This keeps reconnect/resume from restarting earlier beats.
    """
    if not scene:
        return fallback

    action_vi = (scene.get("action_detail_vi") or "").strip()
    if action_vi:
        sentences = [
            s.strip()
            for s in re.split(r"[.!?\n]+", action_vi)
            if s.strip()
        ]
        if sentences:
            return sentences[-1]
        return action_vi

    prompt = (scene.get("veo3_prompt_en") or "").strip()
    if prompt:
        prompt = re.sub(r",?\s*voice:\s*[\"'].*?[\"']\s*$", "", prompt, flags=re.IGNORECASE)
        return prompt[:220]

    return fallback


def standardize_scene_titles(scenes: list, scene_duration_sec: int) -> list:
    """
    Standardize the title field of all scenes to the format:
    'Scene {scene_number} [mm:ss - mm:ss]'
    """
    for s in scenes:
        num = s.get("scene_number", 1)
        start_sec = (num - 1) * scene_duration_sec
        end_sec = num * scene_duration_sec

        start_min, start_s = start_sec // 60, start_sec % 60
        end_min, end_s = end_sec // 60, end_sec % 60

        s["title"] = f"Scene {num} [{start_min:02d}:{start_s:02d} - {end_min:02d}:{end_s:02d}]"
    return scenes
