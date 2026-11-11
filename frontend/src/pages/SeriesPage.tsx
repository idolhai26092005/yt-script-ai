import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  createSeries,
  deleteSeries,
  fetchEpisodeBrief,
  fetchEpisodes,
  fetchSeriesDetail,
  generateEpisodeScript,
  generateEpisodeSuggestions,
  getErrorMessage,
  updateEpisodeBrief,
  type EpisodeBriefUpdatePayload,
  type EpisodeResponse,
  type SeriesBriefCandidate,
  type SeriesEndingMode,
  type SeriesResponse,
  type SeriesScene,
  type SeriesScriptOutput,
  type SeriesStreamEvent,
  type SeriesTopicType,
  type SeriesV2CreatePayload,
} from '../services/api';

interface SeriesPageProps {
  apiKey: string;
  modelName: string;
  initialSeriesId?: number | null;
  onNavigateToHistory?: () => void;
}

type PresetStyle = 'anime' | 'realistic' | 'cinematic' | 'cartoon';
type StyleChoice = PresetStyle | 'custom';
type SeriesPhase = 1 | 2 | 3;
type EpisodeStage = 'brief' | 'output';
type SeriesGenerationOptions = { restart?: boolean };

type BriefDraft = {
  title: string;
  premise: string;
  mustInclude: string;
  mustAvoid: string;
  sceneCount: number;
  endingMode: SeriesEndingMode;
  notes: string;
};

type SeriesIntakeDraft = {
  title: string;
  premise: string;
  styleChoice: StyleChoice;
  customStyle: string;
  topicType: SeriesTopicType;
  targetEpisodeCount: number;
  defaultSceneCount: number;
  sceneDurationSec: number;
};

type StreamProgress = {
  phase: string;
  label: string;
  percent: number;
  scenesDone: number;
  scenesTotal: number;
};

type ArtifactTab = 'continuity' | 'review' | 'phase_log';

const EMPTY_PROGRESS: StreamProgress = {
  phase: 'idle',
  label: 'Chưa bắt đầu',
  percent: 0,
  scenesDone: 0,
  scenesTotal: 0,
};

const DEFAULT_INTAKE: SeriesIntakeDraft = {
  title: '',
  premise: '',
  styleChoice: 'anime',
  customStyle: '',
  topicType: 'fictional_original',
  targetEpisodeCount: 5,
  defaultSceneCount: 8,
  sceneDurationSec: 8,
};

const ENDING_OPTIONS: { value: SeriesEndingMode; label: string }[] = [
  { value: 'open_loop', label: 'Open loop' },
  { value: 'soft_cliffhanger', label: 'Soft cliffhanger' },
  { value: 'hard_cliffhanger', label: 'Hard cliffhanger' },
  { value: 'season_finale', label: 'Season finale' },
];

const STYLE_OPTIONS: Array<{ value: StyleChoice; label: string }> = [
  { value: 'anime', label: 'Anime' },
  { value: 'realistic', label: 'Realistic' },
  { value: 'cinematic', label: 'Cinematic' },
  { value: 'cartoon', label: 'Cartoon 3D' },
  { value: 'custom', label: 'Tùy chọn' },
];

const TOPIC_TYPE_OPTIONS: Array<{ value: SeriesTopicType; label: string }> = [
  { value: 'fictional_original', label: 'Sáng tác gốc' },
  { value: 'fictional_mythology', label: 'Thần thoại' },
  { value: 'scientific', label: 'Khoa học' },
  { value: 'historical', label: 'Lịch sử' },
];

const EPISODE_OPTIONS = [2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 30];
const SCENE_OPTIONS = [4, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 80, 100, 120, 150, 200];
const DURATION_OPTIONS = [4, 6, 8, 10, 12];
const SERIES_STEPS: Array<{ id: SeriesPhase; label: string; detail: string }> = [
  { id: 1, label: 'Khởi tạo chuỗi', detail: 'Ý tưởng + cấu hình' },
  { id: 2, label: 'Sinh brief', detail: 'Brief trước' },
  { id: 3, label: 'Sinh tập & output', detail: 'Cảnh, review, continuity' },
];

// Text safety guard: series artifacts are model-shaped JSON, so UI rendering
// keeps unknown values readable without assuming a single backend prompt schema.
function textValue(value: unknown, fallback = ''): string {
  return typeof value === 'string' && value.trim() ? value : fallback;
}

// List editing guard: textarea rows map to array fields in the v2 brief update
// contract, avoiding hidden comma parsing and keeping Vietnamese prose intact.
function linesToList(value: string): string[] {
  return value
    .split('\n')
    .map(item => item.trim())
    .filter(Boolean);
}

// Brief draft guard: every pending episode edits only the public brief surface
// and preserves deterministic defaults produced by the backend.
function draftFromEpisode(episode: EpisodeResponse | null): BriefDraft {
  const brief = episode?.brief || {};
  return {
    title: textValue(brief.title, episode?.title || `Tap ${episode?.episode_number || 1}`),
    premise: textValue(brief.premise),
    mustInclude: Array.isArray(brief.must_include) ? brief.must_include.join('\n') : '',
    mustAvoid: Array.isArray(brief.must_avoid) ? brief.must_avoid.join('\n') : '',
    sceneCount: Number(brief.scene_count || episode?.scene_count || 8),
    endingMode: (brief.ending_mode || episode?.ending_mode || 'open_loop') as SeriesEndingMode,
    notes: textValue(brief.notes),
  };
}

// Candidate guard: deterministic backend candidates patch the same editable
// brief fields, so applying one never mutates generated artifacts.
function draftFromCandidate(candidate: SeriesBriefCandidate, fallback: BriefDraft): BriefDraft {
  return {
    title: candidate.brief.title || candidate.title || fallback.title,
    premise: candidate.brief.premise || candidate.synopsis || fallback.premise,
    mustInclude: (candidate.brief.must_include || linesToList(fallback.mustInclude)).join('\n'),
    mustAvoid: (candidate.brief.must_avoid || linesToList(fallback.mustAvoid)).join('\n'),
    sceneCount: Number(candidate.brief.scene_count || fallback.sceneCount),
    endingMode: (candidate.brief.ending_mode || fallback.endingMode) as SeriesEndingMode,
    notes: candidate.brief.notes || fallback.notes,
  };
}

// Payload guard: the backend owns schema validation; the client sends a compact
// explicit payload rather than reflecting the whole draft object.
function briefPayloadFromDraft(draft: BriefDraft): EpisodeBriefUpdatePayload {
  return {
    title: draft.title.trim(),
    premise: draft.premise.trim(),
    must_include: linesToList(draft.mustInclude),
    must_avoid: linesToList(draft.mustAvoid),
    scene_count: draft.sceneCount,
    ending_mode: draft.endingMode,
    notes: draft.notes.trim(),
  };
}

// Series-title guard: intake may omit a title, so derive a stable readable name
// from the premise without inventing content or storing a style placeholder.
function deriveTitleFromPremise(premise: string): string {
  const clean = premise.trim().split(/\s+/).join(' ');
  if (!clean) return 'Chuỗi video mới';
  const firstSentence = clean.split(/[.!?。！？]/)[0]?.trim() || clean;
  return firstSentence.length > 82 ? `${firstSentence.slice(0, 79).trim()}...` : firstSentence;
}

// Phase copy guard: v2 phase names are transport-level identifiers, while the
// dashboard needs short operator-facing labels.
function phaseLabel(phase?: string | null): string {
  switch (phase) {
    case 'episode_planning':
      return 'Lập blueprint và cảm xúc arc';
    case 'episode_scenes':
      return 'Sinh cảnh theo lật';
    case 'continuity_review':
      return 'Review continuity';
    case 'fact_check':
      return 'Fact-check';
    case 'continuity_delta':
      return 'Đóng gói handoff';
    case 'final_persist':
      return 'Lưu kết quả';
    default:
      return phase || 'Đang xử lý';
  }
}

// Progress guard: phase estimates are visual feedback only; completion truth
// still comes from the backend `done` event and refreshed episode state.
function estimateProgress(event: SeriesStreamEvent, current: StreamProgress, totalScenes: number): StreamProgress {
  if (event.status === 'scene') {
    const scenesDone = Math.min(current.scenesDone + 1, totalScenes || current.scenesTotal || 1);
    const scenesTotal = totalScenes || current.scenesTotal || scenesDone;
    return {
      phase: event.phase || 'episode_scenes',
      label: `Đã nhận ${scenesDone}/${scenesTotal} cảnh`,
      scenesDone,
      scenesTotal,
      percent: Math.min(88, 28 + Math.round((scenesDone / scenesTotal) * 55)),
    };
  }

  if (event.status === 'review') {
    return { ...current, phase: event.phase || 'continuity_review', label: phaseLabel(event.phase), percent: Math.max(current.percent, 88) };
  }

  if (event.status === 'done') {
    return { ...current, phase: event.phase || 'final_persist', label: 'Hoàn tất', percent: 100 };
  }

  const phase = event.phase || current.phase;
  const baseline = phase === 'episode_planning' ? 18 : phase === 'episode_scenes' ? 28 : phase === 'fact_check' ? 82 : 72;
  return {
    ...current,
    phase,
    label: event.message || phaseLabel(phase),
    scenesTotal: totalScenes || current.scenesTotal,
    percent: Math.max(current.percent, baseline),
  };
}

// Status visual guard: all episode states have a text label plus shape/color so
// status is not conveyed by color alone.
function statusMeta(status: string): { label: string; className: string } {
  switch (status) {
    case 'completed':
      return { label: 'Hoàn thành', className: 'series-status series-status--done' };
    case 'needs_review':
      return { label: 'Cần review', className: 'series-status series-status--review' };
    case 'generating':
      return { label: 'Đang sinh / tiếp tục', className: 'series-status series-status--active' };
    case 'failed':
      return { label: 'Lỗi, có thể sinh lại', className: 'series-status series-status--error' };
    default:
      return { label: 'Chờ brief', className: 'series-status' };
  }
}

// JSON summary guard: dense artifacts get a small stable excerpt first and keep
// the full JSON available through copy/export actions.
function artifactSummary(value: unknown): string {
  if (!value) return 'Chưa có dữ liệu.';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function recordValue(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function nullableString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null;
}

function listValue(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

// Prompt-pack guard: the single copy action exports only prompt/voice material
// needed for video assembly, never review reports or heavy continuity artifacts.
function buildSeriesPromptPackJson(
  series: SeriesResponse | null,
  episode: EpisodeResponse | null,
  output: SeriesScriptOutput | null,
  scenes: SeriesScene[],
): string {
  const seriesBible = recordValue(series?.series_bible);
  const episodeBlueprint = recordValue(output?.episode_blueprint || episode?.episode_blueprint);
  const brief = episode?.brief || null;
  const pack = {
    schema_version: 'series.prompt_pack.v1',
    episode_number: output?.episode_number || episode?.episode_number || brief?.episode_number || null,
    title: output?.title || episode?.title || brief?.title || null,
    prompt_0: {
      series_visual_anchor: stringValue(seriesBible.visual_anchor),
      world_rules: listValue(seriesBible.world_rules),
      cast_locks: listValue(seriesBible.cast_locks),
      style_tone: stringValue(seriesBible.style_tone),
      central_conflict: stringValue(seriesBible.central_conflict),
      visual_constraints: listValue(episodeBlueprint.visual_constraints),
      audio_constraints: listValue(episodeBlueprint.audio_constraints),
      prompt_0_extension: stringValue(episodeBlueprint.prompt_0_extension),
      episode_title: brief?.title || null,
      episode_premise: brief?.premise || null,
      must_include: brief?.must_include || [],
      must_avoid: brief?.must_avoid || [],
    },
    scenes: scenes.map((scene, index) => ({
      scene_number: scene.scene_number || index + 1,
      title: scene.title || null,
      veo3_prompt_en: nullableString(scene.veo3_prompt_en),
      veo3_prompt_vi: nullableString(scene.veo3_prompt_vi),
      negative_prompt_en: nullableString(scene.negative_prompt_en),
      scene_specific_negative_en: nullableString(scene.scene_specific_negative_en),
      voice_over_en: nullableString(scene.voice_over_en),
      voice_over_vi: nullableString(scene.voice_over_vi),
    })),
  };

  return JSON.stringify(pack, null, 2);
}

// Stepper guard: Series mirrors Single's three-stage rhythm while keeping
// generation output on the same tab for continuity work.
// Stage split guard: episode work now separates brief preparation from output
// review, so generated episodes can reopen directly to their readable output.
function deriveSeriesPhase(hasSeries: boolean, episodeStage: EpisodeStage, generating: boolean): SeriesPhase {
  if (!hasSeries) return 1;
  if (episodeStage === 'output' || generating) return 3;
  return 2;
}

// Output preview guard: the scene navigator needs a short stable summary while
// the selected detail panel keeps the full action and prompt text available.
function scenePreview(scene: SeriesScene): string {
  return scene.action_detail_vi || scene.voice_over_vi || scene.veo3_prompt_en || 'Chưa có mô tả cảnh.';
}

// Timeline guard: users can inspect generated episodes plus only the next
// unsolved episode, preventing accidental skips in a continuity-bound series.
function canOpenEpisode(episodeNumber: number, episodes: EpisodeResponse[], targetCount: number): boolean {
  const generatedNumbers = episodes
    .filter(ep => ['completed', 'needs_review', 'generating', 'failed'].includes(ep.status))
    .map(ep => ep.episode_number);
  const highestGenerated = generatedNumbers.length ? Math.max(...generatedNumbers) : 0;
  const allowedMax = Math.min(targetCount, Math.max(1, highestGenerated + 1));
  return episodeNumber <= allowedMax;
}

// Series workbench guard: the tab owns creation and selected-series editing,
// while opening older series still flows through unified History.
export function SeriesPage({ apiKey, modelName, initialSeriesId, onNavigateToHistory }: SeriesPageProps) {
  const [selectedSeriesId, setSelectedSeriesId] = useState<number | null>(null);
  const [selectedSeries, setSelectedSeries] = useState<SeriesResponse | null>(null);
  const [episodes, setEpisodes] = useState<EpisodeResponse[]>([]);
  const [activeEpisode, setActiveEpisode] = useState<EpisodeResponse | null>(null);
  const [briefDraft, setBriefDraft] = useState<BriefDraft>(() => draftFromEpisode(null));
  const [intakeDraft, setIntakeDraft] = useState<SeriesIntakeDraft>(DEFAULT_INTAKE);
  const [intakeError, setIntakeError] = useState<string | null>(null);
  const [intakeSuccess, setIntakeSuccess] = useState<string | null>(null);
  const [creatingSeries, setCreatingSeries] = useState(false);
  const [scriptOutput, setScriptOutput] = useState<SeriesScriptOutput | null>(null);
  const [streamScenes, setStreamScenes] = useState<SeriesScene[]>([]);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [progress, setProgress] = useState<StreamProgress>(EMPTY_PROGRESS);
  const [artifactTab, setArtifactTab] = useState<ArtifactTab>('continuity');
  const [episodeStage, setEpisodeStage] = useState<EpisodeStage>('brief');
  const [briefReady, setBriefReady] = useState(false);
  const [selectedSceneIdx, setSelectedSceneIdx] = useState(0);

  const [loadingDetail, setLoadingDetail] = useState(false);
  const [loadingBrief, setLoadingBrief] = useState(false);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [savingBrief, setSavingBrief] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [briefError, setBriefError] = useState<string | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const consumedInitialSeriesIdRef = useRef<number | null>(null);
  const sceneSelectionPinnedRef = useRef(false);
  const streamSceneCountRef = useRef(0);

  const activeEpisodeNumber = activeEpisode?.episode_number || 1;
  const scenes = scriptOutput?.scenes || activeEpisode?.script_output?.scenes || activeEpisode?.scenes || streamScenes;
  const activeSceneIdx = scenes.length ? Math.min(selectedSceneIdx, scenes.length - 1) : 0;
  const selectedScene = scenes[activeSceneIdx] || null;
  const isRecoverableEpisode = Boolean(activeEpisode && ['generating', 'failed'].includes(activeEpisode.status) && !generating);
  // Output heading guard: scene count is metadata, while the operator needs the
  // episode title as the primary anchor when reviewing a generated episode.
  const outputEpisodeTitle = scriptOutput?.title || activeEpisode?.script_output?.title || activeEpisode?.title || briefDraft.title || `Tap ${activeEpisodeNumber}`;
  const phaseLog = useMemo(() => activeEpisode?.phase_log || [], [activeEpisode?.phase_log]);
  const completedCount = episodes.filter(ep => ep.status === 'completed' || ep.status === 'needs_review').length;
  const hasSeries = Boolean(selectedSeries);
  const currentPhase = deriveSeriesPhase(hasSeries, episodeStage, generating);
  const selectedStyle = intakeDraft.styleChoice === 'custom' ? intakeDraft.customStyle.trim() : intakeDraft.styleChoice;

  const seasonSlots = useMemo(() => {
    const slots = selectedSeries?.season_map?.episode_slots;
    return Array.isArray(slots) ? slots : [];
  }, [selectedSeries]);

  const selectedSlot = useMemo(() => {
    return seasonSlots.find(slot => typeof slot === 'object' && slot !== null && (slot as { episode_number?: unknown }).episode_number === activeEpisodeNumber);
  }, [activeEpisodeNumber, seasonSlots]);

  const artifactContent = useMemo(() => {
    if (artifactTab === 'review') {
      return artifactSummary(scriptOutput?.review_report || activeEpisode?.review_report);
    }
    if (artifactTab === 'phase_log') {
      if (phaseLog.length === 0) return 'Chưa có phase log.';
      return phaseLog
        .slice()
        .reverse()
        .map(entry => `${phaseLabel(entry.phase)} - ${entry.validation_status || 'passed'}`)
        .join('\n');
    }
    return artifactSummary(scriptOutput?.continuity_delta || activeEpisode?.continuity_delta);
  }, [activeEpisode?.continuity_delta, activeEpisode?.review_report, artifactTab, phaseLog, scriptOutput?.continuity_delta, scriptOutput?.review_report]);

  const selectEpisode = useCallback(async (seriesId: number, episodeNumber: number) => {
    setLoadingBrief(true);
    setBriefError(null);
    setGenerationError(null);
    sceneSelectionPinnedRef.current = false;
    try {
      const episode = await fetchEpisodeBrief(apiKey, seriesId, episodeNumber);
      const episodeHasOutput = Boolean(episode.script_output || (episode.scenes && episode.scenes.length > 0));
      setActiveEpisode(episode);
      setBriefDraft(draftFromEpisode(episode));
      setScriptOutput(episode.script_output || null);
      setStreamScenes(episode.scenes || []);
      streamSceneCountRef.current = episode.scenes?.length || episode.script_output?.scenes?.length || 0;
      setEpisodeStage(episodeHasOutput ? 'output' : 'brief');
      setBriefReady(Boolean(episode.user_revision || episodeHasOutput));
      setSelectedSceneIdx(0);
      setEpisodes(prev => {
        const exists = prev.some(item => item.episode_number === episode.episode_number);
        const next = exists
          ? prev.map(item => item.episode_number === episode.episode_number ? episode : item)
          : [...prev, episode];
        return next.sort((a, b) => a.episode_number - b.episode_number);
      });
    } catch (err: unknown) {
      setBriefError(getErrorMessage(err, 'Không thể tải brief tập phim.'));
    } finally {
      setLoadingBrief(false);
    }
  }, [apiKey]);

  // Series selection guard: History handoff and newly created series both enter
  // the same workbench path and default to the next available episode.
  const selectSeries = useCallback(async (id: number, preferredEpisode?: number) => {
    setSelectedSeriesId(id);
    setLoadingDetail(true);
    setPageError(null);
    try {
      const detail = await fetchSeriesDetail(apiKey, id);
      const eps = await fetchEpisodes(apiKey, id);
      const sorted = eps.slice().sort((a, b) => a.episode_number - b.episode_number);
      const completedBeforeNext = sorted.filter(ep => ep.status === 'completed' || ep.status === 'needs_review').length;
      const nextEpisode = preferredEpisode
        || sorted.find(ep => ep.status === 'generating')?.episode_number
        || sorted.find(ep => ep.status === 'failed')?.episode_number
        || Math.min(detail.target_episode_count, Math.max(1, completedBeforeNext + 1))
        || 1;
      setSelectedSeries(detail);
      setEpisodes(sorted);
      await selectEpisode(id, nextEpisode);
    } catch (err: unknown) {
      setPageError(getErrorMessage(err, 'Không thể tải chi tiết series.'));
    } finally {
      setLoadingDetail(false);
    }
  }, [apiKey, selectEpisode]);

  // History handoff guard: a series id opened from unified History selects the
  // intended workbench once, while sidebar visits keep the intake blank.
  useEffect(() => {
    if (initialSeriesId && consumedInitialSeriesIdRef.current !== initialSeriesId) {
      consumedInitialSeriesIdRef.current = initialSeriesId;
      void selectSeries(initialSeriesId);
    }
  }, [initialSeriesId, selectSeries]);

  // Intake validation guard: series setup is an expensive LLM call, so the
  // client rejects empty premise/custom style before touching the backend.
  const handleCreateSeries = async () => {
    if (!apiKey.trim()) {
      setIntakeError('Vui lòng lưu App API Key trong Cài đặt trước khi tạo chuỗi.');
      return;
    }
    if (!intakeDraft.premise.trim()) {
      setIntakeError('Nhập ý tưởng chuỗi video trước khi sinh ý tưởng.');
      return;
    }
    if (intakeDraft.styleChoice === 'custom' && !intakeDraft.customStyle.trim()) {
      setIntakeError('Nhập phong cách tùy chỉnh hoặc chọn preset có sẵn.');
      return;
    }

    setCreatingSeries(true);
    setIntakeError(null);
    setIntakeSuccess(null);
    try {
      const payload: SeriesV2CreatePayload = {
        title: intakeDraft.title.trim() || deriveTitleFromPremise(intakeDraft.premise),
        premise: intakeDraft.premise.trim(),
        style: selectedStyle || 'anime',
        topic_type: intakeDraft.topicType,
        target_episode_count: intakeDraft.targetEpisodeCount,
        default_scene_count: intakeDraft.defaultSceneCount,
        scene_duration_sec: intakeDraft.sceneDurationSec,
        model_name: modelName,
      };
      const series = await createSeries(apiKey, payload);
      setIntakeSuccess('Đã tạo chuỗi. Đang mở workbench...');
      setIntakeDraft(DEFAULT_INTAKE);
      await selectSeries(series.id, 1);
    } catch (err: unknown) {
      setIntakeError(getErrorMessage(err, 'Không thể tạo chuỗi video.'));
    } finally {
      setCreatingSeries(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Xóa chuỗi này và tất cả tập liên quan?')) return;
    try {
      await deleteSeries(apiKey, id);
      setSelectedSeriesId(null);
      setSelectedSeries(null);
      setEpisodes([]);
      setActiveEpisode(null);
      setScriptOutput(null);
      setStreamScenes([]);
      setProgress(EMPTY_PROGRESS);
      setEpisodeStage('brief');
      setBriefReady(false);
      setSelectedSceneIdx(0);
      sceneSelectionPinnedRef.current = false;
    } catch (err: unknown) {
      setPageError(getErrorMessage(err, 'Không thể xóa chuỗi.'));
    }
  };

  // Brief-generation guard: the UI no longer exposes multiple brief candidates;
  // it applies the first backend suggestion into the editable brief form.
  const handleLoadCandidates = async () => {
    if (!selectedSeriesId || !activeEpisode) return;
    setLoadingCandidates(true);
    setBriefError(null);
    try {
      const res = await generateEpisodeSuggestions(apiKey, selectedSeriesId, activeEpisode.episode_number);
      if (!res.success) throw new Error(res.error || 'Không thể sinh brief.');
      const firstCandidate = (res.suggestions || [])[0];
      if (!firstCandidate) throw new Error('Backend không trả về brief hợp lệ.');
      setBriefDraft(current => draftFromCandidate(firstCandidate, current));
      setBriefReady(true);
    } catch (err: unknown) {
      setBriefError(getErrorMessage(err, 'Không thể sinh brief.'));
    } finally {
      setLoadingCandidates(false);
    }
  };

  const handleSaveBrief = async (): Promise<EpisodeResponse | null> => {
    if (!selectedSeriesId || !activeEpisode) return null;
    setSavingBrief(true);
    setBriefError(null);
    try {
      const updated = await updateEpisodeBrief(
        apiKey,
        selectedSeriesId,
        activeEpisode.episode_number,
        briefPayloadFromDraft(briefDraft)
      );
      setActiveEpisode(updated);
      setBriefDraft(draftFromEpisode(updated));
      setScriptOutput(updated.script_output || null);
      setEpisodes(prev => prev.map(item => item.episode_number === updated.episode_number ? updated : item));
      setBriefReady(true);
      return updated;
    } catch (err: unknown) {
      setBriefError(getErrorMessage(err, 'Không thể lưu brief.'));
      return null;
    } finally {
      setSavingBrief(false);
    }
  };

  const handleCopyToClipboard = async (text: string, key: string) => {
    if (!text) return;
    await navigator.clipboard.writeText(text);
    setCopiedKey(key);
    window.setTimeout(() => setCopiedKey(null), 2200);
  };

  // Copy-contract guard: output exposes exactly one copy button, and that button
  // returns the compact JSON prompt pack expected by downstream video assembly.
  const handleCopyPromptPack = () => {
    const output = scriptOutput || activeEpisode?.script_output || null;
    void handleCopyToClipboard(buildSeriesPromptPackJson(selectedSeries, activeEpisode, output, scenes), 'prompt_pack');
  };

  // Scene detail guard: compact rows only choose context; full prompt and copy
  // controls stay in one stable detail panel to keep long episodes scannable.
  const handleSelectScene = (index: number) => {
    sceneSelectionPinnedRef.current = true;
    setSelectedSceneIdx(index);
  };

  // Recovery action guard: retry keeps persisted scenes visible, while restart
  // clears only generated episode output after the accepted brief is saved.
  const handleStartGeneration = async (options: SeriesGenerationOptions = {}) => {
    if (!selectedSeriesId || !activeEpisode) return;
    const savedEpisode = await handleSaveBrief();
    if (!savedEpisode) return;

    setGenerating(true);
    setEpisodeStage('output');
    setGenerationError(null);
    if (options.restart) {
      setScriptOutput(null);
      setStreamScenes([]);
      setSelectedSceneIdx(0);
    } else {
      setScriptOutput(scriptOutput || activeEpisode.script_output || null);
      setStreamScenes(activeEpisode.scenes || []);
    }
    sceneSelectionPinnedRef.current = false;
    streamSceneCountRef.current = options.restart ? 0 : scenes.length;
    setProgress({
      ...EMPTY_PROGRESS,
      phase: 'episode_planning',
      label: 'Đang kết nối stream',
      percent: 8,
      scenesTotal: savedEpisode.scene_count,
    });

    try {
      const response = await generateEpisodeScript(
        apiKey,
        selectedSeriesId,
        savedEpisode.episode_number,
        modelName,
        { run_reviewer: true, run_packaging: false, restart: options.restart ?? false }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(getErrorMessage(errorData, `Lỗi kết nối server (${response.status}).`));
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('Trình duyệt không hỗ trợ đọc stream.');

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
          if (!trimmed.startsWith('data: ')) continue;
          const raw = trimmed.slice(6);
          if (!raw) continue;

          let event: SeriesStreamEvent;
          try {
            event = JSON.parse(raw) as SeriesStreamEvent;
          } catch {
            continue;
          }

          if (event.status === 'error') {
            throw new Error(event.message || 'Stream báo lỗi.');
          }
          if (event.status === 'scene' && event.data && !Array.isArray(event.data)) {
            const scene = event.data as SeriesScene;
            const sceneIndex = streamSceneCountRef.current;
            streamSceneCountRef.current += 1;
            setStreamScenes(prev => [...prev, scene]);
            if (!sceneSelectionPinnedRef.current) {
              setSelectedSceneIdx(sceneIndex);
            }
          }
          if (event.status === 'done' && event.data && !Array.isArray(event.data)) {
            setScriptOutput(event.data as SeriesScriptOutput);
          }
          setProgress(current => estimateProgress(event, current, savedEpisode.scene_count));
        }
      }

      await selectSeries(selectedSeriesId, savedEpisode.episode_number);
      setArtifactTab('continuity');
    } catch (err: unknown) {
      setGenerationError(getErrorMessage(err, 'Gặp lỗi khi sinh tập.'));
      setActiveEpisode(current => current ? { ...current, status: 'failed' } : current);
      setEpisodes(prev => prev.map(item => item.episode_number === savedEpisode.episode_number ? { ...item, status: 'failed' } : item));
      setProgress(current => ({ ...current, label: 'Stream lỗi', phase: 'error' }));
    } finally {
      setGenerating(false);
    }
  };

  if (!apiKey.trim()) {
    return (
      <div className="series-page">
        <section className="series-empty">
          <p className="series-kicker">CHUỖI VIDEO</p>
          <h1>Cần App API Key</h1>
          <p>Vào Cài đặt để lưu App API Key trước khi quản lý chuỗi video.</p>
        </section>
      </div>
    );
  }

  return (
    <div className="series-page">
      <section className="series-workspace" aria-label="Quản lý chuỗi video">
        <div className="series-stepper" aria-label="Tiến trình chuỗi">
          {SERIES_STEPS.map(step => (
            <div key={step.id} className={`series-step ${currentPhase === step.id ? 'is-active' : ''}`}>
              <span>{step.id}</span>
              <strong>{step.label}</strong>
              <small>{step.detail}</small>
            </div>
          ))}
        </div>

        {!selectedSeries ? (
          <section className="series-intake-grid">
            <div className="series-panel series-intake">
              <div className="series-panel__head">
                <div>
                  <p className="series-kicker">CHUỖI VIDEO</p>
                  <h1>Chuỗi video</h1>
                  <p className="series-muted">Nhập ý tưởng, cấu hình chuỗi, rồi sinh setup series.</p>
                </div>
              </div>
              {(intakeError || intakeSuccess || pageError) && (
                <div className={`series-alert ${intakeError || pageError ? 'series-alert--error' : 'series-alert--success'}`}>
                  {intakeError || pageError || intakeSuccess}
                </div>
              )}
              <textarea
                className="series-textarea"
                value={intakeDraft.premise}
                onChange={(event) => setIntakeDraft(current => ({ ...current, premise: event.target.value }))}
                placeholder="Ví dụ: Một đội thám hiểm bị kẹt trong thành phố ngầm, mỗi tập mở khóa một tầng ký ức và một lời nói dối mới..."
                disabled={creatingSeries}
              />
              <div className="series-actions series-actions--intake">
                <button
                  type="button"
                  className="series-btn series-btn--primary"
                  onClick={() => void handleCreateSeries()}
                  disabled={creatingSeries}
                >
                  {creatingSeries ? 'Đang tạo...' : 'Sinh ý tưởng'}
                </button>
                <span>{intakeDraft.targetEpisodeCount} tập · {intakeDraft.defaultSceneCount} cảnh/tập · {intakeDraft.sceneDurationSec}s/cảnh</span>
              </div>
            </div>

            <aside className="series-panel series-config">
              <div className="series-panel__head">
                <div>
                  <p className="series-kicker">CẤU HÌNH</p>
                  <h2>Thiết lập chuỗi</h2>
                </div>
                <span className="series-config__model">{modelName}</span>
              </div>
              <div className="brief-form">
                <label>
                  <span>Tên series</span>
                  <input
                    value={intakeDraft.title}
                    onChange={(event) => setIntakeDraft(current => ({ ...current, title: event.target.value }))}
                    placeholder="Để trống để lấy từ ý tưởng"
                    disabled={creatingSeries}
                  />
                </label>
                <label>
                  <span>Phong cách dựng</span>
                  <select
                    value={intakeDraft.styleChoice}
                    onChange={(event) => {
                      const value = event.target.value as StyleChoice;
                      setIntakeDraft(current => ({
                        ...current,
                        styleChoice: value,
                        customStyle: value === 'custom' ? current.customStyle : '',
                      }));
                      setIntakeError(null);
                    }}
                    disabled={creatingSeries}
                  >
                    {STYLE_OPTIONS.map(option => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Phong cách tùy chỉnh</span>
                  <input
                    value={intakeDraft.customStyle}
                    onChange={(event) => setIntakeDraft(current => ({ ...current, customStyle: event.target.value }))}
                    placeholder="Vi du: austere sci-fi, glass cockpit"
                    disabled={creatingSeries || intakeDraft.styleChoice !== 'custom'}
                  />
                </label>
                <label>
                  <span>Loại chủ đề</span>
                  <select
                    value={intakeDraft.topicType}
                    onChange={(event) => setIntakeDraft(current => ({ ...current, topicType: event.target.value as SeriesTopicType }))}
                    disabled={creatingSeries}
                  >
                    {TOPIC_TYPE_OPTIONS.map(option => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </label>
                <div className="brief-form__row">
                  <label>
                    <span>Số tập</span>
                    <select
                      value={intakeDraft.targetEpisodeCount}
                      onChange={(event) => setIntakeDraft(current => ({ ...current, targetEpisodeCount: Number(event.target.value) }))}
                      disabled={creatingSeries}
                    >
                      {EPISODE_OPTIONS.map(value => (
                        <option key={value} value={value}>{value} tập</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>Cảnh/tập</span>
                    <select
                      value={intakeDraft.defaultSceneCount}
                      onChange={(event) => setIntakeDraft(current => ({ ...current, defaultSceneCount: Number(event.target.value) }))}
                      disabled={creatingSeries}
                    >
                      {SCENE_OPTIONS.map(value => (
                        <option key={value} value={value}>{value} cảnh</option>
                      ))}
                    </select>
                  </label>
                </div>
                <label>
                  <span>Giây/cảnh</span>
                  <select
                    value={intakeDraft.sceneDurationSec}
                    onChange={(event) => setIntakeDraft(current => ({ ...current, sceneDurationSec: Number(event.target.value) }))}
                    disabled={creatingSeries}
                  >
                    {DURATION_OPTIONS.map(value => (
                      <option key={value} value={value}>{value}s</option>
                    ))}
                  </select>
                </label>
              </div>
            </aside>
          </section>
        ) : (
          <>
            <header className="series-topbar">
              <div className="series-title-block">
                <nav className="series-breadcrumb" aria-label="Breadcrumb series">
                  <button type="button" onClick={onNavigateToHistory}>
                    Series
                  </button>
                  <span aria-hidden="true">&gt;</span>
                  <button type="button" onClick={onNavigateToHistory}>
                    {selectedSeries.title}
                  </button>
                </nav>
                <h1>{selectedSeries.title}</h1>
                <p>{selectedSeries.premise}</p>
              </div>
              <div className="series-metrics" aria-label="Thông số series">
                <span><strong>{completedCount}</strong> hoàn thành</span>
                <span><strong>{selectedSeries.target_episode_count}</strong> tập</span>
                <span><strong>{selectedSeries.default_scene_count}</strong> cảnh/tập</span>
                <button
                  className="series-icon-btn series-icon-btn--danger"
                  onClick={() => void handleDelete(selectedSeries.id)}
                  title="Xóa chuỗi"
                >
                  Xóa
                </button>
              </div>
            </header>

            {pageError && <div className="series-alert series-alert--error">{pageError}</div>}
            {loadingDetail && <div className="series-skeleton">Đang tải chuỗi...</div>}

            <nav className="episode-timeline" aria-label="Timeline episode">
              {Array.from({ length: selectedSeries.target_episode_count }, (_, index) => {
                const number = index + 1;
                const episode = episodes.find(ep => ep.episode_number === number);
                const meta = statusMeta(episode?.status || 'pending');
                const active = activeEpisodeNumber === number;
                const enabled = canOpenEpisode(number, episodes, selectedSeries.target_episode_count);
                return (
                  <button
                    key={number}
                    className={`episode-chip ${active ? 'is-active' : ''}`}
                    onClick={() => void selectEpisode(selectedSeries.id, number)}
                    disabled={generating || !enabled}
                    aria-pressed={active}
                  >
                    <span className="episode-chip__number">{String(number).padStart(2, '0')}</span>
                    <span className={meta.className}>{meta.label}</span>
                  </button>
                );
              })}
            </nav>

            {episodeStage === 'brief' && (
              <section className="series-panel series-panel--brief">
                <div className="series-panel__head">
                  <div>
                    <p className="series-kicker">GIAI ĐOẠN 1</p>
                    <h2>Tập {activeEpisodeNumber}: {briefDraft.title || 'Chưa đặt tên'}</h2>
                  </div>
                  <span className={statusMeta(activeEpisode?.status || 'pending').className}>
                    {statusMeta(activeEpisode?.status || 'pending').label}
                  </span>
                </div>

                {briefError && <div className="series-alert series-alert--error">{briefError}</div>}
                {isRecoverableEpisode && (
                  <div className="series-alert" role="status">
                    <div>
                      <strong>{activeEpisode?.status === 'failed' ? 'Tập trước đó bị lỗi' : 'Tập đang sinh dở'}</strong>
                      <p>Tiếp tục sẽ dùng artifact đã lưu; sinh lại từ đầu giữ brief nhưng bỏ output cũ.</p>
                    </div>
                    <div className="series-actions series-actions--compact">
                      <button className="series-btn series-btn--primary" onClick={() => void handleStartGeneration({ restart: false })} disabled={generating || savingBrief}>
                        Tiếp tục sinh
                      </button>
                      <button className="series-btn" onClick={() => void handleStartGeneration({ restart: true })} disabled={generating || savingBrief}>
                        Sinh lại từ đầu
                      </button>
                    </div>
                  </div>
                )}
                {loadingBrief ? (
                  <div className="series-skeleton">Đang tải brief...</div>
                ) : (
                  <>
                    <div className="series-brief-layout">
                      <div className="brief-form">
                        <label>
                          <span>Tiêu đề tập</span>
                          <input
                            value={briefDraft.title}
                            onChange={(event) => setBriefDraft(current => ({ ...current, title: event.target.value }))}
                            disabled={generating || savingBrief}
                          />
                        </label>
                        <label>
                          <span>Premise</span>
                          <textarea
                            value={briefDraft.premise}
                            onChange={(event) => setBriefDraft(current => ({ ...current, premise: event.target.value }))}
                            disabled={generating || savingBrief}
                          />
                        </label>
                        <div className="brief-form__split">
                          <label>
                            <span>Phải có</span>
                            <textarea
                              value={briefDraft.mustInclude}
                              onChange={(event) => setBriefDraft(current => ({ ...current, mustInclude: event.target.value }))}
                              disabled={generating || savingBrief}
                            />
                          </label>
                          <label>
                            <span>Cần tránh</span>
                            <textarea
                              value={briefDraft.mustAvoid}
                              onChange={(event) => setBriefDraft(current => ({ ...current, mustAvoid: event.target.value }))}
                              disabled={generating || savingBrief}
                            />
                          </label>
                        </div>
                        <div className="brief-form__row">
                          <label>
                            <span>Số cảnh</span>
                            <input
                              type="number"
                              min={4}
                              max={200}
                              value={briefDraft.sceneCount}
                              onChange={(event) => setBriefDraft(current => ({ ...current, sceneCount: Number(event.target.value) }))}
                              disabled={generating || savingBrief}
                            />
                          </label>
                          <label>
                            <span>Kiểu kết thúc</span>
                            <select
                              value={briefDraft.endingMode}
                              onChange={(event) => setBriefDraft(current => ({ ...current, endingMode: event.target.value as SeriesEndingMode }))}
                              disabled={generating || savingBrief}
                            >
                              {ENDING_OPTIONS.map(option => (
                                <option key={option.value} value={option.value}>{option.label}</option>
                              ))}
                            </select>
                          </label>
                        </div>
                        <label>
                          <span>Ghi chú</span>
                          <textarea
                            value={briefDraft.notes}
                            onChange={(event) => setBriefDraft(current => ({ ...current, notes: event.target.value }))}
                            disabled={generating || savingBrief}
                          />
                        </label>
                      </div>

                      <div className="series-brief-side">
                        <div className="series-mini-panel">
                          <p className="series-kicker">VỊ TRÍ TẬP</p>
                          <pre>{artifactSummary(selectedSlot || activeEpisode?.brief?.slot).slice(0, 1200)}</pre>
                        </div>
                      </div>
                    </div>

                    <div className="series-actions">
                      {!briefReady ? (
                        <>
                          <button className="series-btn series-btn--primary" onClick={() => void handleLoadCandidates()} disabled={loadingCandidates || generating || !activeEpisode}>
                            {loadingCandidates ? 'Đang sinh...' : 'Sinh brief'}
                          </button>
                          <button className="series-btn" onClick={() => void handleSaveBrief()} disabled={savingBrief || generating || !activeEpisode}>
                            {savingBrief ? 'Đang lưu...' : 'Lưu brief thủ công'}
                          </button>
                        </>
                      ) : (
                        <>
                          <button className="series-btn" onClick={() => void handleSaveBrief()} disabled={savingBrief || generating || !activeEpisode}>
                            {savingBrief ? 'Đang lưu...' : 'Lưu brief'}
                          </button>
                          <button className="series-btn series-btn--primary" onClick={() => void handleStartGeneration()} disabled={generating || savingBrief || !activeEpisode}>
                            {generating ? 'Đang sinh...' : 'Sinh tập này'}
                          </button>
                        </>
                      )}
                    </div>
                  </>
                )}
              </section>
            )}

            {episodeStage === 'output' && (
              <>
                {(generating || generationError || progress.percent > 0) && (
                  <section className="series-panel">
                    <div className="series-panel__head">
                      <div>
                        <p className="series-kicker">STREAM</p>
                        <h2>{progress.label}</h2>
                      </div>
                      <span className="series-progress__value">{progress.percent}%</span>
                    </div>
                    <div className="series-progress" aria-label="Tiến độ sinh tập">
                      <span style={{ width: `${progress.percent}%` }} />
                    </div>
                    {generationError && <div className="series-alert series-alert--error">{generationError}</div>}
                  </section>
                )}

                <section className="series-panel series-panel--output">
                  <div className="series-panel__head">
                    <div>
                      <p className="series-kicker">GIAI ĐOẠN 2</p>
                      <h2>{outputEpisodeTitle}</h2>
                      <p className="series-muted">{scenes.length} cảnh</p>
                    </div>
                    <div className="series-actions series-actions--compact">
                      {!generating && (
                        <button className="series-btn" onClick={() => setEpisodeStage('brief')} disabled={loadingBrief}>
                          Sửa brief
                        </button>
                      )}
                      <button
                        className="series-btn"
                        onClick={handleCopyPromptPack}
                        disabled={scenes.length === 0}
                      >
                        {copiedKey === 'prompt_pack' ? 'Đã sao chép' : 'Sao chép JSON'}
                      </button>
                    </div>
                  </div>

                  {isRecoverableEpisode && (
                    <div className="series-alert" role="status">
                      <div>
                        <strong>{activeEpisode?.status === 'failed' ? 'Tập trước đó bị lỗi' : 'Tập đang sinh dở'}</strong>
                        <p>Tiếp tục sẽ giữ các cảnh đã lưu; sinh lại từ đầu sẽ reset output của tập này.</p>
                      </div>
                      <div className="series-actions series-actions--compact">
                        <button className="series-btn series-btn--primary" onClick={() => void handleStartGeneration({ restart: false })} disabled={generating || savingBrief}>
                          Tiếp tục sinh
                        </button>
                        <button className="series-btn" onClick={() => void handleStartGeneration({ restart: true })} disabled={generating || savingBrief}>
                          Sinh lại từ đầu
                        </button>
                      </div>
                    </div>
                  )}

                  <div className="series-output-layout">
                    {scenes.length === 0 ? (
                      <p className="series-muted">Chưa có cảnh cho tập này.</p>
                    ) : (
                      <div className="series-scene-workbench">
                        <div className="series-scene-nav" aria-label="Danh sách cảnh">
                          {scenes.map((scene, index) => (
                            <button
                              key={`${scene.scene_number || index}-${scene.title || 'scene'}`}
                              className={`series-scene-row ${activeSceneIdx === index ? 'is-active' : ''}`}
                              onClick={() => handleSelectScene(index)}
                              aria-pressed={activeSceneIdx === index}
                            >
                              <span>{String(scene.scene_number || index + 1).padStart(2, '0')}</span>
                              <strong>{scene.title || 'Untitled scene'}</strong>
                              <small>{scenePreview(scene).slice(0, 100)}</small>
                              {scene.veo3_prompt_en && <em>Prompt</em>}
                            </button>
                          ))}
                        </div>

                        <article className="series-scene-detail">
                          {selectedScene ? (
                            <>
                              <header>
                                <div>
                                  <span>{String(selectedScene.scene_number || activeSceneIdx + 1).padStart(2, '0')}</span>
                                  <h3>{selectedScene.title || 'Untitled scene'}</h3>
                                </div>
                              </header>
                              {selectedScene.action_detail_vi && <p>{selectedScene.action_detail_vi}</p>}
                              {selectedScene.voice_over_vi && selectedScene.voice_over_vi !== selectedScene.action_detail_vi && (
                                <p className="series-scene-detail__voice">{selectedScene.voice_over_vi}</p>
                              )}
                              {selectedScene.veo3_prompt_en && <pre>{selectedScene.veo3_prompt_en}</pre>}
                              {selectedScene.handoff_state && <small>Handoff: {selectedScene.handoff_state}</small>}
                            </>
                          ) : (
                            <p className="series-muted">Chọn một cảnh để xem chi tiết.</p>
                          )}
                        </article>
                      </div>
                    )}

                    <div className="series-artifact-tabs">
                      <div className="series-tablist" role="tablist" aria-label="Artifact tabs">
                        {[
                          ['continuity', 'Continuity'],
                          ['review', 'Review'],
                          ['phase_log', 'Nhật ký'],
                        ].map(([value, label]) => (
                          <button
                            key={value}
                            type="button"
                            role="tab"
                            aria-selected={artifactTab === value}
                            className={`series-tab ${artifactTab === value ? 'is-active' : ''}`}
                            onClick={() => setArtifactTab(value as ArtifactTab)}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                      <pre>{artifactContent.slice(0, 2600)}</pre>
                    </div>
                  </div>
                </section>
              </>
            )}
          </>
        )}
      </section>
    </div>
  );
}
