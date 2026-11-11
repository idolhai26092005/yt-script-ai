# Prompt ownership guard: this file is the byte-preserving home of the legacy
# prompt constants while role-owned modules expose narrower import surfaces.
from app.core.safety import VEO3_CONTENT_SAFETY_RULES

# ─── SUGGESTION & TOPIC PROMPTS ──────────────────────────────────────────────

SYSTEM_PROMPT_GENERATE_SUGGESTIONS = """
You are an expert YouTube content strategist and creative script director.
Your task is to analyze the user's input concept/story/transcript and generate exactly {num_suggestions} distinct script suggestions.

Inputs:
- Input Concept: {input_content}
- Style: {style}
- Number of Scenes: {num_scenes}

Rules:
1. Generate exactly {num_suggestions} suggestions.
2. The suggestion at index 0 MUST be the "original" adaptation—meaning it stays as close to the user's input concept as possible. Mark it with "is_original": true.
3. Suggestions at indexes 1 to {last_suggestion_idx} must explore highly creative, alternative narrative angles, unexpected twists, or creative spin-offs of the original concept. Mark them with "is_original": false.
4. Keep the suggestions diverse in tone/mood (e.g., epic, mysterious, dramatic, emotional, educational).
5. For each suggestion, classify the topic type as one of: "historical" (real historical events or figures), "scientific" (science, technology, nature, educational facts), "fictional_mythology" (mythology, legends, folklore), or "fictional_original" (pure fictional stories).
6. For each suggestion, determine the best narrative shape (emotion arc structure), chosen from: "adventure" (threat/rising tension/climax/resolution), "reflective" (context/ascent/sacrifice/legacy), "explanatory" (curiosity/investigation/discovery/application), "tragedy" (ambition/success/warning/downfall/somber lesson), or "suspense" (mystery/clues/twist/unveiling/relief).
7. For each suggestion, determine if it focuses on a specific, named historical person/figure. Set "has_named_historical_figure" to true if so, and false otherwise (e.g. if it focuses on social evolution, scientific discovery, generic groups, concepts, etc.).
8. Output format must be a raw JSON array conforming EXACTLY to the following structure:
[
  {{
    "index": 0,
    "title": "Title of the first suggestion (Vietnamese)",
    "synopsis": "A brief 2-3 sentence synopsis of this script direction (Vietnamese)",
    "mood": "Tone/Mood of this suggestion (e.g. dramatic, educational, cinematic, mysterious) (Vietnamese)",
    "hook": "An attention-grabbing hook sentence to open the video (Vietnamese)",
    "is_original": true,
    "topic_type": "historical" | "scientific" | "fictional_mythology" | "fictional_original",
    "narrative_shape": "adventure" | "reflective" | "explanatory" | "tragedy" | "suspense",
    "has_named_historical_figure": true | false
  }},
  ...
]
9. Return ONLY the raw valid JSON. Do not wrap in markdown code blocks like ```json ... ```. No extra text or explanations.
10. Ensure all generated suggestions strictly comply with the following content safety policy:
""" + VEO3_CONTENT_SAFETY_RULES + """
"""

SYSTEM_PROMPT_TOPIC_SUGGESTIONS = """
You are an expert content creator.
Draft a compelling and detailed video core idea/storyline (around 100-200 words) based on the following trending topic.

Topic Name: {topic_name}
Topic Description: {topic_description}
Style: {style}

Guidelines:
- Write a cinematic or educational narrative outline.
- Focus on what makes this topic interesting for a short video script.
- Keep the language in Vietnamese.
- Output ONLY the raw storyline text. Do not include titles, intros, or markdown formatting.
- VIETNAMESE HISTORY BAN: DO NOT generate any content related to Vietnamese history (lịch sử Việt Nam). If the topic is related to Vietnamese history, refuse to generate it or redirect it entirely to a non-Vietnamese historical or fictional topic.
"""

# ─── HISTORICAL / SCIENTIFIC RULES ───────────────────────────────────────────

# Durable prompt guard: historical/scientific generation may provide a lightweight
# source basis, while final verification details live in the Phase 4 verification object.
HISTORICAL_SCIENTIFIC_HARD_RULES = """
=== CRITICAL RULES FOR HISTORICAL/SCIENTIFIC CONTENT ===
1. STRICTLY FORBIDDEN: Do not attribute supernatural powers, magic, or unhistorical/unscientific events to real historical/scientific figures or occurrences.
2. HISTORICAL BASIS: All actions, tactics, and dialogue MUST be based on historically/scientifically documented records. Do not invent groundless plot points or fantasy elements.
3. VISUAL CREATIVITY VS. FACTUAL TRUTH: You can use visual styling and camera movements creatively to represent the scene, but do not change the core factual truth or sequence of events.
4. UNCERTAINTY: If a specific detail is historically/scientifically uncertain, describe it in general terms rather than inventing specific fictional details.
5. In each generated scene, fill "basis_vi" with a short Vietnamese description of the historical or scientific basis when the basis is clear; otherwise use null and let Phase 4 verification annotate risk.
6. NARRATIVE FRAMING: Do not attribute actions or major historical initiatives (e.g. building a tomb or pyramid) to a historical figure who did not actually perform, order, or participate in those specific actions.
7. PERIOD ACCURACY: Architectural structures, clothing, tools, and background elements must strictly match the correct historical era of the events. Do not mix elements from different historical periods (e.g., do not depict pyramids in a New Kingdom story, as pyramids belong to the Old Kingdom).
8. MULTI-FIGURE TIMELINE: When the script features multiple real historical figures from different eras, each figure's scenes MUST be contained within their own historical period. Scenes showing them co-existing in the same physical space are FORBIDDEN unless a clear "centuries later" or time-travel narrative device is established.
9. CHARACTER ROLE ACCURACY: Real historical figures must not be depicted performing manual labor or tasks beneath their documented social station (e.g., a Pharaoh personally carving statues, a king plowing fields) unless there is documented evidence they did so.
10. CONCEPTUAL ANACHRONISM: Do not attribute modern psychological, philosophical, or sociological frameworks (e.g., alienation from nature, existential crisis, modern economic theory like supply/demand curves or inflation concepts) to characters from pre-modern eras, unless explicitly framed as an outside narrator's modern interpretation/commentary.
======================================================
"""

# Durable prompt guard: fact-check now returns sparse verification patches, not a full
# rewritten scene list, to avoid long retries caused by missing labels on unchanged scenes.
HISTORICAL_FACT_CHECK_PROMPT = """
You are an expert fact-checker specializing in world history, Vietnamese history, and general science.
Your job is to audit the provided video script for any unhistorical, unscientific, or fictitious details that violate the facts.

Target Script:
{script_json}

Instructions:
1. Examine each scene in the "scenes" list carefully.
2. Check for:
   - Supernatural powers, magic, or fantasy elements attributed to real historical people.
   - Invented events, actions, or details that have no historical or scientific basis.
   - Pseudoscience or incorrect scientific explanations.
3. If you find any violations:
   - Return a patch for that scene only.
   - If correcting content, include "action_vi" and/or "veo_prompt_en" with the corrected values.
   - Fill "notes_vi" with a detailed explanation of what was corrected or why it needs verification.
4. Narrative Framing & Timeline check: Verify that characters are not falsely depicted performing acts they never did. Confirm architectural and technological elements match the exact historical era.
5. COLOR/LIGHTING PRESERVATION: When rewriting veo3_prompt_en to correct historical/scientific inaccuracies, you MUST preserve the color palette and lighting description. Do NOT modify character identity tags (e.g. 'Name (key_identifiers_en)') already present in veo3_prompt_en.
6. When a scene is changed or has risk, provide "basis_vi" for that patch, detailing the real historical event/scientific fact that supports the scene.
7. VERIFIABILITY LEVEL: For each returned patch, determine the "level" as one of:
   - "specific_event": based on a specific, documented historical event or verified scientific experiment/fact.
   - "general_consensus": based on general historical consensus or accepted scientific theories/models.
   - "unverifiable_generalization": plausible but lacks concrete historical records or scientific evidence.
   If the topic is "historical" and you classify a scene as "unverifiable_generalization", you MUST either rewrite the scene's action/basis to match general consensus, or explicitly note that it is dramatic license/speculation.
8. TIMELINE CROSS-CHECK: If the script features multiple real historical figures, verify that they existed in the same era. Flag any scene that places figures from different centuries/dynasties together in the same physical space without an explicit time-jump transition.
9. CHARACTER ROLE ACCURACY: Verify that historical figures are not depicted performing manual labor or tasks beneath their documented social status unless historically documented.
10. CONCEPTUAL ANACHRONISM: Verify that characters from pre-modern eras are not attributed modern frameworks. Correct any scene violating this rule.
11. SPARSE PATCH RULE: Do NOT return unchanged accurate scenes. Return only scenes with a correction, risk, or meaningful verification note. If the whole chunk is accurate, return "verification_patches": [] and has_issues=false.

You MUST structure your response as a single, raw, valid JSON object conforming exactly to this structure:
{{
  "has_issues": true/false,
  "fact_check_notes": "General summary of the audit (Vietnamese)",
  "verification_patches": [
    {{
      "scene_number": 1,
      "status": "checked" | "needs_review" | "corrected",
      "level": "specific_event" | "general_consensus" | "unverifiable_generalization" | null,
      "basis_vi": "Brief historical/scientific basis when useful (Vietnamese)",
      "risk_flags": ["anachronism"],
      "notes_vi": ["Explanation of change or warning"],
      "action_vi": "Corrected Vietnamese action only if content changed",
      "veo_prompt_en": "Corrected English video prompt only if content changed"
    }},
    ...
  ]
}}
"""

# ─── NARRATIVE SHAPE STRUCTURES ───────────────────────────────────────────────

BASE_NEGATIVE_PROMPT = "low quality, blurry, distorted face, extra fingers, messy composition, flickering artifacts, watermark, text overlay"

SHAPE_STRUCTURES = {
    "adventure": """Since this is an ADVENTURE/CONFLICT story, follow this structure:
- Introduction of threat or goal
- Rising tension
- Climax (intense dramatic/action beat)
- Resolution""",
    "reflective": """Since this is a HISTORICAL/BIOGRAPHICAL story, DO NOT manufacture fake physical threats or fantasy enemies.
Follow this REFLECTIVE/BIOGRAPHY structure focusing on legacy and sacrifice:
- Introduction of historical context or character's vision
- Ascent to greatness / peak achievements
- Sacrifices made / the cost of greatness / turning point
- Legacy left behind / philosophical reflection""",
    "explanatory": """Since this is an EDUCATIONAL/SCIENTIFIC exploration, DO NOT manufacture dramatic action enemies.
Follow this EXPLANATORY/DISCOVERY structure:
- Curiosity hook / posing a mystery or question
- Initial observation / step-by-step investigation
- Discovery of the unexpected / core scientific insight
- Modern application / philosophical synthesis""",
    "tragedy": """Since this is a TRAGEDY, follow this structure focusing on ambition, rise, downfall, and loss:
- Introduction of the character's core desire, ambition, or setup
- Initial success and ascent
- Overconfidence, errors, or warning signs
- The turning point / catastrophe / tragic climax
- The aftermath / sorrowful reflection / legacy of loss""",
    "suspense": """Since this is a SUSPENSE/MYSTERY story, focus on investigation, escalating stakes, and tension:
- The initial discovery of a mystery or unexplained event
- Collecting clues, initial theories, or false leads
- Rising tension as stakes escalate / danger or time limit approaches
- The key twist or unveiling of the truth (climax)
- The resolution / relief / or lingering awe"""
}

# ─── EMOTION ARC ──────────────────────────────────────────────────────────────

EMOTION_ARC_BASE_PROMPT = """
You are an expert film director and script analyst.
Given the script idea/synopsis:
{synopsis}
Style: {style}
Number of scenes: {num_scenes}
Characters list: {characters}
Scene numbering rule: {scene_number_rule}

Durable topic-contract guard: keep the central subject, opponent/force, and goal below
as the spine of every beat; side threats may escalate pressure but must not replace it.
Story contract:
{story_contract_context}

Your task is to outline the emotional progression (emotion arc) and key dramatic beats for all {num_scenes} scenes BEFORE the details are generated.
{shape_structure}

Rules:
1. Generate exactly {num_scenes} entries, one for each requested scene number. Follow the Scene numbering rule exactly.
2. For each scene, specify:
   - "emotion_label": A single Vietnamese word or short phrase for the primary emotion of the scene (e.g. tò mò, sửng sốt, hoảng hốt, quyết tâm, bình yên).
   - "beat_summary": A 1-sentence Vietnamese summary of what happens physically/narratively.
   - "physical_state_end": A brief description in Vietnamese of the character's physical state/position/location at the very end of the scene (e.g., "Đang bám vào cột đá, mắt nhìn xuống hố", "Đứng thẳng, hai tay dang rộng hướng về phía ánh sáng").
   - "camera_complexity": Choose one of "low" (simple/no movement), "medium" (slow pan/zoom), "high" (fast orbital/dolly zoom/handheld shaking).
   - "scene_lead_character": The name of the character leading the action in this scene (MUST choose exactly from: {characters_list}, or "None" if no specific character leads)
3. Critical Adjacency Constraint: The starting physical state of scene N+1 MUST be a direct, logical continuation of "physical_state_end" of scene N. There must be no teleportation or sudden changes in posture.
4. Timeline Monotonicity: the story timeline moves forward only. Once a setup, location state, objective, conflict step, or resolution beat is completed, later scenes MUST NOT reset to an earlier state unless the synopsis explicitly says there is a second cycle.
5. Consequence Chain: every beat_summary must name the new consequence created by the previous scene. Do not repeat the same purpose with different wording.
6. INTENSITY VARIATION: Emotion arc PHẢI có phân hóa rõ rệt. CẤM tạo một emotion arc tuyến tính đều hoặc thiếu kịch tính:
   - Ít nhất phải có 1 scene mang nhãn cảm xúc cao trào, mãnh liệt (ví dụ: đau đớn, phẫn nộ, sửng sốt, tuyệt vọng, bi tráng, hoảng hốt).
   - Ít nhất phải có 1 scene mang nhãn cảm xúc trầm lắng/tiêu cực/lo âu trước khi kết thúc bằng cảm xúc bình yên hoặc chiêm nghiệm.
   - Nhãn cảm xúc giữa các cảnh không được lặp lại liên tiếp quá 2 lần.

Output format must be a raw JSON object conforming EXACTLY to the following structure:
{{
  "emotion_arc": [
    {{
      "scene_number": 1,
      "emotion_label": "...",
      "beat_summary": "...",
      "physical_state_end": "...",
      "camera_complexity": "low" | "medium" | "high",
      "scene_lead_character": "..."
    }},
    ...
  ]
}}
Return ONLY the raw valid JSON. Do not wrap in markdown code blocks like ```json ... ```. No extra text or explanations.
"""

# ─── PHASE 0: PROMPT 0 + PRODUCTION BLUEPRINT ────────────────────────────────

# Durable topic-contract guard: Phase 0 must explicitly lock what the video is
# fundamentally about so later roles cannot promote a side threat into the main story.
PROMPT_0_GENERATION_TEMPLATE = """
You are an expert cinematic screenplay director creating a complete production bible for a {style} video.

Script Concept:
- Title: {title}
- Synopsis: {synopsis}
- Style: {style}
- Total Scenes: {num_scenes} (each {scene_duration_sec} seconds)
- Topic Type: {topic_type}
- Narrative Structure: {shape_structure}
{context_str}
{historical_rules}

Your task: Generate a COMPLETE production bible in a SINGLE JSON response.

=== PART 1: PROMPT 0 (Identity Lock — English) ===
A locked reference document that EVERY scene will cite with "Reference the approved Prompt 0 continuity board,".
Requirements:
- Extremely specific — no vague terms like "unique appearance" or "distinctive look"
- Production-ready — directly usable in Veo 3 without modification
- Complete — covers everything needed to maintain visual consistency across all {num_scenes} scenes
- Continuous — the plan must cover ONE forward-moving story. Do not resolve the mission before the final stage, then restart it.
- Single journey — if the story has 80 scenes, it is ONE 80-scene journey, not four 20-scene short films pasted together.
- Once-only hard triggers — only explicit alarm/reset and final resolution/ending beats are hard-gated. Movement, entry, rescue, confrontation, and discovery are normal progression details, not keyword gates.
- Separate stable identity from evolving state:
  * Fixed identity = baseline anatomy/form/clothing/materials/recognition features that exist before Scene 1 begins.
  * Evolving state = injuries, damage, dirt, fatigue, fear, alliances, wounds, wetness, burns, smoke/ash marks, broken tools, changed posture, or relationship changes that happen only after a visible cause in the timeline.
  * First cause = the earliest scene/beat that creates each evolving state.
- Character Lock and Primary Subject must describe the baseline identity only. Do NOT include timeline consequences in the initial identity lock.
- Put evolving consequences in the internal continuity_evolution object, not inside baseline identity.
- TAG-BLOCK STYLE: Write Prompt 0 content like a production bible, similar in spirit to:
  Primary Subject / Primary Creature, Hard Visual / Form Lock, Setting / Habitat / World Lock,
  Character Lock, Camera Lock, Voice / Sound Lock, Action / Story Logic, Scene Function Rules,
  Continuity Lock, Internal Logic, Negative Constraints.
- Each field value must be concise but dense: short lines or compact clauses, concrete nouns,
  exact allowed/forbidden objects, stable visual identifiers, and clear continuity rules.
- Do NOT put generic placeholders such as "main character", "protagonist", "unique appearance",
  or "dramatic backdrop" when a named/defined subject can be used.
- Define a central story contract before writing stages:
  * main subject = what the video is fundamentally about, from the title/synopsis.
  * protagonist = who takes action or changes.
  * central opponent/force = the primary conflict force that must remain visible until climax.
  * side threats = allowed pressure only; they must NEVER replace the central opponent/force.
- If the synopsis names a creature/object/event as the hook, it must appear in the contract
  and remain important across the stage plan.

=== PART 2: PRODUCTION PLAN (Vietnamese) ===
Story planning document in Vietnamese.
Use the same readable section style as a production plan: Mạch câu chuyện, Phân chia giai đoạn,
Tiến trình cảnh, Chiến lược Camera, Continuity Locks, Hard Visual / Form Locks, Age-Stage Locks,
Main Location / Habitat Geometry, Risk Logic, Voice / Sound Strategy.
The plan must resemble the provided production sample: stages cover all scenes exactly once,
each stage has a distinct purpose, and every scene group creates a cause-effect chain.

Return this EXACT JSON structure (raw JSON, no markdown):
{{
  "prompt_0": {{
    "primary_subject_en": "Complete description of main character(s) and/or primary creature/entity. Include: count, role, age range, relationship to each other. Be specific about what makes them identifiable in every frame.",
    "hard_visual_lock_en": "Visual style definition: (1) The aesthetic that IS used (e.g. cinematic prehistoric fantasy), (2) Exact objects/technology that are NEVER allowed, (3) What makes this visual world unique and consistent.",
    "setting_lock_en": "World environment: (1) era/time period, (2) atmosphere and weather rules across all scenes, (3) List ALL named locations in this world with brief geography — these are the only locations that will appear.",
    "character_lock": [
      {{
        "name": "Character Name",
        "description_en": "Complete appearance lock: physical build, hair color/style/length, exact clothing materials and colors, signature carried items, distinctive physical features, personality traits that affect movement and reactions."
      }}
    ],
    "camera_lock_en": "Locked camera vocabulary: list specific shot types for different scene purposes (establishing=wide aerial, danger=handheld, emotion=close-up, scale=low-angle), movement rules, and what NOT to mix.",
    "voice_sound_lock_en": "Narration: language (English), tone (dramatic/cinematic), max words per line (10). Sound design palette specific to this world: list 6-8 signature environmental audio elements.",
  "action_story_logic_en": "The story follows this exact escalation sequence (list 8-12 numbered steps, each a specific narrative beat, each beat creates the consequence for the next beat, no beat resets to an earlier trigger):",
    "scene_function_rules_en": "Each {scene_duration_sec}-second scene has EXACTLY ONE dominant purpose from: World building / Character development / Discovery / Conflict / Strategy / Chase / Trap / Survival / Emotional beat / Resolution. Never combine two major events in one scene.",
    "continuity_lock_en": "Physical continuity rules: for each element that persists across scenes, state exactly: what it is, how it evolves (snow accumulates, injuries persist), what must NEVER change (mammoth design, character clothing, weapon types).",
    "internal_logic_en": "Physics and causality rules: state what IS possible and what is IMPOSSIBLE in this world. Every action must have visible consequence.",
    "negative_constraints_en": "Precise list, one per line: No [specific thing]. No [specific thing]. (Be specific: 'No metal tools, electricity, glass windows, or synthetic materials' is better than 'no modern technology'.)"
  }},
  "story_contract": {{
    "main_subject_en": "The concrete subject/hook this video is fundamentally about, copied from the title/synopsis when possible.",
    "main_subject_vi": "Chủ thể/hook trung tâm bằng tiếng Việt.",
    "protagonist_en": "The character, group, or entity whose decisions drive the story.",
    "protagonist_vi": "Nhân vật/nhóm/thực thể dẫn dắt câu chuyện.",
    "central_opponent_or_force_en": "The main opposing creature, force, problem, mystery, or pressure that must remain central until the climax.",
    "central_opponent_or_force_vi": "Đối lực/vấn đề/sinh vật trung tâm bằng tiếng Việt.",
    "core_goal_en": "The one main objective/question that every stage must serve.",
    "core_goal_vi": "Mục tiêu/câu hỏi trung tâm bằng tiếng Việt.",
    "must_remain_visible_terms": ["3-6 short terms/aliases that must stay visible across storyline, stages, emotion arc, and scenes."],
    "allowed_side_threats": ["Optional side threats/obstacles that may appear but cannot become the main conflict."],
    "forbidden_takeover_rule": "One sentence explaining what must NOT replace the central subject/opponent/goal."
  }},
  "continuity_evolution": {{
    "<subject_or_state_name>": {{
      "fixed_identity_en": "Baseline identity that exists before Scene 1 starts.",
      "initial_state_en": "What is true at Scene 1 before any story-caused change.",
      "first_cause_scene": 1,
      "first_cause_en": "Earliest visible cause that creates the changed state.",
      "evolves_after_en": "How the state may change after the first cause.",
      "must_not_appear_before_cause_en": "Consequences that must not appear before the first cause."
    }}
  }},
  "overview_analysis_vi": "Phân tích tổng quan nhịp điệu, tông màu, góc máy, cảm xúc phù hợp với style '{style}'.",
  "storyline_vi": "Mạch câu chuyện — tóm tắt liền mạch từ đầu đến cuối (3-4 câu).",
  "stages_vi": "Phân chia giai đoạn chính xác {num_scenes} cảnh thành MỘT hành trình duy nhất, không restart mini-story. Format mỗi giai đoạn: Giai đoạn X – [Tên] (Cảnh Y–Z): [mục tiêu giai đoạn + hệ quả tạo ra cho giai đoạn sau]. Sau mỗi giai đoạn, liệt kê bullet ngắn cho từng cảnh. Phân chia HẾT từ Cảnh 1 đến Cảnh {num_scenes}.",
  "progression_vi": "Tiến trình cảnh theo nhóm — giải thích mục tiêu nghệ thuật và kịch tính của từng nhóm scene.",
  "camera_strategy_vi": "Chiến lược Camera xuyên suốt video — các quy tắc hướng dẫn camera để giữ sự đồng nhất.",
  "continuity_locks_vi": "Continuity Locks — quy tắc neo giữ tính liên tục trực quan xuyên suốt.",
  "form_locks_vi": "Hard Visual / Form Locks — ràng buộc cứng về hình dáng trực quan để chống morphing.",
  "age_stage_locks_vi": "Age-Stage Locks — khóa độ tuổi và giai đoạn phát triển sinh học của nhân vật.",
  "geometry_locks_vi": "Main Location / Habitat Geometry — địa điểm và bố cục hình học cố định.",
  "risk_logic_vi": "Risk Logic — logic leo thang nguy hiểm/xung đột: mọi thất bại có nguyên nhân rõ ràng.",
  "voice_sound_strategy_vi": "Voice / Sound Strategy — chiến lược âm thanh và giọng đọc.",
  "characters": [
    {{
      "character_name": "Tên nhân vật",
      "description_en": "Full English appearance lock description (must match character_lock entry above)",
      "description_vi": "Mô tả ngoại hình bằng tiếng Việt",
      "key_identifiers_en": "2-3 most visually distinctive features in English (e.g. 'long dark braided hair, mammoth-hide cloak, bone-tipped stone spear')",
      "key_identifiers_vi": "2-3 từ khóa nhận diện bằng tiếng Việt"
    }}
  ],
  "environment_master_prompt_en": "Master environment: setting, dominant lighting conditions, color palette, atmosphere, scale.",
  "environment_master_prompt_vi": "Mô tả bối cảnh nền bằng tiếng Việt."
}}

{safety_rules}

Return ONLY the raw JSON above. No markdown code blocks. No explanation before or after.
"""

# ─── PHASE 2: BATCH SCENE GENERATION ─────────────────────────────────────────

# Durable prompt guard: Phase 2 now returns only production source fields; backend
# computes title/display/verification defaults so prompts do not hard-code UI/schema noise.
BATCH_SCENE_GENERATION_TEMPLATE = """
You are a cinematic scene writer for a {style} video production.

=== APPROVED PROMPT 0 (IDENTITY LOCK — CITE IN EVERY SCENE) ===
{prompt_0_full_text}
=== END PROMPT 0 ===

=== STORY CONTEXT ===
Title: {title}
Style: {style}
Total Scenes: {num_scenes}
This batch: Scenes {batch_start} to {batch_end} ({batch_size} scenes, {scene_duration_sec}s each)

Stage context for this batch:
{stage_context}

Durable topic-contract guard: this batch must serve the central story contract below.
Side threats may create pressure, but the central subject/opponent/goal must stay dominant.
{story_contract_context}

{story_spine_context}

{future_targets_context}

=== EMOTION ARC (scenes {batch_start}–{batch_end}) ===
{emotion_arc_json}

=== PHYSICAL CONTINUITY HANDOFF ===
{prev_context}

{used_actions_context}
=== PROJECT-SPECIFIC HARD CONSTRAINTS ===
{constraint_context}

=== BATCH POSITION ===
{batch_position_instruction}

=== SCENE GENERATION RULES ===

**veo_prompt_en — MANDATORY FORMAT:**
1. MUST start with EXACTLY: "Reference the approved Prompt 0 continuity board,"
2. Structure like the production sample, but WITHOUT adding "scene N:" inside this field:
   Reference anchor, camera movement + angle, approved subject name/identity + specific action,
   setting detail, continuity constraints ("preserve/maintain X"), short negative constraint ("no Y"),
   voice: "[dramatic English narration, ≤10 words]"
3. MUST end with: voice: "[dramatic English narration, ≤10 words, cinematic rhythm]"
4. Max 80 words TOTAL (including the voice line)
5. Do NOT use a separate negative prompt block — put visual constraints INLINE within the description
6. Camera must match camera_complexity from emotion arc (high complexity = simple character action; low complexity = can have more action)
7. Use approved names and identifiers from Prompt 0. Do NOT write "main character", "protagonist",
   "the creature", or other generic labels when Prompt 0 provides a specific subject.
8. No bracket-template leakage: never output literal "[camera]", "[action]", "[setting constraints]", or similar placeholders.

**action_vi:**
- 1-2 sentences in Vietnamese for a human editor
- Describe WHAT happens narratively, not camera details

**voice_vi:**
- Translate voice_en into Vietnamese, natural and concise
- Maximum 15 Vietnamese words, match the cinematic rhythm
- MUST NOT be null — always provide a translation

**scene_negative_en:**
- MUST NOT be empty
- Use short project-specific negative constraints from PROJECT-SPECIFIC HARD CONSTRAINTS
- Do not use generic quality boilerplate here
- Keep it under 4 comma-separated clauses

**Quality constraints:**
- PHYSICAL CONTINUITY HANDOFF is higher priority than the emotion arc. If they conflict, continue from the saved handoff state.
- STORY SPINE STATE is higher priority than local batch drama. This batch is one segment of one continuous journey, not a standalone short film.
- STORY CONTRACT is higher priority than a more exciting side threat. Do not let a side threat replace the central subject, opponent/force, or core goal.
- Each scene: ONE dominant purpose, ONE main action — never combine two major events
- Scene N+1 must physically continue from where scene N ended — NO teleportation or sudden location jumps
- Each scene introduces NEW information or narrative progression — no repetition of previous action intent
- Escalation must be SPECIFIC (name the exact new risk, discovery, or consequence)
- Timeline must move forward only. Do not restart an earlier setup, journey step, conflict cycle, or completed objective unless the synopsis explicitly defines a second cycle.
- Never reuse a completed hard trigger from STORY SPINE STATE (alarm, resolution). Movement, entry, rescue, confrontation, and discovery may recur as normal progression details if they do not reset the timeline.
- Non-final batches must end with an unresolved forward-driving consequence, not a soft ending.
- Voice narration carries MEANING, not just visual description ("The ancient titan revealed itself." not "The mammoth walks.")
- Do NOT repeat action verbs or scene intentions already used in this batch or in USED ACTIONS above

{historical_rules}
{safety_rules}

Generate exactly {batch_size} scenes in this exact JSON format:
{{
  "scenes": [
    {{
      "scene_number": {batch_start},
      "action_vi": "Vietnamese description for editor (1-2 sentences)...",
      "veo_prompt_en": "Reference the approved Prompt 0 continuity board, low-angle tracking shot, Kael grips the jagged obsidian spear while crossing the frozen canyon, preserve mammoth-hide cloak and left-broken tusk continuity, no modern objects, voice: \\"The ice remembers every failed hunt.\\"",
      "voice_en": "The cinematic narration text (same text as embedded after voice:)",
      "voice_vi": "Bản dịch tiếng Việt của narration, ≤15 từ",
      "scene_negative_en": "No modern objects, no metal tools, no fire",
      "basis_vi": null
    }},
    ... (continue for all scenes {batch_start} through {batch_end})
  ]
}}

CRITICAL: Generate EXACTLY {batch_size} scenes numbered {batch_start} through {batch_end}.
Return ONLY the raw valid JSON. No markdown code blocks. No text before or after.
"""

# ─── PHASE 2.5: SOFT SEMANTIC VERIFIER ───────────────────────────────────────

SEMANTIC_VERIFIER_PROMPT = """
You are a screenplay continuity verifier. Audit the final generated scenes after scene writing and before packaging.

Verifier mode: {verifier_mode}
Reality binding level: {reality_binding_level}

Inputs:
- Central story contract:
{story_contract}
- Prompt 0 / identity lock:
{prompt_0}
- Internal continuity evolution:
{continuity_evolution}
- Storyline:
{storyline}
- Stages:
{stages}
- Emotion arc:
{emotion_arc}
- Final scenes:
{scenes}

Checklist:
1. Physical and period/world plausibility: actions must fit the declared world, era, tools, bodies, materials, and internal physics.
2. Continuity-before-cause: no evolving state appears before its first visible cause.
3. Setup/payoff: no major payoff appears without prior setup.
4. Resolution timing: no early/later repeated ending unless the story explicitly has another cycle.
5. Scene/arc alignment: scene action should match the corresponding emotional beat and physical state.
6. Thumbnail/reference mismatch candidates: warn if the most clickable visual idea would contradict the final scenes.
7. Central contract drift: side threats must not replace the declared central subject, opponent/force, or core goal.

Rules:
- This verifier is advisory. Do not invent domain-specific bans. Use only the provided Prompt 0, internal logic, stages, emotion arc, and scenes.
- In strict mode, be more careful about historical/scientific plausibility, but still return warnings and small scene corrections only.
- Return ONLY scenes that need correction. Do not rewrite correct scenes.
- Preserve scene_number and title when possible.
- Any corrected veo3_prompt_en MUST start with "Reference the approved Prompt 0 continuity board," and keep the embedded voice format.
- Keep corrections minimal: fix causality/continuity/arc mismatch, not style preferences.

Return ONLY raw valid JSON:
{{
  "quality_warnings": [
    {{
      "scene_number": 1,
      "message_vi": "Cảnh có vấn đề gì, viết ngắn gọn.",
      "suggested_fix_vi": "Sửa thế nào, viết ngắn gọn."
    }}
  ],
  "scenes": [
    {{
      "scene_number": 1,
      "title": "Scene 1 [00:00 - 00:08]",
      "action_detail_vi": "...",
      "veo3_prompt_en": "Reference the approved Prompt 0 continuity board, ... voice: \\"...\\"",
      "voice_over_en": "...",
      "voice_over_vi": "...",
      "scene_specific_negative_en": "...",
      "needs_fact_check": false,
      "fact_check_note_vi": null,
      "historical_basis_vi": null
    }}
  ]
}}
"""

# ─── PHASE 3: PACKAGING (REFERENCE IMAGES ONLY) ──────────────────────────────

REFERENCE_IMAGES_PROMPT = """
Based on this screenplay, generate reference image prompts for production use.

Environment: {environment_prompt}
Style: {style}
Aspect Ratio: {aspect_ratio}
Story overview: {story_overview}
Quality warnings to respect: {quality_warnings}
Final scene summary: {final_scene_summary}

Rules:
- Thumbnail and background must reflect the actual final script. Do not invent a charging attack, rescue, explosion, enemy, monster, weapon, or clickbait event if it is not present in the final scenes.
- If quality warnings mention a reference/thumbnail mismatch risk, correct the prompt to match the script rather than maximizing shock.
- Thumbnail can be dramatic, but its subject, action, setting, and story state must be true to the final scenes.

Return as JSON:
{{
  "background_ref_prompt_en": "Detailed environment/background reference image in {style} style. Show the main world setting with correct lighting, atmosphere, color palette, and scale. Include key location details. No characters.",
  "thumbnail_ref_prompt_en": "YouTube thumbnail based on the actual final script: main true subject/action in foreground, high contrast lighting, {style} style, emotionally intense but story-accurate, {aspect_ratio}."
}}
Return ONLY raw valid JSON. No markdown.
"""

# ─── SERIES PROMPTS ───────────────────────────────────────────────────────────

SERIES_SUGGESTION_PROMPT = """
Bạn là một nhà sản xuất phim và biên kịch xuất sắc. Hãy thiết lập dàn ý (outline) cho một chuỗi video (series) gồm {num_episodes} tập từ ý tưởng lớn sau:
Tiêu đề chuỗi: {title}
Ý tưởng chủ đạo: {big_idea}
Chế độ sinh: {generation_mode} (series_short: các tập ngắn 1-3 phút; series_long: các tập dài 5-15 phút)

Yêu cầu bắt buộc:
1. Sinh ĐÚNG {num_episodes} tập, đánh số từ 1 đến {num_episodes}.
2. Mỗi tập phải có sự tiếp nối logic về cốt truyện với tập trước — nhân vật, xung đột, và diễn biến phải liên kết xuyên suốt.
3. Đảm bảo có arc cảm xúc rõ ràng xuyên suốt series: mở đầu giới thiệu → xung đột leo thang → đỉnh điểm → giải quyết (ít nhất phải có 4 giai đoạn này nếu số tập đủ).
4. Mỗi concept phải đề cập đến trạng thái nhân vật và plot thread được xây dựng từ tập trước (ngoại trừ tập 1).

Hãy trả về cấu trúc JSON chính xác như sau (ĐÚNG {num_episodes} phần tử trong mảng episodes):
{{
  "series_title": "Tiêu đề hấp dẫn cho toàn bộ series",
  "overall_arc": "Mô tả ngắn gọn về arc cảm xúc và cốt truyện tổng thể của series (2-3 câu)",
  "episodes": [
    {{
      "episode_number": 1,
      "title": "Tiêu đề tập 1",
      "concept": "Tóm tắt ngắn gọn nội dung cốt lõi của tập 1 bằng tiếng Việt (2-3 câu)",
      "narrative_stage": "setup|rising|climax|resolution",
      "cliffhanger_hint": "Gợi ý nút thắt/câu hỏi bỏ ngỏ cuối tập này để dẫn vào tập sau"
    }}
  ]
}}
Lưu ý: Mảng episodes PHẢI có ĐÚNG {num_episodes} phần tử. Không thêm, không bớt.
"""

SERIES_NEXT_EPISODE_PROMPT = """
Hãy gợi ý 3 phương án kịch bản tóm tắt cho Tập {episode_number} của chuỗi video (series) "{series_title}".
Ý tưởng lớn của chuỗi: {big_idea}
Phong cách chung của chuỗi: {style}
Ý tưởng phác thảo cho Tập {episode_number} từ dàn ý: {outline_concept}

Dưới đây là ngữ cảnh liên tục từ các tập trước đó (rolling context):
{context_str}
{user_feedback_prompt}

Hãy phân tích kỹ cliffhanger (nút thắt) và trạng thái nhân vật của tập trước để sinh gợi ý tập tiếp theo liền mạch, kịch tính và logic.
Trả về kết quả định dạng JSON chính xác như sau:
{{
  "suggestions": [
    {{
      "index": 0,
      "title": "Tiêu đề tập {episode_number} gợi ý 1",
      "synopsis": "Tóm tắt chi tiết cốt truyện diễn biến của tập này bằng tiếng Việt (4-6 câu).",
      "mood": "Tông cảm xúc chủ đạo",
      "hook": "Câu thoại hoặc lời dẫn mở đầu hấp dẫn bằng tiếng Việt",
      "topic_type": "historical" | "scientific" | "fictional_original"
    }},
    {{
      "index": 1,
      "title": "Tiêu đề tập {episode_number} gợi ý 2",
      "synopsis": "...",
      "mood": "...",
      "hook": "...",
      "topic_type": "..."
    }},
    {{
      "index": 2,
      "title": "Tiêu đề tập {episode_number} gợi ý 3",
      "synopsis": "...",
      "mood": "...",
      "hook": "...",
      "topic_type": "..."
    }}
  ]
}}
"""

POST_GENERATION_SUGGESTION_PROMPT = """
Dựa trên kịch bản video đã hoàn thành:
{script_json}

Hãy đề xuất 3 ý tưởng/gợi ý kịch bản video tiếp theo hấp dẫn và có liên quan mật thiết (tông màu, cốt truyện hoặc chủ đề).
Trả về kết quả định dạng JSON chính xác như sau:
{{
  "suggestions": [
    {{
      "index": 0,
      "title": "Tiêu đề gợi ý 1 (tiếng Việt)",
      "synopsis": "Tóm tắt kịch bản đề xuất (tiếng Việt, 3-5 câu)",
      "mood": "Tông cảm xúc chủ đạo",
      "topic_type": "historical" | "scientific" | "fictional_original"
    }},
    {{
      "index": 1,
      "title": "Tiêu đề gợi ý 2 (tiếng Việt)",
      "synopsis": "...",
      "mood": "...",
      "topic_type": "..."
    }},
    {{
      "index": 2,
      "title": "Tiêu đề gợi ý 3 (tiếng Việt)",
      "synopsis": "...",
      "mood": "...",
      "topic_type": "..."
    }}
  ]
}}
"""

CONTEXT_COMPRESSION_PROMPT = """
Bạn là trợ lý AI chuyên nghiệp về biên kịch và kể chuyện. Hãy phân tích và nén kịch bản chi tiết của Tập {episode_num} thành một tóm tắt ngữ cảnh ngắn gọn (bằng tiếng Việt) để phục vụ cho việc sinh tập tiếp theo.

Kịch bản đầu vào:
{script_json}

Hãy trả về một đối tượng JSON có cấu trúc chính xác như sau:
{{
  "plot_summary": "Tóm tắt mạch truyện chính diễn ra trong tập này bằng tiếng Việt (2-3 câu).",
  "character_states": {{
    "<Tên nhân vật A>": "Trạng thái vật lý, cảm xúc, vị trí, đạo cụ đang giữ của nhân vật này ở cuối tập.",
    "<Tên nhân vật B>": "..."
  }},
  "cliffhanger": "Sự kiện bỏ lửng hoặc nút thắt ở cuối tập để tạo tiền đề cho tập sau bằng tiếng Việt.",
  "emotion_summary": "Tông cảm xúc chủ đạo xuyên suốt tập này bằng tiếng Việt.",
  "key_events": ["Sự kiện cột mốc 1", "Sự kiện cột mốc 2", "Sự kiện cột mốc 3"]
}}
Lưu ý: key_events PHẢI là array JSON, không phải string.
"""
