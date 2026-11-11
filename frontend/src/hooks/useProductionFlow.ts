import { useState, useCallback, useRef } from 'react';
import {
  API_URL,
  getAuthHeaders,
  generateSuggestions,
  getProject,
  getErrorMessage,
} from '../services/api';
import type {
  ScriptSuggestion,
  ScriptOutput,
  GenerateSuggestionsRequest,
  SceneScript,
  EmotionArcEntry
} from '../services/api';

type StreamPayload = {
  status?: string;
  group?: string;
  step?: string;
  message?: string;
  data?: Partial<ScriptOutput> | EmotionArcEntry[] | SceneScript;
};

type PresetStyle = 'anime' | 'realistic' | 'cinematic' | 'cartoon';
type GenerationMode = 'single' | 'longform' | 'series_short' | 'series_long';
type ScriptGenerationOptions = { restart?: boolean };

const DEFAULT_PRESET_STYLE: PresetStyle = 'anime';
const DEFAULT_ASPECT_RATIO = '16:9';
const DEFAULT_SCENE_DURATION = 8;

const activeScriptGenerationKeys = new Set<string>();

function isPresetStyle(value: string): value is PresetStyle {
  return ['anime', 'realistic', 'cinematic', 'cartoon'].includes(value);
}

function readErrorName(err: unknown): string {
  if (typeof err !== 'object' || err === null) return '';
  const value = (err as { name?: unknown }).name;
  return typeof value === 'string' ? value : '';
}

function getStreamErrorMessage(err: unknown): string {
  const name = readErrorName(err);
  const message = getErrorMessage(err, '');
  if (name === 'AbortError') {
    return 'Đã hủy luồng sinh kịch bản.';
  }
  if (err instanceof TypeError && /network|failed to fetch|load failed/i.test(message)) {
    return 'Stream SSE bị cắt giữa chừng. Backend có thể vừa lỗi nội bộ hoặc kết nối stream bị đóng trước khi hoàn tất.';
  }
  return message || 'Lỗi kết nối khi sinh kịch bản.';
}

// Single-mode routing guard: the V2 UI hides the short/long switch, while the
// backend still needs the legacy mode label for resume signatures and history.
function deriveSingleGenerationMode(numScenes: number): Extract<GenerationMode, 'single' | 'longform'> {
  return numScenes > 20 ? 'longform' : 'single';
}

// Default-scene guard: fresh Single resets should honor the saved duration
// preference while staying deterministic when localStorage is unavailable.
function getInitialNumScenes() {
  try {
    const savedDuration = localStorage.getItem('DEFAULT_DURATION') || '05:00';
    const parts = savedDuration.split(':');
    if (parts.length === 2) {
      const totalSec = parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
      const options = [4, 6, 8, 10, 12, 15, 20];
      const calculated = Math.ceil(totalSec / 8);
      return options.reduce((prev, curr) =>
        Math.abs(curr - calculated) < Math.abs(prev - calculated) ? curr : prev
      );
    }
  } catch {
    // fallback
  }
  return 8;
}

export function useProductionFlow() {
  // Input State
  const [inputType, setInputType] = useState<'topic' | 'manual' | 'youtube_url'>('manual');
  const [inputContent, setInputContent] = useState<string>('');
  const [selectedTopicId, setSelectedTopicId] = useState<number | null>(null);
  const [presetStyle, setPresetStyle] = useState<PresetStyle>(DEFAULT_PRESET_STYLE);
  const [customStyle, setCustomStyle] = useState<string>('');
  const [numScenes, setNumScenes] = useState<number>(getInitialNumScenes);
  const [aspectRatio, setAspectRatio] = useState<'16:9' | '9:16'>(DEFAULT_ASPECT_RATIO);
  const [sceneDuration, setSceneDuration] = useState<number>(DEFAULT_SCENE_DURATION);
  const [generationMode, setGenerationMode] = useState<GenerationMode>('single');
  const [episodeDurationMinutes, setEpisodeDurationMinutes] = useState<number | null>(null);
  const [numEpisodes, setNumEpisodes] = useState<number>(5);
  const [resetRevision, setResetRevision] = useState<number>(0);

  // Workflow State
  const [projectId, setProjectId] = useState<number | null>(null);
  const [suggestions, setSuggestions] = useState<ScriptSuggestion[]>([]);
  const [selectedSuggestionIdx, setSelectedSuggestionIdx] = useState<number | null>(null);
  const [scriptOutput, setScriptOutput] = useState<ScriptOutput | null>(null);
  const [emotionArc, setEmotionArc] = useState<EmotionArcEntry[]>([]);
  const [status, setStatus] = useState<string>('draft');
  const [topicTypeOverride, setTopicTypeOverride] = useState<'historical' | 'scientific' | 'fictional_mythology' | 'fictional_original' | null>(null);

  // Loading & Error States
  const [loadingSuggestions, setLoadingSuggestions] = useState<boolean>(false);
  const [suggestionsError, setSuggestionsError] = useState<string | null>(null);
  const [generatingScript, setGeneratingScript] = useState<boolean>(false);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [streamProgress, setStreamProgress] = useState<{ group: string; step: string; percent: number }>({
    group: 'idle',
    step: 'Chưa bắt đầu',
    percent: 0,
  });
  const generationInFlightRef = useRef<boolean>(false);
  const streamAbortControllerRef = useRef<AbortController | null>(null);
  // Suggestion request guard: sidebar/init resets must invalidate in-flight
  // suggestion responses so old results cannot reopen phase 2 after navigation.
  const suggestionsRequestSeqRef = useRef<number>(0);

  // Load / Restore project history
  const handleLoadProject = useCallback(async (apiKey: string, id: number) => {
    try {
      const data = await getProject(apiKey, id);
      setProjectId(data.id);
      setInputType(data.input_type);
      setInputContent(data.input_content || '');
      setSelectedTopicId(data.topic_id);
      
      // Parse style
      if (isPresetStyle(data.style)) {
        setPresetStyle(data.style);
        setCustomStyle('');
      } else {
        setCustomStyle(data.style);
      }

      setNumScenes(data.num_scenes);
      setSceneDuration(data.scene_duration || 8);
      setAspectRatio('16:9');
      setStatus(data.status);
      setSuggestions(data.suggestions || []);
      setSelectedSuggestionIdx(data.selected_suggestion_idx ?? null);
      setScriptOutput(data.script_output ?? null);
      setEmotionArc(data.script_output?.emotion_arc || []);
      setTopicTypeOverride(data.topic_type || null);
      if (data.generation_mode) {
        setGenerationMode(data.generation_mode);
      }
    } catch (err: unknown) {
      console.error('Error loading project details:', err);
      throw err;
    }
  }, []);

  // Single-flow reset guard: reset returns to manual intake so legacy
  // topic/YouTube restores cannot leak into new project creation.
  // Default-state guard: sidebar Video đơn now means a fresh blank workflow, not
  // merely returning to the intake phase with the old idea still present.
  const handleReset = useCallback(() => {
    suggestionsRequestSeqRef.current += 1;
    streamAbortControllerRef.current?.abort();
    streamAbortControllerRef.current = null;
    generationInFlightRef.current = false;
    activeScriptGenerationKeys.clear();
    setProjectId(null);
    setInputType('manual');
    setInputContent('');
    setSelectedTopicId(null);
    setPresetStyle(DEFAULT_PRESET_STYLE);
    setCustomStyle('');
    setNumScenes(getInitialNumScenes());
    setAspectRatio(DEFAULT_ASPECT_RATIO);
    setSceneDuration(DEFAULT_SCENE_DURATION);
    setSuggestions([]);
    setSelectedSuggestionIdx(null);
    setScriptOutput(null);
    setEmotionArc([]);
    setStatus('draft');
    setLoadingSuggestions(false);
    setSuggestionsError(null);
    setGeneratingScript(false);
    setGenerationError(null);
    setStreamProgress({ group: 'idle', step: 'Chưa bắt đầu', percent: 0 });
    setTopicTypeOverride(null);
    setGenerationMode('single');
    setEpisodeDurationMinutes(null);
    setResetRevision((value) => value + 1);
  }, []);

  // Single-phase rewind guard: returning from suggestion review should preserve
  // the current idea/config while removing the transient project and output.
  const handleReturnToSingleIntake = useCallback(() => {
    suggestionsRequestSeqRef.current += 1;
    streamAbortControllerRef.current?.abort();
    streamAbortControllerRef.current = null;
    generationInFlightRef.current = false;
    activeScriptGenerationKeys.clear();
    setProjectId(null);
    setSuggestions([]);
    setSelectedSuggestionIdx(null);
    setScriptOutput(null);
    setEmotionArc([]);
    setStatus('draft');
    setLoadingSuggestions(false);
    setSuggestionsError(null);
    setGeneratingScript(false);
    setGenerationError(null);
    setStreamProgress({ group: 'idle', step: 'Chưa bắt đầu', percent: 0 });
    setTopicTypeOverride(null);
    setGenerationMode(deriveSingleGenerationMode(numScenes));
  }, [numScenes]);

  // Step 1: Generate Suggestions
  // Single-flow payload guard: new projects are always manual ideas; longform is
  // inferred from scene count instead of exposed as a separate user mode.
  // In-flight response guard: each run owns a sequence id so sidebar navigation
  // back to init cannot be overwritten by an older async response.
  const handleGenerateSuggestions = useCallback(async (apiKey: string, modelName: string) => {
    if (!apiKey.trim()) return;
    const requestSeq = suggestionsRequestSeqRef.current + 1;
    suggestionsRequestSeqRef.current = requestSeq;
    setLoadingSuggestions(true);
    setSuggestionsError(null);
    setSuggestions([]);
    setProjectId(null);
    setInputType('manual');
    setSelectedTopicId(null);
    const derivedGenerationMode = deriveSingleGenerationMode(numScenes);
    setGenerationMode(derivedGenerationMode);
    
    const requestPayload: GenerateSuggestionsRequest = {
      input_type: 'manual',
      input_content: inputContent,
      topic_id: null,
      style: {
        preset: customStyle.trim() ? null : presetStyle,
        custom: customStyle.trim() ? customStyle : null,
      },
      num_scenes: numScenes,
      num_suggestions: 5,
      model_name: modelName,
      generation_mode: derivedGenerationMode,
      scene_duration_sec: sceneDuration,
    };

    try {
      const response = await generateSuggestions(apiKey, requestPayload);
      if (requestSeq !== suggestionsRequestSeqRef.current) return;
      if (response.success) {
        setProjectId(response.project_id);
        setSuggestions(response.suggestions || []);
        setStatus('suggestions_generated');
      } else {
        throw new Error(response.error || 'Sinh gợi ý kịch bản thất bại.');
      }
    } catch (err: unknown) {
      if (requestSeq !== suggestionsRequestSeqRef.current) return;
      console.error(err);
      setSuggestionsError(getErrorMessage(err, 'Lỗi hệ thống khi sinh gợi ý kịch bản.'));
    } finally {
      if (requestSeq === suggestionsRequestSeqRef.current) {
        setLoadingSuggestions(false);
      }
    }
  }, [inputContent, presetStyle, customStyle, numScenes, sceneDuration]);

  // Step 2: Select a Suggestion card
  const handleSelectSuggestion = useCallback((idx: number) => {
    setSelectedSuggestionIdx(idx);
  }, []);

  // Step 3: Stream script generation (SSE)
  // Recovery guard: retry resumes persisted phase cache; restart clears local
  // output and tells the backend to ignore saved partial artifacts.
  const handleStartScriptGeneration = useCallback(async (apiKey: string, modelName: string, options: ScriptGenerationOptions = {}) => {
    if (!apiKey.trim()) {
      setGenerationError("Không tìm thấy App API Key. Vui lòng cấu hình ở Cài đặt.");
      return;
    }
    if (projectId === null) {
      setGenerationError("Dự án chưa được tạo hoặc chưa chọn gợi ý.");
      return;
    }
    if (selectedSuggestionIdx === null) {
      setGenerationError("Vui lòng chọn 1 kịch bản gợi ý trước khi tiếp tục.");
      return;
    }

    const generationKey = `${projectId}:${selectedSuggestionIdx}`;
    if (generationInFlightRef.current || activeScriptGenerationKeys.has(generationKey)) {
      return;
    }

    activeScriptGenerationKeys.add(generationKey);
    generationInFlightRef.current = true;
    const abortController = new AbortController();
    streamAbortControllerRef.current = abortController;
    setGeneratingScript(true);
    setGenerationError(null);
    setStatus('generating_script');
    setStreamProgress({ group: 'metadata', step: 'Bắt đầu khởi tạo kết nối...', percent: 5 });
    if (options.restart) {
      setEmotionArc([]);
      setScriptOutput(null);
    }

    const emptyScript: ScriptOutput = {
      overview_analysis_vi: '',
      storyline_vi: '',
      stages_vi: '',
      progression_vi: '',
      camera_strategy_vi: '',
      continuity_locks_vi: '',
      form_locks_vi: '',
      age_stage_locks_vi: '',
      geometry_locks_vi: '',
      risk_logic_vi: '',
      characters: [],
      environment_master_prompt_en: '',
      emotion_arc: [],
      scenes: [],
      continuity_prompt_en: '',
      global_negative_prompt_en: '',
      reference_images: {
        character_ref_prompt_en: '',
        background_ref_prompt_en: '',
        thumbnail_ref_prompt_en: '',
      },
    };

    let tempScript: ScriptOutput = emptyScript;
    let sawDone = false;

    try {
      const latestProject = options.restart ? null : await getProject(apiKey, projectId);
      if (latestProject?.script_output) {
        const cached = latestProject.script_output;
        tempScript = {
          ...emptyScript,
          ...cached,
          emotion_arc: cached.emotion_arc || [],
          scenes: cached.scenes || [],
          reference_images: {
            ...emptyScript.reference_images,
            ...(cached.reference_images || {}),
          },
        };
        setEmotionArc(tempScript.emotion_arc || []);
        setScriptOutput({ ...tempScript });
        const cachedScenes = tempScript.scenes.length;
        if (cachedScenes > 0) {
          setStreamProgress({
            group: 'scenes',
            step: `resume_cache_${cachedScenes}_scenes`,
            percent: Math.min(85, 15 + Math.round((cachedScenes / numScenes) * 70)),
          });
        }
      } else {
        setEmotionArc([]);
        setScriptOutput(tempScript);
      }
    } catch (preloadErr: unknown) {
      console.warn('Could not preload cached script before streaming:', preloadErr);
      setEmotionArc([]);
      setScriptOutput(tempScript);
    }

    try {
      const response = await fetch(`${API_URL}/production/script/generate`, {
        method: 'POST',
        headers: getAuthHeaders(apiKey),
        signal: abortController.signal,
        body: JSON.stringify({
          project_id: projectId,
          suggestion_index: selectedSuggestionIdx,
          model_name: modelName,
          topic_type_override: topicTypeOverride,
          aspect_ratio: aspectRatio,
          scene_duration_sec: sceneDuration,
          restart: options.restart ?? false,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Lỗi kết nối server (${response.status})`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Trình duyệt không hỗ trợ đọc Stream Body.');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith('data: ')) continue;

          const dataStr = trimmed.slice(6);
          if (!dataStr) continue;

          let payload: StreamPayload;
          try {
            payload = JSON.parse(dataStr) as StreamPayload;
          } catch (jsonErr: unknown) {
            console.error('Error parsing streaming event:', jsonErr);
            continue;
          }

          // Xử lý các sự kiện trả về từ stream SSE
          if (payload.status === 'generating') {
            const stepName = payload.step || '';
            const groupName = payload.group || '';
            let progressPercent = 10;
            
            if (groupName === 'scenes') {
              // Tiến trình từ 15% -> 85%
              const currentSceneNum = parseInt(stepName.replace('scene_', ''), 10) || 1;
              progressPercent = 15 + Math.round((currentSceneNum / numScenes) * 70);
            } else if (groupName === 'global') {
              progressPercent = 90;
            }

            setStreamProgress({
              group: groupName,
              step: stepName,
              percent: progressPercent,
            });
          } else if (payload.status === 'metadata') {
            tempScript = {
              ...tempScript,
              overview_analysis_vi: (payload.data as Partial<ScriptOutput>)?.overview_analysis_vi || '',
              storyline_vi: (payload.data as Partial<ScriptOutput>)?.storyline_vi || '',
              stages_vi: (payload.data as Partial<ScriptOutput>)?.stages_vi || '',
              progression_vi: (payload.data as Partial<ScriptOutput>)?.progression_vi || '',
              camera_strategy_vi: (payload.data as Partial<ScriptOutput>)?.camera_strategy_vi || '',
              continuity_locks_vi: (payload.data as Partial<ScriptOutput>)?.continuity_locks_vi || '',
              form_locks_vi: (payload.data as Partial<ScriptOutput>)?.form_locks_vi || '',
              age_stage_locks_vi: (payload.data as Partial<ScriptOutput>)?.age_stage_locks_vi || '',
              geometry_locks_vi: (payload.data as Partial<ScriptOutput>)?.geometry_locks_vi || '',
              risk_logic_vi: (payload.data as Partial<ScriptOutput>)?.risk_logic_vi || '',
              characters: (payload.data as Partial<ScriptOutput>)?.characters || [],
              environment_master_prompt_en: (payload.data as Partial<ScriptOutput>)?.environment_master_prompt_en || '',
            };
            setScriptOutput({ ...tempScript });
          } else if (payload.status === 'emotion_arc') {
            const arc = Array.isArray(payload.data) ? payload.data as EmotionArcEntry[] : [];
            setEmotionArc(arc);
            tempScript = {
              ...tempScript,
              emotion_arc: arc,
            };
            setScriptOutput({ ...tempScript });
          } else if (payload.status === 'scene') {
            const newScene = payload.data as SceneScript;
            // Tránh trùng lắp scene đã có
            const updatedScenes = tempScript.scenes.filter((s: SceneScript) => s.scene_number !== newScene.scene_number);
            updatedScenes.push(newScene);
            updatedScenes.sort((a: SceneScript, b: SceneScript) => a.scene_number - b.scene_number);
            
            tempScript = {
              ...tempScript,
              scenes: updatedScenes,
            };
            setScriptOutput({ ...tempScript });
          } else if (payload.status === 'global') {
            tempScript = {
              ...tempScript,
              continuity_prompt_en: (payload.data as Partial<ScriptOutput>)?.continuity_prompt_en || '',
              global_negative_prompt_en: (payload.data as Partial<ScriptOutput>)?.global_negative_prompt_en || '',
              reference_images: (payload.data as Partial<ScriptOutput>)?.reference_images || tempScript.reference_images,
              prompt_0: (payload.data as Partial<ScriptOutput>)?.prompt_0 || tempScript.prompt_0,
            };
            setScriptOutput({ ...tempScript });
          } else if (payload.status === 'done') {
            sawDone = true;
            setStreamProgress({
              group: 'done',
              step: 'Hoàn tất sinh kịch bản chi tiết!',
              percent: 100,
            });
            setStatus('script_generated');
            setGeneratingScript(false);
          } else if (payload.status === 'error') {
            throw new Error(payload.message || 'Lỗi không xác định khi stream kịch bản.');
          }
        }
      }

      if (!sawDone) {
        throw new Error('Stream SSE đóng trước khi backend gửi tín hiệu hoàn tất.');
      }
    } catch (err: unknown) {
      console.error(err);
      if (readErrorName(err) !== 'AbortError') {
        setGenerationError(getStreamErrorMessage(err));
        setStatus('script_failed');
      }
    } finally {
      if (streamAbortControllerRef.current === abortController) {
        streamAbortControllerRef.current = null;
      }
      generationInFlightRef.current = false;
      activeScriptGenerationKeys.delete(generationKey);
      setGeneratingScript(false);
    }
  }, [projectId, selectedSuggestionIdx, numScenes, topicTypeOverride, aspectRatio, sceneDuration]);

  return {
    // Input config states & setters
    inputType,
    setInputType,
    inputContent,
    setInputContent,
    selectedTopicId,
    setSelectedTopicId,
    presetStyle,
    setPresetStyle,
    customStyle,
    setCustomStyle,
    numScenes,
    setNumScenes,
    generationMode,
    setGenerationMode,
    episodeDurationMinutes,
    setEpisodeDurationMinutes,
    numEpisodes,
    setNumEpisodes,

    // Status states
    projectId,
    suggestions,
    selectedSuggestionIdx,
    scriptOutput,
    emotionArc,
    status,
    loadingSuggestions,
    suggestionsError,
    generatingScript,
    generationError,
    streamProgress,
    topicTypeOverride,
    resetRevision,
    setTopicTypeOverride,
    aspectRatio,
    setAspectRatio,
    sceneDuration,
    setSceneDuration,

    // Actions
    handleLoadProject,
    handleReset,
    handleGenerateSuggestions,
    handleSelectSuggestion,
    handleReturnToSingleIntake,
    handleStartScriptGeneration,
  };
}
