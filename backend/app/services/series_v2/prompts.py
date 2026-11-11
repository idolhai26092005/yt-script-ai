import json
from typing import Any

from app.services.series_v2.contracts import SCHEMA_VERSION


# Prompt serialization guard: LLM phases receive compact canonical JSON blocks so
# retry feedback can be appended without mutating the source artifact structure.
def _json_block(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


# Setup prompt guard: one call creates both series bible and season map to avoid
# the legacy multi-option branch and reduce setup latency.
def build_setup_prompt(series_in: Any, feedback: list[str] | None = None) -> str:
    feedback_text = "\nFix these schema issues: " + "; ".join(feedback) if feedback else ""
    return f"""
You are designing a serialized YouTube video series.
Return raw JSON only. No markdown. Schema version: {SCHEMA_VERSION}.

Input:
title: {series_in.title}
premise: {series_in.premise}
style: {series_in.style}
topic_type: {series_in.topic_type}
target_episode_count: {series_in.target_episode_count}
default_scene_count: {series_in.default_scene_count}
scene_duration_sec: {series_in.scene_duration_sec}

Output object:
{{
  "schema_version": "{SCHEMA_VERSION}",
  "reality_binding_level": "soft|strict",
  "series_bible": {{
    "world_rules": [],
    "cast_locks": [],
    "visual_anchor": "stable approved look, props, places, era",
    "style_tone": "",
    "central_conflict": "",
    "reality_constraints": [],
    "forbidden_drift": []
  }},
  "season_map": {{
    "episode_slots": [
      {{
        "episode_number": 1,
        "title": "",
        "premise": "",
        "goal": "",
        "pressure_increase": "",
        "required_reveal": "",
        "required_unresolved_thread": "",
        "intended_next_start_state": "",
        "must_include": [],
        "must_avoid": [],
        "scene_count": {series_in.default_scene_count},
        "ending_mode": "open_loop|soft_cliffhanger|hard_cliffhanger|season_finale"
      }}
    ]
  }}
}}

Rules:
- episode_slots length must equal target_episode_count.
- Non-final episodes must leave a forward-driving unresolved state.
- Final episode may use season_finale; earlier episodes must not.
- Use positive-first visual constraints. Avoid negative-only visual instructions.
- Do not create three episode options.{feedback_text}
""".strip()


# Planning prompt guard: blueprint and emotion arc are combined so each episode
# spends one planning call and every scene has a planned handoff target.
def build_episode_plan_prompt(
    *,
    series_bible: dict,
    season_slot: dict,
    brief: dict,
    prior_deltas: list[dict],
    scene_count: int,
    feedback: list[str] | None = None,
) -> str:
    feedback_text = "\nFix these schema issues: " + "; ".join(feedback) if feedback else ""
    return f"""
Return raw JSON only. No markdown. Schema version: {SCHEMA_VERSION}.

Inputs:
series_bible: {_json_block(series_bible)}
season_slot: {_json_block(season_slot)}
accepted_brief: {_json_block(brief)}
prior_continuity_deltas: {_json_block(prior_deltas)}
scene_count: {scene_count}

Output object:
{{
  "schema_version": "{SCHEMA_VERSION}",
  "episode_blueprint": {{
    "prompt_0_extension": "",
    "story_contract": "",
    "stage_ranges": [],
    "visual_constraints": [],
    "audio_constraints": [],
    "handoff_target": "",
    "next_start_promise": ""
  }},
  "emotion_arc": [
    {{
      "scene_number": 1,
      "scene_goal": "",
      "emotion_shift": "",
      "physical_state_end": "",
      "scene_lead": "",
      "anchor_to_cite": "approved visual anchor or continuity fact"
    }}
  ]
}}

Rules:
- emotion_arc length must equal scene_count and scene_number must be 1..scene_count.
- Each beat must cite what continuity anchor the later scene should reference.
- Keep audio constraints concise.
- Non-final episode planning must point the final scene at the next-start promise.{feedback_text}
""".strip()


# Scene prompt guard: every generated scene must directly cite the approved anchor
# in `veo3_prompt_en` so structural validation can catch continuity drift.
def build_scene_batch_prompt(
    *,
    series_bible: dict,
    episode_blueprint: dict,
    emotion_arc: list[dict],
    brief: dict,
    previous_handoff: str,
    batch_start: int,
    batch_end: int,
    feedback: list[str] | None = None,
) -> str:
    feedback_text = "\nFix these schema issues: " + "; ".join(feedback) if feedback else ""
    return f"""
Return raw JSON only. No markdown. Schema version: {SCHEMA_VERSION}.

Inputs:
series_bible: {_json_block(series_bible)}
episode_blueprint: {_json_block(episode_blueprint)}
accepted_brief: {_json_block(brief)}
batch_emotion_arc: {_json_block(emotion_arc)}
previous_saved_scene_handoff: {previous_handoff}
batch_range: {batch_start}-{batch_end}

Output object:
{{
  "schema_version": "{SCHEMA_VERSION}",
  "scenes": [
    {{
      "scene_number": {batch_start},
      "action_detail_vi": "",
      "veo3_prompt_en": "Reference the approved visual anchor: ...",
      "voice_over_en": "",
      "continuity_anchor": "",
      "handoff_state": ""
    }}
  ]
}}

Rules:
- Generate exactly scenes {batch_start} through {batch_end}, no gaps or duplicates.
- Start every veo3_prompt_en with: Reference the approved
- Use positive-first visual wording before any negative constraints.
- Voice text must be concise and present.
- Last scene in a non-final episode must preserve the next episode handoff.{feedback_text}
""".strip()


# Review prompt guard: reviewer returns soft continuity judgment only; hard
# blocking stays limited to parse/schema/runtime validators.
def build_continuity_review_prompt(
    *,
    series_bible: dict,
    season_slot: dict,
    brief: dict,
    scenes: list[dict],
    is_final_episode: bool,
    feedback: list[str] | None = None,
) -> str:
    feedback_text = "\nFix these review issues: " + "; ".join(feedback) if feedback else ""
    return f"""
Return raw JSON only. No markdown. Schema version: {SCHEMA_VERSION}.

Inputs:
series_bible: {_json_block(series_bible)}
season_slot: {_json_block(season_slot)}
accepted_brief: {_json_block(brief)}
is_final_episode: {str(is_final_episode).lower()}
scenes: {_json_block(scenes)}

Output object:
{{
  "schema_version": "{SCHEMA_VERSION}",
  "handoff_strength": "strong|medium|weak",
  "open_threads": [],
  "next_start_state": "",
  "review_notes": [],
  "too_closed": false,
  "season_alignment": "strong|medium|weak"
}}

Rules:
- Do not rewrite scenes.
- For non-final episodes, report weak if the ending fully resolves the episode.
- No regex-style wording judgment; judge continuity pressure and next-start clarity.{feedback_text}
""".strip()


# Fact prompt guard: strict-topic verification is optional and patch based so
# factual fixes cannot silently rewrite already-valid scenes.
def build_fact_verification_prompt(
    *,
    series_bible: dict,
    scenes: list[dict],
    feedback: list[str] | None = None,
) -> str:
    feedback_text = "\nFix these verification issues: " + "; ".join(feedback) if feedback else ""
    return f"""
Return raw JSON only. No markdown. Schema version: {SCHEMA_VERSION}.

Inputs:
series_bible: {_json_block(series_bible)}
scenes: {_json_block(scenes)}

Output object:
{{
  "schema_version": "{SCHEMA_VERSION}",
  "patches": [
    {{
      "scene_number": 1,
      "fields": {{}},
      "reason": ""
    }}
  ],
  "warnings": []
}}

Rules:
- Only patch factual errors for historical or scientific topics.
- Do not patch style or creative preference issues.
- Preserve scene_number and required render fields.{feedback_text}
""".strip()


# Packaging prompt guard: packaging can be deferred by callers, but when enabled
# it emits a compact metadata artifact instead of rewriting episode content.
def build_packaging_prompt(*, script_output: dict, feedback: list[str] | None = None) -> str:
    feedback_text = "\nFix these packaging issues: " + "; ".join(feedback) if feedback else ""
    return f"""
Return raw JSON only. No markdown. Schema version: {SCHEMA_VERSION}.

Input script_output: {_json_block(script_output)}

Output object:
{{
  "schema_version": "{SCHEMA_VERSION}",
  "video_title": "",
  "description": "",
  "tags": [],
  "thumbnail_prompt_en": ""
}}

Rules:
- Do not rewrite scenes.
- Keep metadata concise and aligned with the episode handoff.{feedback_text}
""".strip()
