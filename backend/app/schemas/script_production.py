from pydantic import BaseModel, Field
from enum import Enum
from typing import Any, Literal
import datetime

# ─── ENUMS ───────────────────────────────────────────────
class InputType(str, Enum):
    """Phân loại nguồn đầu vào của dự án."""
    TOPIC = "topic"              # Từ chủ đề nóng
    MANUAL = "manual"            # Tự nhập ý tưởng viết tay
    YOUTUBE_URL = "youtube_url"  # Từ URL YouTube (tùy chọn phụ)

class TopicType(str, Enum):
    """Phân loại loại hình chủ đề."""
    HISTORICAL = "historical"
    SCIENTIFIC = "scientific"
    FICTIONAL_MYTHOLOGY = "fictional_mythology"
    FICTIONAL_ORIGINAL = "fictional_original"

class ProjectStatus(str, Enum):
    """Các trạng thái của dự án trong pipeline."""
    DRAFT = "draft"
    SUGGESTIONS_GENERATED = "suggestions_generated"
    GENERATING_SCRIPT = "generating_script"
    SCRIPT_FAILED = "script_failed"
    SCRIPT_GENERATED = "script_generated"

class PresetStyle(str, Enum):
    """Các phong cách video dựng sẵn."""
    ANIME = "anime"
    REALISTIC = "realistic"
    CINEMATIC = "cinematic"
    CARTOON = "cartoon"

# ─── TRENDING TOPICS ────────────────────────────────────
class TrendingTopicCreate(BaseModel):
    """Schema cho yêu cầu tạo mới chủ đề nóng."""
    name: str = Field(..., description="Tên chủ đề nóng hiển thị trên UI", min_length=1, max_length=255)
    description: str = Field("", description="Mô tả chi tiết hoặc gợi ý về chủ đề", max_length=1000)
    icon: str = Field("🔥", description="Icon hoặc emoji hiển thị đại diện", max_length=10)
    display_order: int = Field(0, description="Thứ tự hiển thị (số nhỏ xếp trước)")

class TrendingTopicUpdate(BaseModel):
    """Schema cập nhật chủ đề nóng."""
    name: str | None = Field(None, description="Tên chủ đề nóng mới")
    description: str | None = Field(None, description="Mô tả mới")
    icon: str | None = Field(None, description="Emoji mới")
    display_order: int | None = Field(None, description="Thứ tự hiển thị mới")
    is_active: bool | None = Field(None, description="Cờ ẩn/hiện")

class TrendingTopicResponse(BaseModel):
    """Dữ liệu trả về cho một chủ đề nóng."""
    id: int
    name: str
    description: str
    icon: str
    display_order: int
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}

# ─── INPUT CONFIGS ──────────────────────────────────────
class StyleInput(BaseModel):
    """Cấu hình phong cách thiết kế video, cho phép chọn mẫu có sẵn hoặc tự nhập."""
    preset: PresetStyle | None = Field(None, description="Lựa chọn phong cách từ danh sách sẵn có")
    custom: str | None = Field(None, description="Phong cách tự nhập chi tiết (Ưu tiên áp dụng nếu có)", max_length=200)

class GenerateSuggestionsRequest(BaseModel):
    """Yêu cầu sinh gợi ý kịch bản tóm tắt."""
    input_type: InputType = Field(..., description="Loại dữ liệu đầu vào")
    input_content: str = Field(..., description="Nội dung ý tưởng/Transcript/URL YouTube tương ứng", min_length=1, max_length=60000)
    topic_id: int | None = Field(None, description="ID chủ đề nóng nếu sinh từ danh sách chủ đề")
    style: StyleInput = Field(default_factory=lambda: StyleInput(preset=PresetStyle.ANIME), description="Cấu hình phong cách")
    num_scenes: int = Field(8, ge=4, le=200, description="Số lượng phân cảnh muốn sinh (4-200, mặc định 8)")
    num_suggestions: int = Field(5, description="Số lượng gợi ý kịch bản muốn sinh (mặc định 5)", ge=2, le=10)
    model_name: str = Field("gemini-3.1-flash-lite", description="Model AI sử dụng", min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._:-]+$")
    generation_mode: Literal["single", "longform", "series_short", "series_long"] = Field("single", description="Chế độ sinh: 'single' | 'longform' | 'series_short' | 'series_long'")
    # Duration persistence guard: the frontend chooses timing before project
    # creation, so the suggestion request must carry it into the saved draft.
    scene_duration_sec: int | None = Field(8, ge=4, le=12, description="Thời lượng mỗi phân cảnh tính bằng giây")
    regenerate_with_input: str | None = Field(None, description="Yêu cầu làm mới/chỉnh sửa gợi ý từ người dùng", max_length=2000)

# ─── SUGGESTIONS CARDS ──────────────────────────────────
class ScriptSuggestion(BaseModel):
    """Thông tin chi tiết của một thẻ gợi ý kịch bản."""
    index: int = Field(..., description="Vị trí index của gợi ý (0-4)")
    title: str = Field(..., description="Tiêu đề gợi ý kịch bản")
    synopsis: str = Field(..., description="Tóm tắt ngắn gọn cốt truyện kịch bản")
    mood: str = Field(..., description="Tông cảm xúc chủ đạo (kịch tính, hồi hộp, tươi sáng...)")
    hook: str = Field(..., description="Câu thoại/dẫn mở đầu thu hút người xem")
    is_original: bool = Field(False, description="Đánh dấu đây là bản dựa sát theo nội dung gốc nhất")
    topic_type: TopicType = Field(TopicType.FICTIONAL_ORIGINAL, description="Phân loại loại hình chủ đề")
    narrative_shape: str | None = Field(None, description="Emotion arc template shape (adventure, reflective, explanatory, tragedy, suspense)")
    has_named_historical_figure: bool | None = Field(None, description="Đánh dấu nếu có nhân vật lịch sử cụ thể được đặt tên")

class SuggestionsResponse(BaseModel):
    """Dữ liệu trả về chứa danh sách gợi ý kịch bản."""
    success: bool
    project_id: int = Field(..., description="ID của dự án tương ứng")
    suggestions: list[ScriptSuggestion] = Field(default_factory=list, description="Danh sách 5 gợi ý kịch bản")
    error: str | None = Field(None, description="Chi tiết lỗi nếu có")

# ─── FULL SCRIPT GENERATION ─────────────────────────────
class GenerateFullScriptRequest(BaseModel):
    """Yêu cầu sinh kịch bản chi tiết từ một gợi ý được chọn."""
    project_id: int = Field(..., description="ID dự án cần sinh kịch bản")
    suggestion_index: int = Field(..., description="Index của gợi ý được chọn (0 đến num_suggestions-1)", ge=0)
    model_name: str = Field("gemini-3.1-flash-lite", description="Model AI sử dụng", min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._:-]+$")
    topic_type_override: TopicType | None = Field(None, description="Loại chủ đề do user chọn đè lên AI classification")
    aspect_ratio: Literal["9:16", "16:9", "1:1"] | None = Field(None, description="Tỉ lệ khung hình (ví dụ: '9:16', '16:9')")
    scene_duration_sec: int | None = Field(None, description="Thời lượng mỗi phân cảnh tính bằng giây", ge=4, le=12)
    batch_mode: bool = Field(False, description="Chạy chế độ batch, bỏ qua sleep")
    generation_mode: Literal["single", "longform", "series_short", "series_long"] = Field("single", description="Chế độ sinh: 'single' | 'longform' | 'series_short' | 'series_long'")
    # Recovery guard: retry uses persisted artifacts by default, while restart
    # intentionally discards resume cache without adding a reset endpoint.
    restart: bool = Field(False, description="Bỏ qua cache đã lưu và sinh lại output từ đầu")

# ─── 9-SECTION OUTPUT FORMAT (Sections A-I) ─────────────
class CharacterPrompt(BaseModel):
    """Phần B: Một nhân vật trong kịch bản kèm prompt mô tả ngoại hình chi tiết bằng tiếng Anh."""
    character_name: str = Field(..., description="Tên nhân vật")
    description_en: str = Field(..., description="Mô tả chi tiết đặc điểm gương mặt, trang phục tiêu chuẩn bằng tiếng Anh để khóa nhân vật")
    description_vi: str = Field("", description="Mô tả chi tiết đặc điểm bằng tiếng Việt cho người dùng")
    key_identifiers_en: str | None = Field(None, description="2-3 từ khóa nhận diện visual quan trọng nhất của nhân vật bằng tiếng Anh")
    key_identifiers_vi: str | None = Field("", description="2-3 từ khóa nhận diện bằng tiếng Việt")

class EmotionArcEntry(BaseModel):
    """Emotion Arc entry describing physical & emotional continuity per scene."""
    scene_number: int = Field(..., description="Số thứ tự cảnh")
    emotion_label: str = Field(..., description="Nhãn cảm xúc (tiếng Việt)")
    beat_summary: str = Field(..., description="Tóm tắt nhịp kịch tính (tiếng Việt)")
    physical_state_end: str = Field(..., description="Trạng thái vật lý cuối phân cảnh (tiếng Việt)")
    camera_complexity: str = Field("medium", description="Độ phức tạp của camera (low/medium/high)")
    scene_lead_character: str | None = Field(None, description="Tên nhân vật chính dẫn dắt scene, lấy từ Phần B hoặc None")

class SceneScript(BaseModel):
    """Kịch bản chi tiết cho 1 phân cảnh 8 giây (Phần D, E, F)."""
    scene_number: int = Field(..., description="Số thứ tự cảnh (bắt đầu từ 1)")
    title: str = Field(..., description="Tiêu đề cảnh kèm thời gian (Ví dụ: 'Scene 1 [00:00 - 00:08]')")
    
    # Phần D: Mô tả bằng tiếng Việt để người dùng đọc hiểu
    action_detail_vi: str = Field(..., description="Nội dung hành động chi tiết xảy ra trong cảnh (tiếng Việt)")
    emotion_gesture_vi: str = Field(..., description="Diễn biến cảm xúc và cử chỉ của nhân vật (tiếng Việt)")
    camera_movement_vi: str = Field(..., description="Góc quay và chuyển động camera chi tiết (tiếng Việt)")
    transition_to_next_vi: str = Field(..., description="Logic/Kỹ thuật chuyển sang cảnh tiếp theo (tiếng Việt)")
    
    # Phần E: Prompt tiếng Anh tối ưu cho sinh video qua Veo 3
    veo3_prompt_en: str = Field(..., description="Prompt tiếng Anh chi tiết kết hợp bối cảnh, nhân vật, hành động, camera và tag styling")
    veo3_prompt_vi: str = Field("", description="Giải thích nội dung prompt tiếng Anh bằng tiếng Việt")
    
    # Phần F: Negative prompt tiếng Anh cho từng cảnh
    negative_prompt_en: str = Field(..., description="Từ khóa phủ định tiếng Anh chống artifact chuyển động dị dạng")
    scene_specific_negative_en: str | None = Field(None, description="Từ khóa phủ định đặc thù tiếng Anh cho riêng cảnh này")
    
    # Bổ sung trường thuyết minh (v2.0: EN cinematic; legacy: VI)
    voice_over_vi: str | None = Field(None, description="Giọng đọc/lời bình tiếng Việt ngắn gọn (≤15 từ) — legacy field")
    voice_over_en: str | None = Field(None, description="Cinematic English voice narration (≤10 words) — v2.0")

    # Bổ sung trường kiểm chứng & phân loại
    historical_basis_vi: str | None = Field(None, description="Cơ sở lịch sử/khoa học làm căn cứ cho cảnh")
    needs_fact_check: bool = Field(False, description="Cờ đánh dấu cần con người xác minh lại tính chính xác")
    fact_check_note_vi: str | None = Field(None, description="Ghi chú về phần cần xác minh lịch sử/khoa học")
    verifiability_level: str | None = Field(None, description="Mức độ kiểm chứng: specific_event, general_consensus, unverifiable_generalization")

class ReferenceImagePrompts(BaseModel):
    """Phần I: Prompt tạo ảnh tham khảo bối cảnh, nhân vật và thumbnail bằng tiếng Anh."""
    character_ref_prompt_en: str = Field(..., description="Prompt vẽ ảnh tham khảo nhân vật chính (Midjourney/Imagen)")
    background_ref_prompt_en: str = Field(..., description="Prompt vẽ ảnh tham khảo bối cảnh nền")
    thumbnail_ref_prompt_en: str = Field(..., description="Prompt vẽ ảnh thiết kế clickbait thumbnail thu hút")

class ContinuityBoard(BaseModel):
    """Phần G: Hướng dẫn ghép nối các cảnh đảm bảo sự đồng đều ánh sáng, tóc tai, trang phục."""
    continuity_prompt_en: str = Field("", description="Hướng dẫn ghép nối bằng tiếng Anh")
    continuity_prompt_vi: str = Field("", description="Hướng dẫn ghép nối bằng tiếng Việt")

class ScriptOutput(BaseModel):
    """Kịch bản video sản xuất hoàn thiện theo đúng format 9 phần A-I."""
    topic_type: TopicType = Field(TopicType.FICTIONAL_ORIGINAL, description="Phân loại loại hình chủ đề của kịch bản")
    # Phần A: Phân tích tổng quan
    overview_analysis_vi: str = Field(..., description="Phân tích nhịp điệu, tông màu chủ đạo, góc máy và cảm xúc (tiếng Việt)")
    
    # Bản Kế Hoạch Sản Xuất mới
    storyline_vi: str = Field(default="", description="Mạch câu chuyện (tiếng Việt)")
    stages_vi: str = Field(default="", description="Phân chia giai đoạn (tiếng Việt)")
    progression_vi: str = Field(default="", description="Tiến trình cảnh (tiếng Việt)")
    camera_strategy_vi: str = Field(default="", description="Chiến lược Camera (tiếng Việt)")
    continuity_locks_vi: str = Field(default="", description="Khóa tính liên tục trực quan (tiếng Việt)")
    form_locks_vi: str = Field(default="", description="Khóa hình dáng visual cứng (tiếng Việt)")
    age_stage_locks_vi: str = Field(default="", description="Khóa độ tuổi và giai đoạn phát triển (tiếng Việt)")
    geometry_locks_vi: str = Field(default="", description="Khóa hình học và bố cục bối cảnh (tiếng Việt)")
    risk_logic_vi: str = Field(default="", description="Logic tăng tiến rủi ro/xung đột (tiếng Việt)")
    
    # Phần B: Prompt khóa nhân vật
    characters: list[CharacterPrompt] = Field(..., description="Danh sách nhân vật kèm prompt khóa bằng tiếng Anh")
    # Phần C: Prompt khóa bối cảnh
    environment_master_prompt_en: str = Field(..., description="Mô tả chi tiết không gian bối cảnh nền, ánh sáng, bầu không khí bằng tiếng Anh")
    environment_master_prompt_vi: str = Field("", description="Mô tả không gian bằng tiếng Việt")
    # Emotion arc tóm tắt
    emotion_arc: list[EmotionArcEntry] | None = Field(None, description="Emotion arc tóm tắt của kịch bản")
    # Phần D+E+F: Danh sách phân cảnh chi tiết
    scenes: list[SceneScript] = Field(..., description="Danh sách các phân cảnh 8 giây liên tục")
    # Phần G: Mô tả liên mạch (Continuity Board)
    continuity_board: ContinuityBoard = Field(default_factory=ContinuityBoard, description="Hướng dẫn ghép nối các cảnh đảm bảo sự đồng đều ánh sáng, tóc tai, trang phục")
    # Phần H: Negative prompt toàn cục
    global_negative_prompt_en: str = Field(..., description="Prompt phủ định chung cho toàn bộ video bằng tiếng Anh")
    # Phần I: Prompt ảnh tham khảo
    reference_images: ReferenceImagePrompts = Field(..., description="Các prompt tạo ảnh tham khảo bối cảnh, nhân vật, và ảnh bìa bằng tiếng Anh")
    
    # Prompt 0 Identity Lock (v2.0) — full production bible in English
    prompt_0: dict | None = Field(None, description="Prompt 0 identity lock object (v2.0): primary_subject_en, character_lock, setting_lock_en, continuity_lock_en, negative_constraints_en, etc.")
    voice_sound_strategy_vi: str = Field(default="", description="Voice/Sound strategy in Vietnamese (v2.0)")

    # Nối tập series
    series_bridge_vi: str | None = Field(None, description="Câu cầu nối giữa tập hiện tại và tập tiếp theo trong series (tiếng Việt)")


# Durable schema guard: v3 separates production truth, UI display helpers, and verification
# so future prompts do not keep adding mixed flat scene fields.
class SceneTimingV3(BaseModel):
    """Backend-owned scene timing; title is deterministic and never LLM-owned."""
    start_sec: int = Field(..., description="Thời điểm bắt đầu cảnh, tính bằng giây")
    end_sec: int = Field(..., description="Thời điểm kết thúc cảnh, tính bằng giây")
    title: str = Field(..., description="Tiêu đề cảnh do backend tính từ scene_number và duration")


# Durable schema guard: source contains only the real production material consumed by video/audio tools.
class SceneSourceV3(BaseModel):
    """Dữ liệu sản xuất thật của cảnh, ưu tiên sinh từ LLM."""
    action_vi: str = Field("", description="Mô tả hành động tiếng Việt cho biên tập")
    veo_prompt_en: str = Field("", description="Prompt tiếng Anh để sinh video")
    voice_en: str | None = Field(None, description="Narration tiếng Anh")
    scene_negative_en: str = Field("", description="Negative prompt đặc thù của cảnh")


# Durable schema guard: display fields are derived/readability aids and must not hard-block final output.
class SceneDisplayV3(BaseModel):
    """Trường phục vụ hiển thị/UI, có thể được backend suy ra."""
    voice_vi: str | None = Field(None, description="Bản dịch/diễn giải narration tiếng Việt")
    camera_vi: str = Field("", description="Diễn giải camera tiếng Việt")
    emotion_vi: str = Field("", description="Diễn giải cảm xúc/cử chỉ tiếng Việt")
    transition_vi: str = Field("", description="Diễn giải chuyển cảnh tiếng Việt")
    prompt_summary_vi: str = Field("", description="Tóm tắt prompt tiếng Việt cho người đọc")


# Durable schema guard: verification fields are grouped so fact-check status is explicit
# without scattering null labels through the source scene contract.
class SceneVerificationV3(BaseModel):
    """Thông tin fact-check/risk của cảnh."""
    status: str = Field("unverified", description="unverified | checked | needs_review | corrected")
    level: str | None = Field(None, description="specific_event | general_consensus | unverifiable_generalization")
    basis_vi: str | None = Field(None, description="Cơ sở lịch sử/khoa học nếu có")
    risk_flags: list[str] = Field(default_factory=list, description="Cờ rủi ro cần chú ý")
    notes_vi: list[str] = Field(default_factory=list, description="Ghi chú kiểm chứng bằng tiếng Việt")


# Durable schema guard: meta records origin/edit trail so later agents do not re-derive
# fields blindly or delete history from semantic/fact-check passes.
class SceneMetaV3(BaseModel):
    """Metadata nội bộ theo dõi nguồn field và các phase đã chỉnh."""
    field_origin: dict[str, str] = Field(default_factory=dict)
    edited_by: list[str] = Field(default_factory=list)


# Durable schema guard: canonical scene v3 is nested by purpose; legacy SceneScript remains for UI compatibility.
class SceneV3(BaseModel):
    """Scene canonical v3."""
    scene_number: int
    timing: SceneTimingV3
    source: SceneSourceV3 = Field(default_factory=SceneSourceV3)
    display: SceneDisplayV3 = Field(default_factory=SceneDisplayV3)
    verification: SceneVerificationV3 = Field(default_factory=SceneVerificationV3)
    generation: dict[str, Any] = Field(default_factory=lambda: {"failed": False, "error": None})
    meta: SceneMetaV3 = Field(default_factory=SceneMetaV3)


# Durable schema guard: top-level v3 groups blueprint/anchors/internal state so public
# production data no longer competes with pipeline bookkeeping fields.
class ScriptOutputV3(BaseModel):
    """Canonical JSON v3 cho backend lưu trữ và future UI."""
    schema_version: Literal["3.0"] = "3.0"
    topic: dict[str, Any] = Field(default_factory=dict)
    production_plan: dict[str, Any] = Field(default_factory=dict)
    anchors: dict[str, Any] = Field(default_factory=dict)
    emotion_arc: list[EmotionArcEntry] = Field(default_factory=list)
    scenes: list[SceneV3] = Field(default_factory=list)
    reference_images: ReferenceImagePrompts | dict[str, Any] = Field(default_factory=dict)
    internal: dict[str, Any] = Field(default_factory=dict)
    series_bridge_vi: str | None = None
    post_suggestions: list[dict[str, Any]] | None = None


class FullScriptResponse(BaseModel):
    """Dữ liệu phản hồi trả về kịch bản đầy đủ."""
    success: bool
    project_id: int
    script: ScriptOutput | None = Field(None, description="Kịch bản chi tiết hoàn chỉnh")
    error: str | None = Field(None, description="Chi tiết lỗi nếu sinh thất bại")


# ─── SERIES AND EPISODES SCHEMAS ────────────────────────
class SeriesCreate(BaseModel):
    title: str = Field(..., description="Tiêu đề của series", min_length=1, max_length=500)
    big_idea: str | None = Field(None, description="Ý tưởng cốt lõi của series", max_length=60000)
    generation_mode: Literal["series_short", "series_long"] = Field("series_short", description="Chế độ sinh: 'series_short' | 'series_long'")
    episode_duration_minutes: int | None = Field(None, description="Thời lượng mỗi tập phim bằng phút (cho series_long)", ge=1, le=30)
    style: str = Field("anime", description="Phong cách video", min_length=1, max_length=200)
    num_episodes: int = Field(5, ge=3, le=30, description="Số tập trong chuỗi (mặc định 5, tối đa 30)")

class SeriesResponse(BaseModel):
    id: int
    title: str
    big_idea: str | None
    series_outline: dict | None = None
    generation_mode: str
    episode_duration_minutes: int | None
    style: str
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}

class EpisodeCreate(BaseModel):
    series_id: int = Field(..., description="ID của series")
    title: str | None = Field(None, description="Tiêu đề của tập", max_length=500)
    user_input: str | None = Field(None, description="Yêu cầu/phản hồi của người dùng", max_length=2000)

class EpisodeResponse(BaseModel):
    id: int
    series_id: int
    episode_number: int
    project_id: int | None
    title: str | None
    context_summary: dict | None = None
    next_suggestions: list | None = None
    user_input: str | None
    status: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}

class NextSuggestionRequest(BaseModel):
    user_input: str | None = Field(None, description="Nhập ý tưởng/chỉnh sửa của người dùng cho tập tiếp theo", max_length=2000)

class NextSuggestionResponse(BaseModel):
    success: bool
    suggestions: list[dict] = Field(default_factory=list, description="Danh sách 3 gợi ý cho tập tiếp theo")
    error: str | None = Field(None, description="Chi tiết lỗi nếu có")
