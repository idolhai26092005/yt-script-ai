import { secureStorage } from '../utils/secureStorage';

let baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
if (!baseUrl.endsWith('/api/v1') && !baseUrl.endsWith('/api/v1/')) {
  baseUrl = baseUrl.endsWith('/') ? `${baseUrl}api/v1` : `${baseUrl}/api/v1`;
}
export const API_URL = baseUrl;

// Helper to get headers with X-API-Key and optionally X-Gemini-API-Key
export function getAuthHeaders(geminiApiKey?: string): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  const appApiKey = secureStorage.getItem('APP_API_KEY');
  if (appApiKey) {
    headers['X-API-Key'] = appApiKey.trim();
  }
  if (geminiApiKey) {
    headers['X-Gemini-API-Key'] = geminiApiKey.trim();
  }
  return headers;
}

export interface GeminiTestResponse {
  success: boolean;
  response: string;
  error?: string;
}

type JsonRecord = Record<string, unknown>;

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null;
}

function readStringField(value: unknown, field: string): string {
  if (!isRecord(value)) return '';
  const fieldValue = value[field];
  return typeof fieldValue === 'string' ? fieldValue : '';
}

export function getErrorMessage(err: unknown, fallback: string): string {
  return readStringField(err, 'message') || fallback;
}

export function parseErrorDetail(detail: unknown): string {
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map(item => {
      if (isRecord(item)) {
        return readStringField(item, 'msg') || JSON.stringify(item);
      }
      return String(item);
    }).join(', ');
  }
  if (isRecord(detail)) {
    return readStringField(detail, 'message') || JSON.stringify(detail);
  }
  return String(detail);
}

export async function testGeminiConnection(apiKey: string, prompt: string, modelName?: string): Promise<GeminiTestResponse> {
  try {
    const response = await fetch(`${API_URL}/gemini/test`, {
      method: 'POST',
      headers: getAuthHeaders(apiKey),
      body: JSON.stringify({ prompt, model_name: modelName }),
    });

    if (response.status === 401) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        response: '',
        error: parseErrorDetail(readStringField(errorData, 'detail')) || 'Unauthorized: API Key is invalid or missing.',
      };
    }

    if (!response.ok) {
      return {
        success: false,
        response: '',
        error: `HTTP Error ${response.status}: ${response.statusText}`,
      };
    }

    return await response.json();
  } catch (err: unknown) {
    return {
      success: false,
      response: '',
      error: getErrorMessage(err, 'Failed to connect to backend server.'),
    };
  }
}

export interface ModelInfo {
  id: string;
  display_name: string;
  description: string;
  group: 'fast' | 'quality' | 'backup' | 'fallback';
  icon: string;
  badge: string | null;
  popular: boolean;
  rpd: number;
  remaining_rpd: number;
  used_today: number;
  status: 'active' | 'cooldown' | 'exhausted';
}

export interface GetModelsResponse {
  success: boolean;
  models: ModelInfo[];
  error?: string;
}

export async function fetchAvailableModels(): Promise<GetModelsResponse> {
  try {
    const response = await fetch(`${API_URL}/gemini/models`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        models: [],
        error: parseErrorDetail(readStringField(errorData, 'detail')) || `HTTP Error ${response.status}: ${response.statusText}`,
      };
    }

    return await response.json();
  } catch (err: unknown) {
    return {
      success: false,
      models: [],
      error: getErrorMessage(err, 'Failed to connect to backend server.'),
    };
  }
}


export interface TranscriptResponse {
  success: boolean;
  video_id: string | null;
  transcript: string | null;
  segments: { text: string; start: number; duration: number }[] | null;
  error: string | null;
}

export async function fetchTranscript(url: string): Promise<TranscriptResponse> {
  try {
    const response = await fetch(`${API_URL}/transcript/`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ url }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        video_id: null,
        transcript: null,
        segments: null,
        error: parseErrorDetail(readStringField(errorData, 'detail')) || `HTTP Error ${response.status}: ${response.statusText}`,
      };
    }

    return await response.json();
  } catch (err: unknown) {
    return {
      success: false,
      video_id: null,
      transcript: null,
      segments: null,
      error: getErrorMessage(err, 'Failed to connect to backend server.'),
    };
  }
}

export interface ReferenceItem {
  title: string;
  source: string;
  link?: string;
  relevance: string;
}

export interface ScriptStructureItem {
  part: string;
  duration_sec: number;
  key_points: string[];
  is_ad_segment?: boolean;
}

export interface ScriptStructure {
  video_summary: string;
  tone: string;
  structure: ScriptStructureItem[];
  references?: ReferenceItem[];
}

export interface GenerateScriptResponse {
  success: boolean;
  structure: ScriptStructure | null;
  script_en: string | null;
  script_vi: string | null;
  script_text?: string | null;
  language?: string | null;
  error: string | null;
}

export async function generateScript(
  apiKey: string,
  transcript: string,
  modelName: string = 'gemini-2.5-flash'
): Promise<GenerateScriptResponse> {
  try {
    const response = await fetch(`${API_URL}/gemini/generate-script`, {
      method: 'POST',
      headers: getAuthHeaders(apiKey),
      body: JSON.stringify({
        transcript,
        model_name: modelName,
      }),
    });

    if (response.status === 401) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        structure: null,
        script_en: null,
        script_vi: null,
        error: parseErrorDetail(readStringField(errorData, 'detail')) || 'Unauthorized: API Key is invalid or missing.',
      };
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        structure: null,
        script_en: null,
        script_vi: null,
        error: parseErrorDetail(readStringField(errorData, 'detail')) || `HTTP Error ${response.status}: ${response.statusText}`,
      };
    }

    return await response.json();
  } catch (err: unknown) {
    return {
      success: false,
      structure: null,
      script_en: null,
      script_vi: null,
      error: getErrorMessage(err, 'Failed to connect to backend server.'),
    };
  }
}

export interface VideoSuggestionItem {
  title_en: string;
  title_vi: string;
  hook_en: string;
  hook_vi: string;
  concept_en: string;
  concept_vi: string;
  why_it_works_en: string;
  why_it_works_vi: string;
}

export interface VideoSuggestionsResponse {
  success: boolean;
  suggestions: VideoSuggestionItem[] | null;
  error: string | null;
}

export async function fetchVideoSuggestions(
  apiKey: string,
  videoId: string,
  modelName: string = 'gemini-2.5-flash'
): Promise<VideoSuggestionsResponse> {
  try {
    const response = await fetch(`${API_URL}/gemini/suggest-next-videos`, {
      method: 'POST',
      headers: getAuthHeaders(apiKey),
      body: JSON.stringify({
        video_id: videoId,
        model_name: modelName,
      }),
    });

    if (response.status === 401) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        suggestions: null,
        error: parseErrorDetail(readStringField(errorData, 'detail')) || 'Unauthorized: API Key is invalid or missing.',
      };
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        suggestions: null,
        error: parseErrorDetail(readStringField(errorData, 'detail')) || `HTTP Error ${response.status}: ${response.statusText}`,
      };
    }

    return await response.json();
  } catch (err: unknown) {
    return {
      success: false,
      suggestions: null,
      error: getErrorMessage(err, 'Failed to fetch video suggestions.'),
    };
  }
}

export interface BatchSuggestionSubmitResponse {
  success: boolean;
  task_id: string;
  status: string;
  error: string | null;
}

export interface BatchSuggestionStatusResponse {
  success: boolean;
  task_id: string;
  status: string;
  suggestions: VideoSuggestionItem[] | null;
  error: string | null;
}

export async function submitVideoSuggestions(
  apiKey: string,
  videoId: string,
  modelName: string = 'gemini-2.5-flash'
): Promise<BatchSuggestionSubmitResponse> {
  try {
    const response = await fetch(`${API_URL}/gemini/suggest-next-videos/submit`, {
      method: 'POST',
      headers: getAuthHeaders(apiKey),
      body: JSON.stringify({
        video_id: videoId,
        model_name: modelName,
      }),
    });

    if (response.status === 401) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        task_id: '',
        status: 'error',
        error: parseErrorDetail(readStringField(errorData, 'detail')) || 'Unauthorized: API Key is invalid or missing.',
      };
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        task_id: '',
        status: 'error',
        error: parseErrorDetail(readStringField(errorData, 'detail')) || `HTTP Error ${response.status}: ${response.statusText}`,
      };
    }

    return await response.json();
  } catch (err: unknown) {
    return {
      success: false,
      task_id: '',
      status: 'error',
      error: getErrorMessage(err, 'Failed to submit video suggestions batch request.'),
    };
  }
}

export async function checkVideoSuggestionsStatus(
  apiKey: string,
  taskId: string
): Promise<BatchSuggestionStatusResponse> {
  try {
    const response = await fetch(`${API_URL}/gemini/suggest-next-videos/status/${taskId}`, {
      method: 'GET',
      headers: getAuthHeaders(apiKey),
    });

    if (response.status === 401) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        task_id: taskId,
        status: 'error',
        suggestions: null,
        error: parseErrorDetail(readStringField(errorData, 'detail')) || 'Unauthorized: API Key is invalid or missing.',
      };
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        task_id: taskId,
        status: 'error',
        suggestions: null,
        error: parseErrorDetail(readStringField(errorData, 'detail')) || `HTTP Error ${response.status}: ${response.statusText}`,
      };
    }

    return await response.json();
  } catch (err: unknown) {
    return {
      success: false,
      task_id: taskId,
      status: 'error',
      suggestions: null,
      error: getErrorMessage(err, 'Failed to check suggestions status.'),
    };
  }
}


// Admin API Key Management Interfaces
export interface APIKeyResponse {
  id: number;
  key_hash: string;
  owner: string;
  quota_limit: number;
  quota_used: number;
  expiry: string | null;
  is_active: boolean;
  created_at: string;
}

export interface APIKeyGeneratedResponse {
  plain_key: string;
  api_key: APIKeyResponse;
}

export interface APIKeyCreate {
  owner: string;
  quota_limit: number;
  expiry: string | null;
}

// Admin API Key Management Functions
export async function listAdminKeys(adminSecret: string): Promise<APIKeyResponse[]> {
  const response = await fetch(`${API_URL}/admin/keys`, {
    method: 'GET',
    headers: {
      'X-Admin-Secret': adminSecret,
    },
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Không thể tải danh sách API Key.');
  }
  return response.json();
}

export async function createAdminKey(adminSecret: string, data: APIKeyCreate): Promise<APIKeyGeneratedResponse> {
  const response = await fetch(`${API_URL}/admin/keys`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Secret': adminSecret,
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Không thể tạo API Key.');
  }
  return response.json();
}

export async function revokeAdminKey(adminSecret: string, keyId: number): Promise<APIKeyResponse> {
  const response = await fetch(`${API_URL}/admin/keys/${keyId}`, {
    method: 'DELETE',
    headers: {
      'X-Admin-Secret': adminSecret,
    },
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Không thể thu hồi API Key.');
  }
  return response.json();
}

export async function validateAppKey(appApiKey: string): Promise<{ success: boolean; error?: string }> {
  try {
    const response = await fetch(`${API_URL}/gemini/validate-app-key`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': appApiKey.trim(),
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: parseErrorDetail(readStringField(errorData, 'detail')) || `HTTP Error ${response.status}: ${response.statusText}`,
      };
    }

    return { success: true };
  } catch (err: unknown) {
    return {
      success: false,
      error: getErrorMessage(err, 'Lỗi kết nối server.'),
    };
  }
}

// ─── NEW PRODUCTION PIPELINE API DEFINITIONS ─────────────────────────

export interface TrendingTopicResponse {
  id: number;
  name: string;
  description: string;
  icon: string;
  display_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TrendingTopicCreate {
  name: string;
  description?: string;
  icon?: string;
  display_order?: number;
}

export interface TrendingTopicUpdate {
  name?: string;
  description?: string;
  icon?: string;
  display_order?: number;
  is_active?: boolean;
}

export interface StyleInput {
  preset?: 'anime' | 'realistic' | 'cinematic' | 'cartoon' | null;
  custom?: string | null;
}

export interface GenerateSuggestionsRequest {
  input_type: 'topic' | 'manual' | 'youtube_url';
  input_content: string;
  topic_id?: number | null;
  style: StyleInput;
  num_scenes: number;
  num_suggestions: number;
  model_name: string;
  generation_mode?: string;
  scene_duration_sec?: number | null;
}

export interface ScriptSuggestion {
  index: number;
  title: string;
  synopsis: string;
  mood: string;
  hook: string;
  is_original: boolean;
  topic_type?: 'historical' | 'scientific' | 'fictional_mythology' | 'fictional_original';
}

export interface SuggestionsResponse {
  success: boolean;
  project_id: number;
  suggestions: ScriptSuggestion[];
  error?: string | null;
}

export interface GenerateFullScriptRequest {
  project_id: number;
  suggestion_index: number;
  model_name: string;
  topic_type_override?: 'historical' | 'scientific' | 'fictional_mythology' | 'fictional_original' | null;
  restart?: boolean;
}

export interface CharacterPrompt {
  character_name: string;
  description_en: string;
  description_vi?: string | null;
  key_identifiers_en?: string;
}

export interface EmotionArcEntry {
  scene_number: number;
  emotion_label: string;
  beat_summary: string;
  physical_state_end: string;
  camera_complexity: 'low' | 'medium' | 'high';
  scene_lead_character?: string;
}

export interface SceneScript {
  scene_number: number;
  title: string;
  action_detail_vi: string;
  emotion_gesture_vi: string;
  camera_movement_vi: string;
  transition_to_next_vi: string;
  veo3_prompt_en: string;
  veo3_prompt_vi?: string | null;
  negative_prompt_en: string;
  scene_specific_negative_en?: string | null;
  historical_basis_vi?: string | null;
  needs_fact_check?: boolean;
  fact_check_note_vi?: string | null;
  generation_failed?: boolean | 'true' | 'false';
  generation_error?: string | null;
  voice_over_vi?: string | null;
  voice_over_en?: string | null;  // v2.0 — cinematic English narration ≤10 words
}

export interface ReferenceImagePrompts {
  character_ref_prompt_en: string;
  background_ref_prompt_en: string;
  thumbnail_ref_prompt_en: string;
}

export interface ScriptOutput {
  topic_type?: 'historical' | 'scientific' | 'fictional_mythology' | 'fictional_original';
  overview_analysis_vi: string;
  storyline_vi?: string;
  stages_vi?: string;
  progression_vi?: string;
  camera_strategy_vi?: string;
  continuity_locks_vi?: string;
  form_locks_vi?: string;
  age_stage_locks_vi?: string;
  geometry_locks_vi?: string;
  risk_logic_vi?: string;
  characters: CharacterPrompt[];
  environment_master_prompt_en: string;
  emotion_arc?: EmotionArcEntry[];
  scenes: SceneScript[];
  continuity_prompt_en: string;
  global_negative_prompt_en: string;
  reference_images: ReferenceImagePrompts;
  // v2.0 additions
  prompt_0?: JsonRecord | null;
  voice_sound_strategy_vi?: string;
}

export interface ProjectResponse {
  id: number;
  title: string;
  input_type: 'topic' | 'manual' | 'youtube_url';
  input_content: string | null;
  topic_id: number | null;
  style: string;
  num_scenes: number;
  scene_duration?: number | null;
  status: string;
  suggestions?: ScriptSuggestion[] | null;
  selected_suggestion_idx?: number | null;
  script_output?: ScriptOutput | null;
  topic_type?: 'historical' | 'scientific' | 'fictional_mythology' | 'fictional_original' | null;
  generation_mode?: 'single' | 'longform' | 'series_short' | 'series_long' | null;
  created_at?: string;
  updated_at?: string;
}

export type HistoryFilter = 'all' | 'single' | 'series';
export type HistoryItemKind = 'single' | 'series';

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export interface HistoryTotals {
  all: number;
  single: number;
  series: number;
}

export interface HistoryItemResponse {
  kind: HistoryItemKind;
  id: number;
  title: string;
  status: string;
  updated_at: string;
  created_at: string;
  preview: string;
  meta: string;
}

export interface HistoryPageResponse extends PaginatedResponse<HistoryItemResponse> {
  totals: HistoryTotals;
}

// Fetch Active Topics (Public)
export async function fetchTrendingTopics(appApiKey: string): Promise<TrendingTopicResponse[]> {
  const response = await fetch(`${API_URL}/topics`, {
    method: 'GET',
    headers: getAuthHeaders(appApiKey),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(parseErrorDetail(readStringField(err, 'detail')) || 'Không thể tải danh sách chủ đề.');
  }
  const data = await response.json().catch(() => []);
  return Array.isArray(data) ? data : [];
}

// Fetch All Topics (Admin)
export async function fetchAdminTrendingTopics(adminSecret: string): Promise<TrendingTopicResponse[]> {
  const response = await fetch(`${API_URL}/topics/admin/all`, {
    method: 'GET',
    headers: {
      'X-Admin-Secret': adminSecret,
    },
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Không thể tải danh sách admin chủ đề.');
  }
  return response.json();
}

// Create Topic (Admin)
export async function createTrendingTopic(adminSecret: string, data: TrendingTopicCreate): Promise<TrendingTopicResponse> {
  const response = await fetch(`${API_URL}/topics/admin/topics`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Secret': adminSecret,
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Không thể tạo chủ đề nóng.');
  }
  return response.json();
}

// Update Topic (Admin)
export async function updateTrendingTopic(adminSecret: string, id: number, data: TrendingTopicUpdate): Promise<TrendingTopicResponse> {
  const response = await fetch(`${API_URL}/topics/admin/topics/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Secret': adminSecret,
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Không thể cập nhật chủ đề.');
  }
  return response.json();
}

// Delete Topic (Admin)
export async function deleteTrendingTopic(adminSecret: string, id: number): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_URL}/topics/admin/topics/${id}`, {
    method: 'DELETE',
    headers: {
      'X-Admin-Secret': adminSecret,
    },
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Không thể xóa chủ đề.');
  }
  return response.json();
}

// Toggle Topic (Admin)
export async function toggleTrendingTopic(adminSecret: string, id: number): Promise<TrendingTopicResponse> {
  const response = await fetch(`${API_URL}/topics/admin/topics/${id}/toggle`, {
    method: 'PATCH',
    headers: {
      'X-Admin-Secret': adminSecret,
    },
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Không thể thay đổi trạng thái chủ đề.');
  }
  return response.json();
}

// Reorder Topics (Admin)
export async function reorderTrendingTopics(adminSecret: string, ids: number[]): Promise<{ success: boolean }> {
  const response = await fetch(`${API_URL}/topics/admin/topics/reorder`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Secret': adminSecret,
    },
    body: JSON.stringify(ids),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Không thể cập nhật thứ tự chủ đề.');
  }
  return response.json();
}

// Generate Suggestions
export async function generateSuggestions(apiKey: string, req: GenerateSuggestionsRequest): Promise<SuggestionsResponse> {
  const response = await fetch(`${API_URL}/production/suggestions`, {
    method: 'POST',
    headers: getAuthHeaders(apiKey),
    body: JSON.stringify(req),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Lỗi sinh gợi ý kịch bản.');
  }
  return response.json();
}

// Get Project details
export async function getProject(apiKey: string, id: number): Promise<ProjectResponse> {
  const response = await fetch(`${API_URL}/production/project/${id}`, {
    method: 'GET',
    headers: getAuthHeaders(apiKey),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Không thể tải thông tin dự án.');
  }
  return response.json();
}

// Project pagination guard: backend returns `{items,total}` while older UI
// surfaces still consume a plain array through `listProjects`.
export async function fetchProjectsPage(
  apiKey: string,
  skip = 0,
  limit = 20
): Promise<PaginatedResponse<ProjectResponse>> {
  const response = await fetch(`${API_URL}/production/projects?skip=${skip}&limit=${limit}`, {
    method: 'GET',
    headers: getAuthHeaders(apiKey),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(parseErrorDetail(readStringField(err, 'detail')) || 'Không thể lấy danh sách lịch sử dự án.');
  }
  const data = await response.json().catch(() => ({ items: [] }));
  if (Array.isArray(data)) {
    return { items: data as ProjectResponse[], total: data.length, skip, limit };
  }
  if (isRecord(data) && Array.isArray(data.items)) {
    return {
      items: data.items as ProjectResponse[],
      total: typeof data.total === 'number' ? data.total : data.items.length,
      skip: typeof data.skip === 'number' ? data.skip : skip,
      limit: typeof data.limit === 'number' ? data.limit : limit,
    };
  }
  return { items: [], total: 0, skip, limit };
}

// Legacy project-list guard: SinglePage keeps its current array contract while
// the rebuilt History tab uses page metadata.
export async function listProjects(apiKey: string): Promise<ProjectResponse[]> {
  const page = await fetchProjectsPage(apiKey, 0, 20);
  return page.items;
}

// Unified history guard: single projects and series rows are paginated by the
// backend after one global updated_at sort.
export async function fetchHistoryPage(
  apiKey: string,
  kind: HistoryFilter = 'all',
  skip = 0,
  limit = 20
): Promise<HistoryPageResponse> {
  const response = await fetch(`${API_URL}/history?kind=${kind}&skip=${skip}&limit=${limit}`, {
    method: 'GET',
    headers: getAuthHeaders(apiKey),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(parseErrorDetail(readStringField(err, 'detail') || (isRecord(err) ? err.detail : null)) || 'Không thể tải lịch sử chung.');
  }
  const data = await response.json().catch(() => ({
    items: [],
    total: 0,
    totals: { all: 0, single: 0, series: 0 },
    skip,
    limit,
  }));
  if (isRecord(data) && Array.isArray(data.items)) {
    return {
      items: data.items as HistoryItemResponse[],
      total: typeof data.total === 'number' ? data.total : data.items.length,
      totals: isRecord(data.totals)
        ? {
            all: typeof data.totals.all === 'number' ? data.totals.all : data.items.length,
            single: typeof data.totals.single === 'number' ? data.totals.single : 0,
            series: typeof data.totals.series === 'number' ? data.totals.series : 0,
          }
        : { all: data.items.length, single: 0, series: 0 },
      skip: typeof data.skip === 'number' ? data.skip : skip,
      limit: typeof data.limit === 'number' ? data.limit : limit,
    };
  }
  return { items: [], total: 0, totals: { all: 0, single: 0, series: 0 }, skip, limit };
}

// Delete project
export async function deleteProject(apiKey: string, id: number): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_URL}/production/project/${id}`, {
    method: 'DELETE',
    headers: getAuthHeaders(apiKey),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Không thể xóa dự án.');
  }
  return response.json();
}

// --- SERIES V2 API CLIENT WRAPPERS ---

export type SeriesTopicType = 'historical' | 'scientific' | 'fictional_mythology' | 'fictional_original';
export type SeriesEndingMode = 'open_loop' | 'soft_cliffhanger' | 'hard_cliffhanger' | 'season_finale';
export type SeriesEpisodeStatus = 'pending' | 'generating' | 'completed' | 'needs_review' | 'failed';
export type SeriesStreamStatus = 'generating' | 'scene' | 'review' | 'done' | 'error';

export interface SeriesV2CreatePayload {
  title: string;
  premise: string;
  style: string;
  topic_type: SeriesTopicType;
  target_episode_count: number;
  default_scene_count: number;
  scene_duration_sec: number;
  model_name: string;
}

export interface SeriesResponse {
  schema_version: 'series.v2';
  id: number;
  title: string;
  premise: string;
  style: string;
  topic_type: SeriesTopicType;
  reality_binding_level: string;
  default_scene_count: number;
  scene_duration_sec: number;
  target_episode_count: number;
  status: string;
  series_bible: JsonRecord | null;
  season_map: JsonRecord | null;
  created_at: string;
  updated_at: string;
}

export interface EpisodeBrief {
  schema_version?: 'series.v2';
  phase?: string;
  episode_number?: number;
  title?: string;
  premise?: string;
  must_include?: string[];
  must_avoid?: string[];
  scene_count?: number;
  ending_mode?: SeriesEndingMode;
  notes?: string;
  prior_handoff?: JsonRecord;
  slot?: JsonRecord;
}

export interface EpisodeBriefUpdatePayload {
  title?: string;
  premise?: string;
  must_include?: string[];
  must_avoid?: string[];
  scene_count?: number;
  ending_mode?: SeriesEndingMode;
  notes?: string;
}

export interface SeriesScene {
  scene_number?: number;
  title?: string;
  action_detail_vi?: string;
  emotion_gesture_vi?: string;
  camera_movement_vi?: string;
  transition_to_next_vi?: string;
  veo3_prompt_en?: string;
  veo3_prompt_vi?: string | null;
  negative_prompt_en?: string;
  scene_specific_negative_en?: string | null;
  voice_over_vi?: string | null;
  voice_over_en?: string | null;
  handoff_state?: string | null;
  [key: string]: unknown;
}

export interface SeriesScriptOutput {
  schema_version?: 'series.v2';
  episode_number?: number;
  title?: string | null;
  scene_count?: number;
  ending_mode?: SeriesEndingMode;
  episode_blueprint?: JsonRecord;
  emotion_arc?: JsonRecord[];
  scenes?: SeriesScene[];
  review_report?: JsonRecord;
  continuity_delta?: JsonRecord;
  packaging?: JsonRecord;
}

export interface SeriesPhaseLogEntry {
  phase?: string;
  role?: string;
  schema_version?: 'series.v2';
  validation_status?: string;
  timestamp?: string;
  artifact_keys?: string[];
  validation_errors?: string[];
  warnings?: string[];
  latency_ms?: number;
  cache_hit?: boolean;
}

export interface EpisodeResponse {
  schema_version: 'series.v2';
  id: number;
  series_id: number;
  episode_number: number;
  status: SeriesEpisodeStatus;
  title: string | null;
  brief: EpisodeBrief | null;
  user_revision: EpisodeBriefUpdatePayload | null;
  scene_count: number;
  ending_mode: SeriesEndingMode;
  episode_blueprint: JsonRecord | null;
  emotion_arc: JsonRecord[] | null;
  scenes: SeriesScene[] | null;
  review_report: JsonRecord | null;
  continuity_delta: JsonRecord | null;
  script_output: SeriesScriptOutput | null;
  phase_log: SeriesPhaseLogEntry[] | null;
  created_at: string;
  updated_at: string;
}

export interface SeriesBriefCandidate {
  index: number;
  title: string;
  synopsis: string;
  mood: string;
  hook: string;
  brief: EpisodeBriefUpdatePayload;
}

export interface SeriesStreamEvent {
  schema_version?: 'series.v2';
  status?: SeriesStreamStatus;
  phase?: string | null;
  data?: SeriesScene | SeriesScriptOutput | JsonRecord | JsonRecord[] | null;
  message?: string | null;
}

// Series v2 page guard: workbench can keep using the unwrapped helper while
// history can read total metadata when needed.
export async function fetchSeriesPage(
  apiKey: string,
  skip = 0,
  limit = 100
): Promise<PaginatedResponse<SeriesResponse>> {
  const response = await fetch(`${API_URL}/series/?skip=${skip}&limit=${limit}`, {
    method: 'GET',
    headers: getAuthHeaders(apiKey),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(parseErrorDetail(readStringField(err, 'detail') || (isRecord(err) ? err.detail : null)) || 'Không thể tải danh sách chuỗi video.');
  }
  const data = await response.json().catch(() => ({ items: [] }));
  if (Array.isArray(data)) {
    return { items: data as SeriesResponse[], total: data.length, skip, limit };
  }
  if (isRecord(data) && Array.isArray(data.items)) {
    return {
      items: data.items as SeriesResponse[],
      total: typeof data.total === 'number' ? data.total : data.items.length,
      skip: typeof data.skip === 'number' ? data.skip : skip,
      limit: typeof data.limit === 'number' ? data.limit : limit,
    };
  }
  return { items: [], total: 0, skip, limit };
}

// Series v2 list guard: the backend returns pagination metadata, so the client
// unwraps `items` and rejects legacy array assumptions at this boundary.
export async function fetchUserSeries(apiKey: string): Promise<SeriesResponse[]> {
  const page = await fetchSeriesPage(apiKey, 0, 100);
  return page.items;
}

export async function fetchSeriesDetail(apiKey: string, seriesId: number): Promise<SeriesResponse> {
  const response = await fetch(`${API_URL}/series/${seriesId}`, {
    method: 'GET',
    headers: getAuthHeaders(apiKey),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(parseErrorDetail(readStringField(err, 'detail') || (isRecord(err) ? err.detail : null)) || 'Không thể tải thông tin chuỗi video.');
  }
  return response.json();
}

// Series v2 create guard: do not send legacy `big_idea` or `generation_mode`
// fields because the backend rejects them to keep v2 isolated from old series.
export async function createSeries(
  apiKey: string,
  data: SeriesV2CreatePayload
): Promise<SeriesResponse> {
  const response = await fetch(`${API_URL}/series/`, {
    method: 'POST',
    headers: getAuthHeaders(apiKey),
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(parseErrorDetail(readStringField(err, 'detail') || (isRecord(err) ? err.detail : null)) || 'Không thể khởi tạo chuỗi video mới.');
  }
  return response.json();
}

export async function deleteSeries(apiKey: string, seriesId: number): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_URL}/series/${seriesId}`, {
    method: 'DELETE',
    headers: getAuthHeaders(apiKey),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(parseErrorDetail(readStringField(err, 'detail') || (isRecord(err) ? err.detail : null)) || 'Không thể xóa chuỗi video.');
  }
  return response.json();
}

export async function fetchEpisodes(apiKey: string, seriesId: number): Promise<EpisodeResponse[]> {
  const response = await fetch(`${API_URL}/series/${seriesId}/episodes`, {
    method: 'GET',
    headers: getAuthHeaders(apiKey),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(parseErrorDetail(readStringField(err, 'detail') || (isRecord(err) ? err.detail : null)) || 'Không thể tải danh sách tập phim.');
  }
  const data = await response.json().catch(() => []);
  return Array.isArray(data) ? data : [];
}

// Brief gate guard: v2 prepares one deterministic editable brief before any
// episode generation call, replacing legacy paid suggestion generation.
export async function fetchEpisodeBrief(apiKey: string, seriesId: number, episodeNumber: number): Promise<EpisodeResponse> {
  const response = await fetch(`${API_URL}/series/${seriesId}/episodes/${episodeNumber}/brief`, {
    method: 'GET',
    headers: getAuthHeaders(apiKey),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(parseErrorDetail(readStringField(err, 'detail') || (isRecord(err) ? err.detail : null)) || 'Không thể tải brief tập phim.');
  }
  return response.json();
}

// Brief update guard: only the public editable fields are sent, preventing
// frontend state from mutating generated artifacts or phase logs.
export async function updateEpisodeBrief(
  apiKey: string,
  seriesId: number,
  episodeNumber: number,
  data: EpisodeBriefUpdatePayload
): Promise<EpisodeResponse> {
  const response = await fetch(`${API_URL}/series/${seriesId}/episodes/${episodeNumber}/brief`, {
    method: 'PUT',
    headers: getAuthHeaders(apiKey),
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(parseErrorDetail(readStringField(err, 'detail') || (isRecord(err) ? err.detail : null)) || 'Không thể lưu brief tập phim.');
  }
  return response.json();
}

// Brief-candidate guard: this endpoint returns deterministic v2 candidates
// that include brief edits; it is not the old LLM suggestion branch.
export async function generateEpisodeSuggestions(
  apiKey: string,
  seriesId: number,
  episodeNumber: number
): Promise<{ success: boolean; suggestions: SeriesBriefCandidate[]; error?: string }> {
  const response = await fetch(`${API_URL}/series/${seriesId}/episodes/${episodeNumber}/suggestions`, {
    method: 'POST',
    headers: getAuthHeaders(apiKey),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(parseErrorDetail(readStringField(err, 'detail') || (isRecord(err) ? err.detail : null)) || 'Lỗi sinh gợi ý tập phim.');
  }
  return response.json();
}

// Stream request guard: v2 generation starts from the accepted brief and passes
// model/review options in the body instead of legacy query-string suggestion ids.
export async function generateEpisodeScript(
  apiKey: string,
  seriesId: number,
  episodeNumber: number,
  modelName: string,
  options: { run_reviewer?: boolean; run_packaging?: boolean; restart?: boolean } = {}
): Promise<Response> {
  const response = await fetch(
    `${API_URL}/series/${seriesId}/episodes/${episodeNumber}/generate`,
    {
      method: 'POST',
      headers: getAuthHeaders(apiKey),
      body: JSON.stringify({
        model_name: modelName,
        run_reviewer: options.run_reviewer ?? true,
        run_packaging: options.run_packaging ?? false,
        restart: options.restart ?? false,
      }),
    }
  );
  return response;
}
