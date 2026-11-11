from dataclasses import dataclass
from typing import Optional, List
import re

# Validation ownership guard: this file is the byte-preserving home of the legacy
# validators while contract-specific modules expose narrower import surfaces.

MAX_VEO_PROMPT_WORDS = 80  # Increased from 50 to match sample format with embedded voice
REQUIRED_BLUEPRINT_FIELDS = [
    "stages_vi",
    "progression_vi",
    "camera_strategy_vi",
    "continuity_locks_vi",
    "form_locks_vi",
    "age_stage_locks_vi",
    "geometry_locks_vi",
    "risk_logic_vi",
    "voice_sound_strategy_vi",
]
REQUIRED_PROMPT_0_KEYS = [
    "primary_subject_en",
    "hard_visual_lock_en",
    "setting_lock_en",
    "character_lock",
    "camera_lock_en",
    "voice_sound_lock_en",
    "action_story_logic_en",
    "scene_function_rules_en",
    "continuity_lock_en",
    "internal_logic_en",
    "negative_constraints_en",
]


@dataclass(frozen=True)
class SceneContract:
    """Schema-agnostic contract for a single scene (v2.0)."""
    veo3_prompt_en: str
    voice_over_en: Optional[str]
    scene_specific_negative_en: Optional[str]
    needs_fact_check: bool
    fact_check_note_vi: Optional[str]


@dataclass(frozen=True)
class ScriptContract:
    """Schema-agnostic contract for a full script."""
    emotion_arc: List[dict]
    scenes: List[dict]
    characters: List[dict]
    environment_master_prompt_en: str


@dataclass(frozen=True)
class ValidationIssue:
    """A validation finding with gate severity.

    BLOCK is reserved for deterministic contract failures. RETRY means the
    current LLM attempt should be regenerated, but it is not necessarily a
    final pipeline blocker. WARN is advisory and must not stop generation.
    """
    message: str
    severity: str = "WARN"
    code: str = "validation"
    scene_number: int | None = None
    phase: str | None = None


BLOCK = "BLOCK"
RETRY = "RETRY"
WARN = "WARN"


def issue_messages(issues: list[ValidationIssue]) -> list[str]:
    return [issue.message for issue in issues]


def blocking_messages(issues: list[ValidationIssue]) -> list[str]:
    return [issue.message for issue in issues if issue.severity == BLOCK]


def retryable_messages(issues: list[ValidationIssue]) -> list[str]:
    return [issue.message for issue in issues if issue.severity in (BLOCK, RETRY)]


# Durable story-contract guard: topic adherence uses terms generated from the
# screenplay's own contract, avoiding new domain-specific regex gates.
def _story_contract_text_values(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, dict):
        texts: list[str] = []
        for nested in value.values():
            texts.extend(_story_contract_text_values(nested))
        return texts
    return []


# Durable story-contract guard: tokenization is intentionally generic and
# conservative so creative wording stays flexible while obvious takeover is visible.
def _story_contract_terms(contract: dict, keys: list[str]) -> set[str]:
    stopwords = {
        "the", "and", "with", "from", "into", "this", "that", "story", "video",
        "main", "central", "core", "young", "ancient", "giant", "cảnh", "cau",
        "chuyen", "nhan", "vat", "muc", "tieu", "chinh", "trung", "tam", "mot",
    }
    terms: set[str] = set()
    for key in keys:
        for text in _story_contract_text_values(contract.get(key)):
            for token in re.findall(r"[A-Za-zÀ-ỹ0-9][A-Za-zÀ-ỹ0-9_-]{2,}", text.lower()):
                normalized = token.strip("_-")
                if len(normalized) >= 3 and normalized not in stopwords:
                    terms.add(normalized)
    return terms


# Durable story-contract guard: counting contract-derived terms is a cheap signal,
# not a creative hard gate; callers decide whether to retry early or warn softly.
def _story_contract_term_hits(text: str, terms: set[str]) -> int:
    low = (text or "").lower()
    return sum(1 for term in terms if term and term in low)


# Durable story-contract guard: Phase 0 contract shape is technical, while
# alignment findings stay WARN so soft-fiction quality issues do not kill output.
def validate_story_contract_issues(script_data: dict) -> list[ValidationIssue]:
    """Validate generic central-subject alignment without domain-specific rules."""
    script_data = _legacy_script_view(script_data)
    contract = script_data.get("story_contract") or {}
    issues: list[ValidationIssue] = []
    required = [
        "main_subject_en",
        "protagonist_en",
        "central_opponent_or_force_en",
        "core_goal_en",
        "must_remain_visible_terms",
        "forbidden_takeover_rule",
    ]
    if not isinstance(contract, dict) or not contract:
        return [ValidationIssue("story_contract is empty after Phase 0", RETRY, "missing_story_contract")]
    for key in required:
        value = contract.get(key)
        if value in (None, "", []):
            issues.append(ValidationIssue(f"story_contract.{key} is empty", RETRY, "invalid_story_contract"))

    central_terms = _story_contract_terms(contract, [
        "main_subject_en",
        "main_subject_vi",
        "central_opponent_or_force_en",
        "central_opponent_or_force_vi",
        "core_goal_en",
        "core_goal_vi",
        "must_remain_visible_terms",
    ])
    side_terms = _story_contract_terms(contract, ["allowed_side_threats"])
    if not central_terms:
        issues.append(ValidationIssue("story_contract has no usable central terms", RETRY, "invalid_story_contract"))
        return issues

    storyline_hits = _story_contract_term_hits(script_data.get("storyline_vi", ""), central_terms)
    stage_text = script_data.get("stages_vi", "")
    stage_hits = _story_contract_term_hits(stage_text, central_terms)
    side_hits = _story_contract_term_hits(stage_text, side_terms)
    if storyline_hits == 0:
        issues.append(ValidationIssue(
            "story_contract central subject/opponent is missing from storyline_vi",
            WARN,
            "central_contract_storyline_drift",
        ))
    if stage_hits == 0:
        issues.append(ValidationIssue(
            "story_contract central subject/opponent is missing from stages_vi",
            WARN,
            "central_contract_stage_drift",
        ))
    if side_terms and side_hits and (stage_hits == 0 or side_hits > stage_hits):
        issues.append(ValidationIssue(
            "story_contract side threat appears stronger than the central subject/opponent in stages_vi",
            WARN,
            "central_contract_takeover_risk",
        ))
    return issues


# Durable story-contract guard: batch drift detection only inspects produced text
# against Phase 0 terms, preserving verifier speed by raising a flag only on drift.
def detect_story_contract_batch_drift(script_data: dict, scenes: list[dict]) -> str | None:
    """Return a soft warning when a scene batch drifts away from the central contract."""
    script_data = _legacy_script_view(script_data)
    contract = script_data.get("story_contract") or {}
    if not isinstance(contract, dict) or not scenes:
        return None
    central_terms = _story_contract_terms(contract, [
        "main_subject_en",
        "main_subject_vi",
        "central_opponent_or_force_en",
        "central_opponent_or_force_vi",
        "core_goal_en",
        "core_goal_vi",
        "must_remain_visible_terms",
    ])
    side_terms = _story_contract_terms(contract, ["allowed_side_threats"])
    if not central_terms:
        return None
    text = "\n".join(
        " ".join([
            str(_legacy_scene_view(scene).get("action_detail_vi") or ""),
            str(_legacy_scene_view(scene).get("veo3_prompt_en") or ""),
            str(_legacy_scene_view(scene).get("voice_over_en") or ""),
        ])
        for scene in scenes
    )
    central_hits = _story_contract_term_hits(text, central_terms)
    side_hits = _story_contract_term_hits(text, side_terms)
    if central_hits == 0 or (side_terms and side_hits > max(central_hits, 1)):
        nums = [scene.get("scene_number") for scene in scenes if scene.get("scene_number")]
        span = f"{min(nums)}-{max(nums)}" if nums else "unknown"
        return (
            f"central_contract_drift: scenes {span} underuse central subject/opponent "
            "or let side threat dominate."
        )
    return None


# Durable schema guard: validation reads a normalized flat view so v2/v3 JSON changes
# do not force every rule to know the public response layout.
def _legacy_scene_view(raw: dict | None) -> dict:
    if not isinstance(raw, dict):
        return {}
    if "source" not in raw:
        return raw
    source = raw.get("source") or {}
    display = raw.get("display") or {}
    verification = raw.get("verification") or {}
    generation = raw.get("generation") or {}
    notes = verification.get("notes_vi") or []
    return {
        "scene_number": raw.get("scene_number"),
        "title": (raw.get("timing") or {}).get("title"),
        "action_detail_vi": source.get("action_vi") or "",
        "veo3_prompt_en": source.get("veo_prompt_en") or "",
        "voice_over_en": source.get("voice_en"),
        "voice_over_vi": display.get("voice_vi"),
        "scene_specific_negative_en": source.get("scene_negative_en"),
        "historical_basis_vi": verification.get("basis_vi"),
        "verifiability_level": verification.get("level"),
        "needs_fact_check": verification.get("status") == "needs_review" or bool(verification.get("risk_flags")),
        "fact_check_note_vi": "; ".join(str(n) for n in notes if n) if notes else None,
        "generation_failed": bool(generation.get("failed")),
        "generation_error": generation.get("error"),
    }


# Durable schema guard: script validators operate on the same flat contract regardless
# of whether callers pass canonical v3 or legacy v2.
# Durable topic-contract guard: validators can read internal.story_contract from v3
# without exposing that internal field through legacy UI responses.
def _legacy_script_view(raw: dict | None) -> dict:
    if not isinstance(raw, dict) or raw.get("schema_version") != "3.0":
        return raw or {}
    topic = raw.get("topic") or {}
    plan = raw.get("production_plan") or {}
    anchors = raw.get("anchors") or {}
    internal = raw.get("internal") or {}
    pipeline = internal.get("pipeline") or {}
    validation = internal.get("validation") or {}
    return {
        "schema_version": "2.0",
        "topic_type": topic.get("type") or "fictional_original",
        "reality_binding_level": topic.get("reality_binding_level") or "soft",
        "overview_analysis_vi": plan.get("overview_vi") or "",
        "storyline_vi": plan.get("storyline_vi") or "",
        "stages_vi": plan.get("stages_vi") or "",
        "progression_vi": plan.get("progression_vi") or "",
        "camera_strategy_vi": plan.get("camera_strategy_vi") or "",
        "continuity_locks_vi": plan.get("continuity_locks_vi") or "",
        "form_locks_vi": plan.get("form_locks_vi") or "",
        "age_stage_locks_vi": plan.get("age_stage_locks_vi") or "",
        "geometry_locks_vi": plan.get("geometry_locks_vi") or "",
        "risk_logic_vi": plan.get("risk_logic_vi") or "",
        "voice_sound_strategy_vi": plan.get("voice_sound_strategy_vi") or "",
        "prompt_0": anchors.get("prompt_0") or {},
        "continuity_evolution": anchors.get("continuity_evolution") or {},
        "characters": anchors.get("characters") or [],
        "environment_master_prompt_en": anchors.get("environment_master_prompt_en") or "",
        "environment_master_prompt_vi": anchors.get("environment_master_prompt_vi") or "",
        "continuity_prompt_en": anchors.get("continuity_prompt_en") or "",
        "continuity_prompt_vi": anchors.get("continuity_prompt_vi") or "",
        "continuity_board": {
            "continuity_prompt_en": anchors.get("continuity_prompt_en") or "",
            "continuity_prompt_vi": anchors.get("continuity_prompt_vi") or "",
        },
        "global_negative_prompt_en": anchors.get("global_negative_prompt_en") or "",
        "emotion_arc": raw.get("emotion_arc") or [],
        "scenes": [_legacy_scene_view(scene) for scene in raw.get("scenes") or []],
        "story_spine": internal.get("story_spine") or {},
        "story_contract": internal.get("story_contract") or {},
        "quality_warnings": validation.get("quality_warnings") or [],
        "_fact_check_completed": bool(pipeline.get("fact_check_completed")),
        "_semantic_verifier_completed": bool(pipeline.get("semantic_verifier_completed")),
    }


def normalize_scene(raw: dict) -> SceneContract:
    """
    Normalizes raw scene dictionary to a SceneContract (v2.0).
    voice_over_en replaces voice_over_vi as the primary voice field.
    """
    scene = _legacy_scene_view(raw)
    return SceneContract(
        veo3_prompt_en=scene.get("veo3_prompt_en") or "",
        voice_over_en=scene.get("voice_over_en") or scene.get("voice_over_vi"),  # fallback to vi
        scene_specific_negative_en=scene.get("scene_specific_negative_en"),
        needs_fact_check=bool(scene.get("needs_fact_check")),
        fact_check_note_vi=scene.get("fact_check_note_vi"),
    )


# Durable validation guard: constraint extraction consumes the normalized contract
# so future JSON nesting does not change safety checks.
def build_constraint_model(script_data: dict) -> dict:
    """Derive measurable hard constraints from Prompt 0 locks."""
    script_data = _legacy_script_view(script_data)
    p0 = script_data.get("prompt_0") or {}
    negative_text = str(p0.get("negative_constraints_en") or script_data.get("global_negative_prompt_en") or "")
    internal_text = str(p0.get("internal_logic_en") or "")
    setting_text = " ".join([
        str(p0.get("setting_lock_en") or ""),
        str(script_data.get("environment_master_prompt_en") or ""),
        internal_text,
    ]).lower()
    combined = f"{negative_text}\n{internal_text}".lower()

    flags = {
        "forbid_fire": bool(re.search(r"\bno\s+(fire|flames?|open flame|campfire|torches?)\b|không\s+(lửa|ngọn lửa|đốt lửa)", combined)),
        "forbid_superhuman_strength": bool(re.search(r"no\s+superhuman|no\s+impossible\s+strength|không\s+(siêu sức mạnh|sức mạnh phi thường)", combined)),
        "forbid_modern": bool(re.search(r"no\s+modern|không\s+hiện đại", combined)),
        "allow_extreme_heat": bool(re.search(r"\b(forge|furnace|blast furnace|foundry|industrial kiln|lava|molten metal source)\b", setting_text)),
    }
    constraints: list[str] = []
    for raw_line in re.split(r"[\n.;]+", negative_text):
        line = re.sub(r"\s+", " ", raw_line).strip(" -")
        if line and re.search(r"\bno\b|không", line, re.IGNORECASE):
            constraints.append(line)
    if flags["forbid_fire"] and not any("fire" in c.lower() or "lửa" in c.lower() for c in constraints):
        constraints.append("No fire, flames, torches, campfires, or firelight.")
    if flags["forbid_superhuman_strength"] and not any("superhuman" in c.lower() for c in constraints):
        constraints.append("No superhuman strength or bare-handed heavy lifting.")
    return {"flags": flags, "constraints": constraints[:8]}


def scene_specific_negative_from_constraints(script_data: dict, scene: dict | None = None) -> str:
    model = build_constraint_model(script_data)
    constraints = model.get("constraints") or []
    if not constraints:
        return ""
    text = _compact_action_text(" ".join([
        str((scene or {}).get("action_detail_vi") or ""),
        str((scene or {}).get("veo3_prompt_en") or ""),
    ]))
    selected = []
    for constraint in constraints:
        low = constraint.lower()
        if len(selected) < 2:
            selected.append(constraint)
        elif ("fire" in low or "lửa" in low) and re.search(r"fire|flame|spark|flint|lửa|đốt", text):
            selected.append(constraint)
        elif "superhuman" in low and re.search(r"lift|pull|drag|raise|nâng|kéo|nhấc", text):
            selected.append(constraint)
    return ", ".join(dict.fromkeys(selected[:4]))


# Durable validation guard: scene-level semantic helpers consume normalized fields
# so v3 nesting does not hide action text from warning checks.
def validate_scene_lead_character(raw_scene: dict, known_character_names: list[str]) -> list[str]:
    """
    Fix 7: Validates that scene_lead_character is consistent with action_detail_vi.
    Returns a list of warning strings (not blocking errors).
    """
    raw_scene = _legacy_scene_view(raw_scene)
    warnings = []
    lead = raw_scene.get("scene_lead_character", "")
    action_vi = raw_scene.get("action_detail_vi", "")
    scene_num = raw_scene.get("scene_number", "?")

    # Skip check if character is None/empty or unknown
    if not lead or lead.lower() in ("none", ""):
        return warnings

    # Check if the claimed lead character name appears in action_detail_vi
    # Use partial match (case-insensitive) since Vietnamese may use different forms
    if action_vi and lead not in ("None",):
        lead_lower = lead.lower()
        action_lower = action_vi.lower()
        if lead_lower not in action_lower:
            warnings.append(
                f"Scene {scene_num}: scene_lead_character='{lead}' not found in action_detail_vi. "
                "Possible mismatch or wrong character assigned."
            )

    return warnings


# Durable schema guard: script normalization is the single adapter boundary for
# validation rules that should not care about public JSON nesting.
def normalize_script(raw: dict) -> ScriptContract:
    """
    Normalizes raw script dictionary to a ScriptContract.
    """
    script = _legacy_script_view(raw)
    return ScriptContract(
        emotion_arc=script.get("emotion_arc") or [],
        scenes=script.get("scenes") or [],
        characters=script.get("characters") or [],
        environment_master_prompt_en=script.get("environment_master_prompt_en") or "",
    )


def validate_scene_issues(scene: SceneContract, continuity_anchor: dict, scene_number: int | None = None) -> list[ValidationIssue]:
    """Validate a single scene and classify findings by gate severity."""
    issues: list[ValidationIssue] = []

    anchor_text = (continuity_anchor or {}).get("continuity_prompt_en") or ""
    if not anchor_text:
        issues.append(ValidationIssue(
            "continuity anchor is empty",
            BLOCK,
            "missing_continuity_anchor",
            scene_number,
        ))

    # 1. Continuity anchor citation check
    veo3_prompt = scene.veo3_prompt_en or ""
    if not veo3_prompt.startswith("Reference the approved"):
        issues.append(ValidationIssue(
            "missing continuity anchor citation (must start with 'Reference the approved')",
            RETRY,
            "missing_anchor_citation",
            scene_number,
        ))

    # 2. veo3_prompt_en word count check
    word_count = len(veo3_prompt.split())
    if word_count > MAX_VEO_PROMPT_WORDS:
        issues.append(ValidationIssue(
            f"veo3_prompt_en exceeds {MAX_VEO_PROMPT_WORDS} words ({word_count})",
            WARN,
            "long_veo_prompt",
            scene_number,
        ))

    # 3. voice_over_en validation check
    if not scene.voice_over_en:
        issues.append(ValidationIssue(
            "missing voice_over_en",
            RETRY,
            "missing_voice_over",
            scene_number,
        ))
    elif len(re.findall(r"\b[\w'-]+\b", scene.voice_over_en)) > 10:
        issues.append(ValidationIssue(
            "voice_over_en exceeds 10 words",
            WARN,
            "long_voice_over",
            scene_number,
        ))

    # 4. Fact-check note missing despite flag
    if scene.needs_fact_check and not scene.fact_check_note_vi:
        issues.append(ValidationIssue(
            "needs_fact_check=true but missing fact_check_note_vi",
            RETRY,
            "missing_fact_check_note",
            scene_number,
        ))

    return issues


def validate_scene(scene: SceneContract, continuity_anchor: dict) -> list[str]:
    """
    Backward-compatible scene validation API. New gate logic should use
    validate_scene_issues() so semantic/style findings do not all become hard
    pipeline blockers.
    """
    return issue_messages(validate_scene_issues(scene, continuity_anchor))


def _strip_negated_constraint_phrases(text: str) -> str:
    text = re.sub(r"\bno\s+(fire|flames?|open flames?|campfires?|torches?|superhuman strength|modern [^,.;]*)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"không\s+(lửa|ngọn lửa|đốt lửa|sức mạnh phi thường|siêu sức mạnh|hiện đại)", " ", text, flags=re.IGNORECASE)
    return text


# Durable validation guard: constraint violations are advisory heuristics over the
# normalized script, not schema-specific hard-coded JSON paths.
def validate_constraint_violations(script_data: dict) -> list[str]:
    """Hard gate positive use of concepts forbidden by Prompt 0."""
    script_data = _legacy_script_view(script_data)
    errors: list[str] = []
    model = build_constraint_model(script_data)
    flags = model.get("flags") or {}

    def check_text(prefix: str, raw_text: str) -> None:
        text = _strip_negated_constraint_phrases(raw_text or "")
        compact = _compact_action_text(text)
        if flags.get("forbid_fire"):
            fire_patterns = [
                r"\bwood fire\b", r"\bcampfire\b", r"\bopen flame\b", r"\bflames?\b",
                r"\btorches?\b", r"\bfirelight\b", r"\bflickering light\b",
                r"\bstrikes? flint\b.*\b(dry moss|tinder|kindling)\b",
                r"\bsparks?\b.*\b(dry moss|tinder|kindling)\b",
                r"\bđốt lửa\b", r"\bngọn lửa\b", r"\blửa bùng\b", r"\bánh lửa\b",
            ]
            if _has_any(compact, fire_patterns):
                errors.append(f"{prefix}: violates Prompt 0 negative constraint 'No fire'")
        if flags.get("forbid_superhuman_strength"):
            strength_patterns = [
                r"\bbare hands?\b.*\b(lift|raise|bend|tear|rip|hold|push)\b.*\b(beam|boulder|tree|iron|stone|debris)\b",
                r"\b(lifts?|raises?|bends?|tears?|rips?|holds?)\b.*\b(beam|boulder|tree|iron|stone|debris)\b.*\bbare hands?\b",
                r"\bwith bare hands?\b.*\b(beam|boulder|iron|stone)\b",
                r"\btay không\b.*\b(nâng|nhấc|kéo|bẻ|xé|giữ)\b.*\b(xà|dầm|sắt|đá|thân cây)\b",
                r"\b(nâng|nhấc|kéo|bẻ|xé|giữ)\b.*\b(xà|dầm|sắt|đá|thân cây)\b.*\btay không\b",
            ]
            if _has_any(compact, strength_patterns):
                errors.append(f"{prefix}: violates Prompt 0 negative constraint 'No superhuman strength'")
        if not flags.get("allow_extreme_heat"):
            heat_patterns = [
                r"\bmolten\s+(iron|steel|metal)\b",
                r"\bwhite[-\s]+hot\s+(iron|steel|metal|beam|crowbar)\b",
                r"\bred[-\s]+hot\s+(iron|steel|metal|beam|crowbar)\b",
                r"\bglowing\s+(iron|steel|metal|beam|crowbar)\b",
            ]
            if _has_any(compact, heat_patterns):
                errors.append(f"{prefix}: impossible hot metal without an approved extreme heat source")

    for entry in script_data.get("emotion_arc") or []:
        prefix = f"Emotion arc scene {entry.get('scene_number', '?')}"
        check_text(prefix, " ".join([
            str(entry.get("beat_summary") or ""),
            str(entry.get("physical_state_end") or ""),
        ]))

    ordered_scenes = sorted(
        [s for s in script_data.get("scenes") or [] if isinstance(s.get("scene_number"), int)],
        key=lambda s: s.get("scene_number", 0),
    )
    for scene in ordered_scenes:
        prefix = f"Scene {scene.get('scene_number', '?')}"
        check_text(prefix, " ".join([
            str(scene.get("action_detail_vi") or ""),
            str(scene.get("veo3_prompt_en") or ""),
            str(scene.get("voice_over_en") or ""),
        ]))

    if ordered_scenes:
        first = ordered_scenes[0]
        first_text = _compact_action_text(" ".join([
            str(first.get("action_detail_vi") or ""),
            str(first.get("veo3_prompt_en") or ""),
        ]))
        if re.search(r"\bsoot stained\b|bồ hóng|ám khói|soot", first_text) and re.search(r"\b(carriage|cart|wagon|arrives?|approaches?|ngồi|xe|đến nơi|tiếp cận)\b", first_text):
            errors.append("Scene 1: soot/smoke staining appears before a visible exposure cause")

    return errors


def validate_script(script: ScriptContract) -> list[str]:
    """
    Validates script-level structural integrity.
    """
    errors = []

    # 1. emotion_arc and scenes count check
    if len(script.emotion_arc) != len(script.scenes):
        errors.append("emotion_arc count does not match scenes count")

    # 2. characters list check
    if not script.characters:
        errors.append("characters list is empty")

    # 3. environment_master_prompt_en check
    if not script.environment_master_prompt_en:
        errors.append("missing environment_master_prompt_en")

    return errors


# Durable validation guard: blueprint completeness should survive v2/v3 migrations
# because Prompt 0 remains the required downstream anchor.
def validate_script_blueprint(script_data: dict) -> list[str]:
    """
    Fix 8: Validates that blueprint metadata fields are populated after Phase 0.
    Returns a list of warning strings indicating incomplete blueprint generation.
    This is a soft validation (warnings only, not blocking).
    """
    script_data = _legacy_script_view(script_data)
    warnings = []
    empty_fields = [f for f in REQUIRED_BLUEPRINT_FIELDS if not script_data.get(f)]
    if empty_fields:
        warnings.append(
            f"Blueprint metadata incomplete — the following fields are empty: {empty_fields}. "
            "This suggests Phase 0 blueprint generation may have partially failed."
        )

    # Check prompt_0 completeness
    p0 = script_data.get("prompt_0", {})
    if not p0 or p0 == {}:
        warnings.append("prompt_0 is empty — Phase 0 blueprint generation completely failed.")
    else:
        missing_p0 = [k for k in REQUIRED_PROMPT_0_KEYS if not p0.get(k)]
        if missing_p0:
            warnings.append(f"prompt_0 is missing required keys: {missing_p0}")

    return warnings


# Durable validation guard: Phase 0 still blocks only missing technical anchors after
# adapting public JSON into the internal contract.
def validate_blueprint_required(script_data: dict) -> list[str]:
    """Hard gate for Phase 0 output before downstream roles can run."""
    script_data = _legacy_script_view(script_data)
    errors = validate_script_blueprint(script_data)
    p0 = script_data.get("prompt_0") or {}
    if p0.get("continuity_lock_en") and not script_data.get("continuity_prompt_en"):
        errors.append("continuity_prompt_en is empty despite prompt_0.continuity_lock_en")
    if not script_data.get("characters"):
        errors.append("characters list is empty after Phase 0")
    if not script_data.get("environment_master_prompt_en"):
        errors.append("environment_master_prompt_en is empty after Phase 0")
    if not script_data.get("global_negative_prompt_en") and p0.get("negative_constraints_en"):
        errors.append("global_negative_prompt_en was not populated from prompt_0")
    return errors


# Durable validation guard: state invariants protect immutable anchors independent
# of whether the stored response is flat v2 or nested v3.
def validate_state_invariants(script_data: dict, locked_blueprint: dict | None = None) -> list[str]:
    """Hard gate that catches prompt_0/anchor loss between phases."""
    script_data = _legacy_script_view(script_data)
    errors = []
    p0 = script_data.get("prompt_0") or {}
    if not p0:
        errors.append("prompt_0 lost or empty")
    if not script_data.get("continuity_prompt_en"):
        errors.append("continuity_prompt_en lost or empty")
    if not script_data.get("continuity_board", {}).get("continuity_prompt_en"):
        errors.append("continuity_board.continuity_prompt_en lost or empty")
    if p0.get("continuity_lock_en") and script_data.get("continuity_prompt_en") != p0.get("continuity_lock_en"):
        errors.append("continuity_prompt_en diverged from prompt_0.continuity_lock_en")
    if locked_blueprint:
        locked_p0 = locked_blueprint.get("prompt_0") or {}
        if locked_p0 and p0 != locked_p0:
            errors.append("prompt_0 changed after Phase 0 without explicit edit")
        for field in REQUIRED_BLUEPRINT_FIELDS:
            if locked_blueprint.get(field) and not script_data.get(field):
                errors.append(f"{field} lost after Phase 0")
    return errors


def validate_emotion_arc_quality(emotion_arc: list[dict], expected_count: int) -> list[str]:
    """Reject placeholder/fallback emotion arcs before scene generation."""
    errors = []
    if len(emotion_arc) != expected_count:
        errors.append(f"emotion_arc length mismatch: expected {expected_count}, got {len(emotion_arc)}")
        return errors

    fallback_rows = []
    for entry in emotion_arc:
        label = (entry.get("emotion_label") or "").strip().lower()
        beat = (entry.get("beat_summary") or "").strip().lower()
        state = (entry.get("physical_state_end") or "").strip().lower()
        if label == "kịch tính" and beat.startswith("diễn biến cảnh") and state == "sẵn sàng cho cảnh tiếp theo":
            fallback_rows.append(entry.get("scene_number"))
        for key in ["emotion_label", "beat_summary", "physical_state_end", "camera_complexity"]:
            if not entry.get(key):
                errors.append(f"Scene {entry.get('scene_number', '?')}: emotion_arc missing {key}")
    if fallback_rows:
        errors.append(f"emotion_arc contains fallback placeholder rows: {fallback_rows[:10]}")
    return errors


def validate_story_spine_quality(script_data: dict) -> list[str]:
    """Validate the compact single-journey state machine created after Phase 0."""
    errors = []
    story_spine = script_data.get("story_spine") or {}
    total = story_spine.get("total_scenes")
    if story_spine.get("version") != "1.2":
        errors.append("story_spine version must be 1.2")
    if not isinstance(total, int) or total <= 0:
        errors.append("story_spine total_scenes is invalid")
    if story_spine.get("mode") != "single_journey":
        errors.append("story_spine mode must be single_journey")
    if story_spine.get("coverage_errors"):
        errors.extend([f"story_spine coverage error: {e}" for e in story_spine["coverage_errors"]])

    stage_ranges = story_spine.get("stage_ranges") or []
    if total and stage_ranges:
        covered = set()
        for stage in stage_ranges:
            start = int(stage.get("scene_start") or 0)
            end = int(stage.get("scene_end") or 0)
            if start < 1 or end > total or start > end:
                errors.append(f"story_spine invalid stage range {start}-{end}")
                continue
            covered.update(range(start, end + 1))
        if covered and covered != set(range(1, total + 1)):
            missing = sorted(set(range(1, total + 1)) - covered)
            if missing:
                errors.append(f"story_spine stage coverage missing scenes {missing[:12]}")

    for step in story_spine.get("steps") or []:
        start = int(step.get("scene_start") or 0)
        end = int(step.get("scene_end") or 0)
        if total and (start < 1 or end > total or start > end):
            errors.append(f"story_spine step {step.get('step')} has invalid range {start}-{end}")
    if not story_spine.get("steps"):
        errors.append("story_spine has no steps")
    return errors


def _compact_action_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^\w\sàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _has_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


STATE_TRIGGER_PATTERNS = {
    "alarm": [r"\balarms?\b", r"chuông báo", r"còi báo", r"báo động"],
    "resolution": [
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
    ],
}

STRICT_REPEAT_TRIGGERS = {"alarm", "resolution"}

LOCALIZED_HISTORICAL_NAME_ALIASES = {
    "qin shi huang": ["tần thủy hoàng", "tan thuy hoang"],
    "adolf hitler": ["hitler"],
    "hitler": ["adolf hitler"],
    "napoleon bonaparte": ["napoleon"],
    "napoleon": ["napoleon bonaparte"],
}


def scene_state_triggers(scene: dict) -> list[str]:
    text = _compact_action_text(
        " ".join([
            str(scene.get("action_detail_vi") or ""),
            str(scene.get("voice_over_en") or ""),
            str(scene.get("veo3_prompt_en") or ""),
        ])
    )
    triggers = []
    for trigger, patterns in STATE_TRIGGER_PATTERNS.items():
        if _has_any(text, patterns):
            triggers.append(trigger)
    return triggers


def emotion_arc_state_triggers(entry: dict) -> list[str]:
    text = _compact_action_text(
        " ".join([
            str(entry.get("beat_summary") or ""),
            str(entry.get("physical_state_end") or ""),
        ])
    )
    triggers = []
    for trigger, patterns in STATE_TRIGGER_PATTERNS.items():
        if _has_any(text, patterns):
            triggers.append(trigger)
    return triggers


def _trigger_ranges_from_spine(story_spine: dict) -> dict[str, list[tuple[int, int]]]:
    trigger_ranges: dict[str, list[tuple[int, int]]] = {}
    total = int(story_spine.get("total_scenes") or 9999)
    for source in (story_spine.get("stage_ranges") or []) + (story_spine.get("steps") or []):
        trigger = source.get("trigger")
        if not trigger:
            continue
        trigger_range = (
            int(source.get("scene_start") or 1),
            int(source.get("scene_end") or total),
        )
        if trigger_range not in trigger_ranges.setdefault(trigger, []):
            trigger_ranges[trigger].append(trigger_range)
    return trigger_ranges


def _trigger_repeat_errors(prefix: str, hits: dict[str, list[int]], trigger_ranges: dict[str, list[tuple[int, int]]]) -> list[str]:
    errors = []
    for trigger, scene_nums in hits.items():
        ranges = trigger_ranges.get(trigger) or []
        if ranges:
            out_of_range = [
                num for num in scene_nums
                if not any(start <= num <= end for start, end in ranges)
            ]
            if out_of_range:
                range_text = ", ".join(f"{start}-{end}" for start, end in ranges)
                errors.append(
                    f"{prefix} trigger '{trigger}' appears outside its assigned scene range {range_text} at scenes {out_of_range}"
                )
        if len(scene_nums) <= 1:
            continue
        if trigger not in STRICT_REPEAT_TRIGGERS:
            continue
        if trigger == "resolution" and ranges and all(
            any(start <= num <= end for start, end in ranges)
            for num in scene_nums
        ):
            continue
        clusters = []
        current = [scene_nums[0]]
        for num in scene_nums[1:]:
            if num <= current[-1] + 2:
                current.append(num)
            else:
                clusters.append(current)
                current = [num]
        clusters.append(current)
        if len(clusters) > 1:
            cluster_starts = [cluster[0] for cluster in clusters]
            errors.append(
                f"{prefix} trigger '{trigger}' repeats across separate cycles at scenes {cluster_starts}"
            )
    return errors


# Durable longform-stage guard: localized historical names bridge Vietnamese
# stage labels and English Prompt 0 locks without making arc generation retry.
def _character_aliases(char: dict) -> set[str]:
    aliases: set[str] = set()
    raw_values = [
        char.get("character_name"),
        char.get("description_en"),
        char.get("key_identifiers_en"),
    ]
    for value in raw_values:
        text = _compact_action_text(str(value or ""))
        if text:
            aliases.add(text)
    name = _compact_action_text(str(char.get("character_name") or ""))
    aliases.update(LOCALIZED_HISTORICAL_NAME_ALIASES.get(name, []))
    return {alias for alias in aliases if alias}


# Durable longform-stage guard: scene-stage checks run after concrete scene text
# exists, keeping emotion arc warnings cheap while blocking wrong-chapter output.
def validate_scene_stage_alignment(script_data: dict) -> list[ValidationIssue]:
    script_data = _legacy_script_view(script_data)
    if script_data.get("topic_type") not in ("historical", "scientific"):
        return []

    story_spine = script_data.get("story_spine") or {}
    stage_ranges = story_spine.get("stage_ranges") or []
    characters = script_data.get("characters") or []
    if not stage_ranges or not characters:
        return []

    aliases_by_name = {
        str(char.get("character_name") or f"character_{idx}"): _character_aliases(char)
        for idx, char in enumerate(characters)
    }
    arc_by_num = {
        entry.get("scene_number"): entry
        for entry in script_data.get("emotion_arc") or []
        if isinstance(entry.get("scene_number"), int)
    }
    issues: list[ValidationIssue] = []
    for scene in script_data.get("scenes") or []:
        scene_num = scene.get("scene_number")
        if not isinstance(scene_num, int):
            continue
        stage = next(
            (
                item for item in stage_ranges
                if int(item.get("scene_start") or 0) <= scene_num <= int(item.get("scene_end") or 0)
            ),
            None,
        )
        if not stage:
            continue
        stage_text = _compact_action_text(str(stage.get("label") or ""))
        allowed_names = {
            name for name, aliases in aliases_by_name.items()
            if any(alias in stage_text for alias in aliases)
        }
        if not allowed_names:
            continue
        arc = arc_by_num.get(scene_num) or {}
        scene_text = _compact_action_text(" ".join([
            str(scene.get("action_detail_vi") or ""),
            str(scene.get("veo3_prompt_en") or ""),
            str(scene.get("voice_over_en") or ""),
            str(arc.get("scene_lead_character") or ""),
        ]))
        mentioned_names = {
            name for name, aliases in aliases_by_name.items()
            if any(alias in scene_text for alias in aliases)
        }
        wrong_names = sorted(mentioned_names - allowed_names)
        if wrong_names:
            issues.append(ValidationIssue(
                (
                    f"Scene {scene_num}: stage-character mismatch; "
                    f"stage {stage.get('scene_start')}-{stage.get('scene_end')} allows "
                    f"{sorted(allowed_names)}, but scene mentions {wrong_names}"
                ),
                BLOCK,
                "stage_character_mismatch",
                scene_num,
            ))
    return issues


def validate_emotion_arc_state_machine(emotion_arc: list[dict], story_spine: dict) -> list[str]:
    """Reject macro-loop beats before scene generation spends batch calls."""
    if not emotion_arc:
        return []
    errors = []
    expected_total = int(story_spine.get("total_scenes") or len(emotion_arc))
    nums = [entry.get("scene_number") for entry in emotion_arc]
    expected_nums = list(range(1, expected_total + 1))
    if nums != expected_nums:
        errors.append(f"emotion_arc scene_number sequence invalid: expected 1-{expected_total}, got {nums[:12]}")

    trigger_ranges = _trigger_ranges_from_spine(story_spine)
    if story_spine:
        allowed_once = list(dict.fromkeys(
            (story_spine.get("allowed_once_triggers") or [])
            + list(trigger_ranges.keys())
        ))
    else:
        allowed_once = list(STATE_TRIGGER_PATTERNS.keys())
    hits: dict[str, list[int]] = {trigger: [] for trigger in allowed_once}
    for entry in emotion_arc:
        scene_num = entry.get("scene_number")
        if not isinstance(scene_num, int):
            continue
        for trigger in emotion_arc_state_triggers(entry):
            if trigger in hits:
                hits[trigger].append(scene_num)
    errors.extend(_trigger_repeat_errors("Emotion arc state", hits, trigger_ranges))

    for prev, curr in zip(emotion_arc, emotion_arc[1:]):
        if prev.get("scene_number") and curr.get("scene_number") != prev.get("scene_number") + 1:
            errors.append(f"Emotion arc scenes {prev.get('scene_number')}->{curr.get('scene_number')}: non-adjacent numbering")
        prev_beat = _compact_action_text(prev.get("beat_summary") or "")
        curr_beat = _compact_action_text(curr.get("beat_summary") or "")
        if prev_beat and len(prev_beat) > 24 and prev_beat == curr_beat:
            errors.append(f"Emotion arc scenes {prev.get('scene_number')}->{curr.get('scene_number')}: repeated beat_summary")
    return errors


def validate_emotion_arc_constraints(script_data: dict) -> list[str]:
    """Validate Prompt 0 hard constraints before scene generation."""
    if not script_data.get("emotion_arc"):
        return []
    return [
        err for err in validate_constraint_violations(script_data)
        if err.startswith("Emotion arc scene")
    ]


def validate_story_state_machine(script_data: dict) -> list[str]:
    """Rejects repeated intro-to-resolution cycles in one continuous screenplay."""
    scenes = sorted(
        [s for s in script_data.get("scenes") or [] if isinstance(s.get("scene_number"), int)],
        key=lambda s: s.get("scene_number", 0),
    )
    if len(scenes) < 8:
        return []

    story_spine = script_data.get("story_spine") or {}
    trigger_ranges = _trigger_ranges_from_spine(story_spine)
    if story_spine:
        allowed_once = list(dict.fromkeys(
            (story_spine.get("allowed_once_triggers") or [])
            + list(trigger_ranges.keys())
        ))
    else:
        allowed_once = list(STATE_TRIGGER_PATTERNS.keys())
    hits: dict[str, list[int]] = {trigger: [] for trigger in allowed_once}

    for scene in scenes:
        for trigger in scene_state_triggers(scene):
            if trigger in hits:
                hits[trigger].append(scene["scene_number"])

    return _trigger_repeat_errors("Story state", hits, trigger_ranges)


def validate_scene_adjacency(scenes: list[dict]) -> list[str]:
    """
    Catches measurable continuity failures between adjacent saved scenes:
    exact-ish repetition and obvious restart to an earlier setup after an exit/resolution beat.
    """
    errors: list[str] = []
    ordered = sorted(
        [s for s in scenes if isinstance(s.get("scene_number"), int)],
        key=lambda s: s.get("scene_number", 0),
    )

    prior_exit_or_resolution = [
        r"\bthoát\b",
        r"\ban toàn\b",
        r"\bđặt nạn nhân\b",
        r"\bcởi mũ\b",
        r"\btháo mũ\b",
        r"\bnhìn lại\b",
        r"\bngã ra\b",
        r"\boutside\b",
        r"\bsafe\b",
        r"\bremoves? (his )?helmet\b",
        r"\blooking back\b",
    ]
    restart_to_setup = [
        r"\bleo lên xe\b",
        r"\blên xe\b",
        r"\bchuẩn bị xuất phát\b",
        r"\bkhởi hành\b",
        r"\blao qua .*phố\b",
        r"\bđến hiện trường\b",
        r"\bbước xuống xe\b",
        r"\bđứng trước .*đám cháy\b",
        r"\bclimbs? onto .*carriage\b",
        r"\breturns? to .*station\b",
        r"\barrives? at .*fire\b",
    ]

    for prev, curr in zip(ordered, ordered[1:]):
        prev_num = prev.get("scene_number")
        curr_num = curr.get("scene_number")
        if curr_num != prev_num + 1:
            continue

        prev_action = _compact_action_text(prev.get("action_detail_vi") or "")
        curr_action = _compact_action_text(curr.get("action_detail_vi") or "")
        if not prev_action or not curr_action:
            continue

        if prev_action == curr_action:
            errors.append(f"Scenes {prev_num}->{curr_num}: repeated identical action_detail_vi")

        if _has_any(prev_action, prior_exit_or_resolution) and _has_any(curr_action, restart_to_setup):
            errors.append(
                f"Scenes {prev_num}->{curr_num}: timeline reset after an exit/resolution beat"
            )

    return errors


def _approved_identity_tokens(script_data: dict) -> set[str]:
    tokens: set[str] = set()
    p0 = script_data.get("prompt_0") or {}
    for field in ["primary_subject_en", "hard_visual_lock_en", "setting_lock_en"]:
        for token in re.findall(r"\b[A-Z][A-Za-z0-9_-]{2,}\b", p0.get(field, "")):
            tokens.add(token.lower())
    for char in script_data.get("characters") or []:
        for value in [char.get("character_name"), char.get("key_identifiers_en")]:
            if value:
                for part in re.split(r"[,;/()\- ]+", str(value)):
                    if len(part) >= 3 and not part.lower().startswith("nhân"):
                        tokens.add(part.lower())
    for char in p0.get("character_lock") or []:
        for value in [char.get("name"), char.get("description_en")]:
            if value:
                for part in re.split(r"[,;/()\- ]+", str(value)):
                    if len(part) >= 4:
                        tokens.add(part.lower())
    return tokens


# Durable validation guard: scene generation checks run against normalized contract fields,
# preventing future JSON display changes from becoming quality gates.
def validate_scene_generation_issues(script_data: dict) -> list[ValidationIssue]:
    """Scene validation with deterministic blockers separated from heuristics."""
    script_data = _legacy_script_view(script_data)
    issues: list[ValidationIssue] = []
    anchor = {"continuity_prompt_en": script_data.get("continuity_prompt_en", "")}
    identity_tokens = _approved_identity_tokens(script_data)
    generic_re = re.compile(r"\b(main character|protagonist|the creature)\b", re.IGNORECASE)
    placeholder_re = re.compile(r"\[[^\]]+\]|No Prompt 0 available|The story continues", re.IGNORECASE)

    scenes = script_data.get("scenes") or []
    constraint_model = build_constraint_model(script_data)
    has_project_constraints = bool(constraint_model.get("constraints"))
    total = (script_data.get("story_spine") or {}).get("total_scenes")
    if isinstance(total, int) and total > 0 and len(scenes) >= total:
        nums = [s.get("scene_number") for s in scenes]
        expected = list(range(1, total + 1))
        if sorted(nums) != expected:
            issues.append(ValidationIssue(
                f"scene number sequence invalid: expected 1-{total}, got {nums[:12]}",
                BLOCK,
                "invalid_scene_sequence",
            ))

    for scene in scenes:
        num = scene.get("scene_number", "?")
        scene_num = num if isinstance(num, int) else None
        for issue in validate_scene_issues(normalize_scene(scene), anchor, scene_num):
            issues.append(ValidationIssue(
                f"Scene {num}: {issue.message}",
                issue.severity,
                issue.code,
                scene_num,
            ))
        if has_project_constraints and not scene.get("scene_specific_negative_en"):
            issues.append(ValidationIssue(
                f"Scene {num}: missing scene_specific_negative_en",
                WARN,
                "missing_scene_specific_negative",
                scene_num,
            ))
        prompt = scene.get("veo3_prompt_en") or ""
        if scene.get("generation_failed"):
            issues.append(ValidationIssue(
                f"Scene {num}: generated fallback scene was merged",
                BLOCK,
                "fallback_scene_merged",
                scene_num,
            ))
        if placeholder_re.search(prompt):
            issues.append(ValidationIssue(
                f"Scene {num}: prompt contains template/fallback text",
                BLOCK,
                "template_text_in_prompt",
                scene_num,
            ))
        if generic_re.search(prompt):
            prompt_lower = prompt.lower()
            if identity_tokens and not any(token in prompt_lower for token in identity_tokens):
                issues.append(ValidationIssue(
                    f"Scene {num}: prompt uses generic subject without approved identity token",
                    WARN,
                    "generic_subject",
                    scene_num,
                ))
    for err in validate_scene_adjacency(scenes):
        issues.append(ValidationIssue(err, WARN, "scene_adjacency"))
    for err in validate_story_state_machine(script_data):
        issues.append(ValidationIssue(err, WARN, "story_state_heuristic"))
    issues.extend(validate_scene_stage_alignment(script_data))
    for err in validate_constraint_violations(script_data):
        if err.startswith("Scene "):
            issues.append(ValidationIssue(err, WARN, "constraint_heuristic"))
    return issues


def validate_scene_generation_quality(script_data: dict) -> list[str]:
    """Backward-compatible API returning all scene validation messages."""
    return issue_messages(validate_scene_generation_issues(script_data))


# Durable fact-check guard: sparse verification blocks only when the verification
# phase never completed; absent per-scene labels become transparent v3 status, not a retry loop.
def validate_historical_coverage(script_data: dict) -> list[str]:
    """Historical/scientific scripts need the fact-check phase to complete, not per-scene hard labels."""
    script_data = _legacy_script_view(script_data)
    errors = []
    if script_data.get("topic_type") not in ("historical", "scientific"):
        return errors
    if not script_data.get("_fact_check_completed"):
        return ["historical/scientific verification phase not completed"]
    for scene in script_data.get("scenes") or []:
        num = scene.get("scene_number", "?")
        if scene.get("needs_fact_check") and not scene.get("fact_check_note_vi"):
            errors.append(f"Scene {num}: needs_fact_check=true but missing fact_check_note_vi")
    return errors
