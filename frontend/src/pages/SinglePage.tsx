import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { useProductionFlow } from '../hooks/useProductionFlow';
import {
  getErrorMessage,
  listProjects,
  type ProjectResponse,
  type ScriptSuggestion,
} from '../services/api';
import { SingleOutputPanel } from './SingleOutputPanel';

type PresetStyle = 'anime' | 'realistic' | 'cinematic' | 'cartoon';
type StyleChoice = PresetStyle | 'custom';
type AspectRatio = '16:9' | '9:16';
type GenerationMode = 'single' | 'longform' | 'series_short' | 'series_long';
type TopicType = 'historical' | 'scientific' | 'fictional_mythology' | 'fictional_original';
type SinglePhase = 1 | 2 | 3;

const SCENE_OPTIONS = [4, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 80, 100, 120, 150, 200];

const STYLE_OPTIONS: Array<{ value: StyleChoice; label: string }> = [
  { value: 'anime', label: 'Anime' },
  { value: 'realistic', label: 'Realistic' },
  { value: 'cinematic', label: 'Cinematic' },
  { value: 'cartoon', label: 'Cartoon 3D' },
  { value: 'custom', label: 'Tùy chọn' },
];

const TOPIC_TYPE_OPTIONS: Array<{ value: TopicType; label: string; detail: string }> = [
  { value: 'fictional_original', label: 'Sáng tác gốc', detail: 'Tự do hư cấu, kiểm logic mềm' },
  { value: 'fictional_mythology', label: 'Thần thoại', detail: 'Giữ tính truyền thuyết, tránh khẳng định lịch sử' },
  { value: 'scientific', label: 'Khoa học', detail: 'Cần kiểm chứng thuật ngữ và cơ chế' },
  { value: 'historical', label: 'Lịch sử', detail: 'Fact-check chặt, tránh lịch sử Việt Nam' },
];

const SINGLE_STEPS: Array<{ id: SinglePhase; label: string; detail: string }> = [
  { id: 1, label: 'Khởi tạo', detail: 'Ý tưởng + cấu hình' },
  { id: 2, label: 'Chọn gợi ý', detail: '5 hướng kịch bản' },
  { id: 3, label: 'Sinh chi tiết', detail: 'Mở output' },
];

interface SinglePageProps {
  apiKey: string;
  modelName: string;
  prodFlow: ReturnType<typeof useProductionFlow>;
  inputContent: string;
  setInputContent: (val: string) => void;
  presetStyle: PresetStyle;
  setPresetStyle: (val: PresetStyle) => void;
  customStyle: string;
  setCustomStyle: (val: string) => void;
  numScenes: number;
  setNumScenes: (val: number) => void;
  aspectRatio: AspectRatio;
  setAspectRatio: (val: AspectRatio) => void;
  sceneDuration: number;
  setSceneDuration: (val: number) => void;
  generationMode: GenerationMode;
  projectId: number | null;
  suggestions: ScriptSuggestion[];
  selectedSuggestionIdx: number | null;
  status: string;
  loadingSuggestions: boolean;
  suggestionsError: string | null;
  resetRevision: number;
  topicTypeOverride?: TopicType | null;
  setTopicTypeOverride?: (val: TopicType | null) => void;
  handleGenerateSuggestions: (apiKey: string, modelName: string) => Promise<void>;
  handleSelectSuggestion: (idx: number) => void;
  onNavigateToHistory: () => void;
  handleReset: () => void;
  handleReturnToSingleIntake: () => void;
  handleLoadProject: (apiKey: string, id: number) => Promise<void>;
}

function isLegacySeriesMode(mode?: GenerationMode | null): boolean {
  return mode === 'series_short' || mode === 'series_long';
}

// Stepper guard: the visible Single workflow follows the old 3-stage rhythm
// while output streaming remains owned by the production hook.
// Inline-output guard: phase 3 now means the embedded production workbench is
// open, not merely that a suggestion card has been selected.
function deriveSinglePhase(
  loadingSuggestions: boolean,
  suggestionsCount: number,
  outputOpen: boolean,
): SinglePhase {
  if (outputOpen) return 3;
  if (loadingSuggestions || suggestionsCount > 0) return 2;
  return 1;
}

function derivedModeLabel(numScenes: number): string {
  return numScenes > 20 ? 'Dài' : 'Ngắn';
}

function statusLabel(status: string): string {
  if (status === 'script_generated') return 'Đã sinh';
  if (status === 'generating_script') return 'Đang sinh / tiếp tục';
  if (status === 'script_failed') return 'Lỗi, có thể tiếp tục';
  if (status === 'suggestions_generated') return 'Có gợi ý';
  return 'Nháp';
}

function formatDuration(numScenes: number, sceneDuration: number): string {
  const totalSeconds = numScenes * sceneDuration;
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return seconds ? `${minutes}m${seconds.toString().padStart(2, '0')}s` : `${minutes}m`;
}

function formatDate(value?: string): string {
  if (!value) return 'Chưa rõ ngày';
  return new Date(value).toLocaleDateString('vi-VN');
}

function sortTime(project: ProjectResponse): number {
  return new Date(project.updated_at || project.created_at || 0).getTime();
}

// Phase-layout guard: SinglePage owns the visible workflow split; API payloads
// and streaming generation stay isolated in the production hook/output panel.
export default function SinglePage({
  apiKey,
  modelName,
  prodFlow,
  inputContent,
  setInputContent,
  presetStyle,
  setPresetStyle,
  customStyle,
  setCustomStyle,
  numScenes,
  setNumScenes,
  aspectRatio,
  setAspectRatio,
  sceneDuration,
  setSceneDuration,
  generationMode,
  projectId,
  suggestions,
  selectedSuggestionIdx,
  status,
  loadingSuggestions,
  suggestionsError,
  resetRevision,
  topicTypeOverride,
  setTopicTypeOverride,
  handleGenerateSuggestions,
  handleSelectSuggestion,
  onNavigateToHistory,
  handleReset,
  handleReturnToSingleIntake,
  handleLoadProject,
}: SinglePageProps) {
  const [historyList, setHistoryList] = useState<ProjectResponse[]>([]);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [styleChoice, setStyleChoice] = useState<StyleChoice>(customStyle.trim() ? 'custom' : presetStyle);
  const [outputRequested, setOutputRequested] = useState(false);
  const [outputDismissed, setOutputDismissed] = useState(false);
  const lastSyncedProjectIdRef = useRef<number | null>(projectId);
  const lastSyncedResetRevisionRef = useRef<number>(resetRevision);

  const safeSuggestions = Array.isArray(suggestions) ? suggestions : [];
  const selectedSuggestion = safeSuggestions.find(sug => sug.index === selectedSuggestionIdx);
  const isLegacySeriesProject = isLegacySeriesMode(generationMode);
  const canOpenOutput = projectId !== null && selectedSuggestionIdx !== null && !isLegacySeriesProject;
  const effectiveTopicType = topicTypeOverride || selectedSuggestion?.topic_type || 'fictional_original';
  const outputHasContent = Boolean(prodFlow.scriptOutput && (
    prodFlow.scriptOutput.overview_analysis_vi ||
    (prodFlow.scriptOutput.characters || []).length > 0 ||
    (prodFlow.scriptOutput.scenes || []).length > 0
  ));
  const restoredOutputOpen = !outputDismissed && (status === 'script_generated' || status === 'generating_script' || status === 'script_failed' || outputHasContent);
  const outputOpen = outputRequested || prodFlow.generatingScript || restoredOutputOpen;
  const currentPhase = deriveSinglePhase(loadingSuggestions, safeSuggestions.length, outputOpen);
  const isCustomStyleSelected = styleChoice === 'custom';

  const recentProjects = useMemo(
    () => historyList
      .filter(project => !isLegacySeriesMode(project.generation_mode))
      .sort((a, b) => sortTime(b) - sortTime(a))
      .slice(0, 5),
    [historyList],
  );

  // Recent-project guard: Single keeps a light local strip while full archive
  // pagination stays owned by the unified History tab.
  const fetchHistory = useCallback(async () => {
    if (!apiKey.trim()) {
      setHistoryList([]);
      setHistoryError(null);
      return;
    }
    setLoadingHistory(true);
    setHistoryError(null);
    try {
      const data = await listProjects(apiKey);
      setHistoryList(data || []);
    } catch (err: unknown) {
      setHistoryError(getErrorMessage(err, 'Không thể tải dự án gần đây.'));
    } finally {
      setLoadingHistory(false);
    }
  }, [apiKey]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void fetchHistory();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [fetchHistory, projectId, status]);

  // Restore-sync guard: project history may hydrate either a preset style or a
  // freeform style; resets also need to force local UI back to the default
  // preset because the sidebar can reset while SinglePage stays mounted.
  useEffect(() => {
    if (lastSyncedResetRevisionRef.current !== resetRevision) {
      lastSyncedResetRevisionRef.current = resetRevision;
      lastSyncedProjectIdRef.current = projectId;
      setStyleChoice(presetStyle);
      setOutputRequested(false);
      setOutputDismissed(false);
      return;
    }
    if (lastSyncedProjectIdRef.current === projectId) return;
    lastSyncedProjectIdRef.current = projectId;
    setStyleChoice(customStyle.trim() ? 'custom' : presetStyle);
    setOutputRequested(false);
    setOutputDismissed(false);
  }, [projectId, customStyle, presetStyle, resetRevision]);

  // Style-choice guard: choosing a preset must clear stale custom text so hidden
  // freeform values cannot be submitted by accident.
  const handleStyleChoiceChange = (value: StyleChoice) => {
    setFormError(null);
    setStyleChoice(value);
    if (value === 'custom') return;
    setPresetStyle(value);
    setCustomStyle('');
  };

  // Suggestion-select guard: choosing a different idea should keep the user in
  // review mode and close any prior output surface for the old suggestion.
  const handleSelectCard = (index: number) => {
    setOutputRequested(false);
    setOutputDismissed(true);
    handleSelectSuggestion(index);
    const suggestion = safeSuggestions.find(sug => sug.index === index);
    if (suggestion && setTopicTypeOverride) {
      setTopicTypeOverride(suggestion.topic_type || 'fictional_original');
    }
  };

  // Manual-intake guard: the redesigned tab has one source of truth, so every
  // new suggestion request starts from the idea textarea and not legacy sources.
  const triggerSuggestions = () => {
    if (!apiKey.trim()) {
      setFormError('Vui lòng lưu App API Key trong Cài đặt trước khi sinh gợi ý.');
      return;
    }
    if (isLegacySeriesProject) {
      setFormError('Dự án này thuộc luồng chuỗi cũ. Hãy mở Chuỗi video hoặc tạo ý tưởng video đơn mới.');
      return;
    }
    if (!inputContent.trim()) {
      setFormError('Nhập ý tưởng kịch bản trước khi sinh gợi ý.');
      return;
    }
    if (isCustomStyleSelected && !customStyle.trim()) {
      setFormError('Nhập phong cách tùy chỉnh hoặc chọn một preset có sẵn.');
      return;
    }
    setFormError(null);
    void handleGenerateSuggestions(apiKey, modelName);
  };

  const handleResetClick = () => {
    setFormError(null);
    setStyleChoice('anime');
    setOutputRequested(false);
    setOutputDismissed(false);
    handleReset();
  };

  const handleReturnToIntakeClick = () => {
    setFormError(null);
    setOutputRequested(false);
    setOutputDismissed(false);
    handleReturnToSingleIntake();
  };

  const handleRestoreProject = async (project: ProjectResponse) => {
    try {
      setFormError(null);
      await handleLoadProject(apiKey, project.id);
      setOutputRequested(project.status === 'script_generated' || project.status === 'generating_script' || project.status === 'script_failed');
      setOutputDismissed(false);
    } catch (err: unknown) {
      setFormError(getErrorMessage(err, 'Lỗi khôi phục dự án.'));
    }
  };

  // Output-entry guard: phase 3 is now an inline workbench, so the CTA only
  // opens output state instead of pushing the legacy /generate route.
  const handleOpenProduction = () => {
    if (projectId !== null && selectedSuggestionIdx !== null) {
      setOutputDismissed(false);
      setOutputRequested(true);
    }
  };

  return (
    <section className="single-page" aria-labelledby="single-title">
      <header className="single-head">
        <div>
          <div className="single-title-line">
            <p className="single-kicker">Kịch bản video</p>
            <h1 id="single-title">Video đơn</h1>
          </div>
        </div>
        <div className="single-head__status" aria-label="Trạng thái video đơn">
          <span><small>Model</small><b>{modelName}</b></span>
          <span><small>Độ dài</small><b>{derivedModeLabel(numScenes)}</b></span>
          <span><small>Trạng thái</small><b>{statusLabel(status)}</b></span>
        </div>
      </header>

      {isLegacySeriesProject && (
        <div className="single-alert" role="alert">
          <div>
            <strong>Dự án chuỗi legacy</strong>
            <p>Project này lưu mode chuỗi cũ nên endpoint video đơn sẽ từ chối. Tạo ý tưởng mới hoặc mở tab Chuỗi video.</p>
          </div>
          <button type="button" className="single-action" onClick={handleResetClick}>
            Tạo mới
          </button>
        </div>
      )}

      {(formError || suggestionsError) && (
        <div className="single-alert single-alert--error" role="alert">
          <strong>Không thể tiếp tục</strong>
          <p>{formError || suggestionsError}</p>
        </div>
      )}

      <nav className="single-stepper" aria-label="Tiến trình video đơn">
        {SINGLE_STEPS.map((step) => {
          const stepState = step.id < currentPhase ? 'done' : step.id === currentPhase ? 'current' : 'upcoming';
          return (
            <div
              key={step.id}
              className="single-step"
              data-state={stepState}
              aria-current={stepState === 'current' ? 'step' : undefined}
            >
              <span className="single-step__index">{step.id}</span>
              <span className="single-step__body">
                <strong>{step.label}</strong>
                <small>{step.detail}</small>
              </span>
            </div>
          );
        })}
      </nav>

      {currentPhase === 1 ? (
        <div className="single-layout">
          <div className="single-main">
            <section className="single-panel single-intake" aria-labelledby="single-idea-title">
              <div className="single-panel__head">
                <div>
                  <h2 id="single-idea-title">Ý tưởng kịch bản</h2>
                  <p>Nhập ý tưởng mới hoặc mở lại project cũ từ Lịch sử.</p>
                </div>
                <button type="button" className="single-action" onClick={handleResetClick}>
                  Reset
                </button>
              </div>
              <textarea
                value={inputContent}
                onChange={(event) => {
                  setFormError(null);
                  setInputContent(event.target.value);
                }}
                placeholder="Ví dụ: Một nhà thám hiểm thức dậy trong thành phố ngầm, mỗi cánh cửa mở ra một ký ức bị đánh cắp..."
                className="single-textarea"
                rows={8}
              />
              <div className="single-action-row">
                <button
                  type="button"
                  className="single-action single-action--primary"
                  onClick={triggerSuggestions}
                  disabled={loadingSuggestions || isLegacySeriesProject}
                >
                  Sinh gợi ý
                </button>
                <span>{numScenes} cảnh · {sceneDuration}s/cảnh · khoảng {formatDuration(numScenes, sceneDuration)}</span>
              </div>
            </section>
          </div>

          <aside className="single-side" aria-label="Cấu hình">
            <section className="single-panel single-config" aria-labelledby="single-config-title">
              <div className="single-panel__head">
                <div>
                  <h2 id="single-config-title">Cấu hình</h2>
                  <p>Ngắn/dài được tự nhận theo số cảnh.</p>
                </div>
                <span className="single-chip">{numScenes > 20 ? 'Dài' : 'Ngắn'}</span>
              </div>

              <label className="single-field">
                <span>Phong cách dựng</span>
                <select
                  value={styleChoice}
                  onChange={(event) => handleStyleChoiceChange(event.target.value as StyleChoice)}
                >
                  {STYLE_OPTIONS.map(option => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </label>

              <label className="single-field">
                <span>Phong cách tùy chỉnh</span>
                <input
                  type="text"
                  value={customStyle}
                  onChange={(event) => setCustomStyle(event.target.value)}
                  placeholder={isCustomStyleSelected ? 'Ví dụ: austere sci-fi, glass cockpit' : 'Chọn Tùy chọn để nhập phong cách riêng'}
                  disabled={!isCustomStyleSelected}
                />
              </label>

              <label className="single-field">
                <span>Số cảnh</span>
                <select value={numScenes} onChange={(event) => setNumScenes(parseInt(event.target.value, 10))}>
                  {SCENE_OPTIONS.map(value => (
                    <option key={value} value={value}>{value} cảnh</option>
                  ))}
                </select>
              </label>

              <div className="single-field-grid">
                <label className="single-field">
                  <span>Tỉ lệ</span>
                  <select value={aspectRatio} onChange={(event) => setAspectRatio(event.target.value as AspectRatio)}>
                    <option value="16:9">16:9</option>
                    <option value="9:16">9:16</option>
                  </select>
                </label>

                <label className="single-field">
                  <span>Giây/cảnh</span>
                  <select value={sceneDuration} onChange={(event) => setSceneDuration(parseInt(event.target.value, 10))}>
                    <option value={5}>5s</option>
                    <option value={8}>8s</option>
                    <option value={10}>10s</option>
                  </select>
                </label>
              </div>
            </section>
          </aside>

          <section className="single-panel single-recent" aria-labelledby="single-recent-title">
            <div className="single-panel__head">
              <div>
                <h2 id="single-recent-title">Gần đây</h2>
                <p>3-5 dự án video đơn mới nhất.</p>
              </div>
              <button type="button" className="single-action" onClick={onNavigateToHistory}>
                Lịch sử
              </button>
            </div>

            {historyError && <div className="single-inline-error">{historyError}</div>}
            {loadingHistory && recentProjects.length === 0 ? (
              <div className="single-skeleton">Đang tải dự án gần đây...</div>
            ) : recentProjects.length === 0 ? (
              <div className="single-empty">Chưa có dự án video đơn gần đây.</div>
            ) : (
              <div className="single-recent-list">
                {recentProjects.map(project => (
                  <button
                    key={project.id}
                    type="button"
                    className="single-recent-item"
                    onClick={() => void handleRestoreProject(project)}
                  >
                    <span>
                      <strong>{project.title}</strong>
                      <small>{statusLabel(project.status)} · {project.num_scenes} cảnh · {formatDate(project.updated_at || project.created_at)}</small>
                    </span>
                  </button>
                ))}
              </div>
            )}
          </section>
        </div>
      ) : currentPhase === 3 ? (
        <SingleOutputPanel
          apiKey={apiKey}
          modelName={modelName}
          prodFlow={prodFlow}
          selectedTitle={selectedSuggestion?.title}
          autoStart
          onBack={() => {
            setOutputRequested(false);
            setOutputDismissed(true);
          }}
          backLabel="Chọn lại gợi ý"
        />
      ) : (
        <section className="single-panel single-phase single-suggestions" aria-labelledby="single-suggestions-title">
          <div className="single-panel__head">
            <div>
              <h2 id="single-suggestions-title">Chọn kịch bản gợi ý</h2>
              <p>{loadingSuggestions ? 'Đang phân tích ý tưởng và dựng 5 hướng.' : `${safeSuggestions.length} hướng đã sẵn sàng để chọn.`}</p>
            </div>
            <div className="single-phase__actions">
              {projectId && <span className="single-chip">Project #{projectId}</span>}
              <button
                type="button"
                className="single-action"
                onClick={handleReturnToIntakeClick}
                disabled={loadingSuggestions}
              >
                Quay lại sửa ý tưởng
              </button>
            </div>
          </div>

          {loadingSuggestions ? (
            <div className="single-skeleton">Đang sinh 5 kịch bản gợi ý...</div>
          ) : safeSuggestions.length === 0 ? (
            <div className="single-empty">Chưa có gợi ý. Quay lại khởi tạo để nhập ý tưởng.</div>
          ) : (
            <>
              <div className="single-suggestion-list">
                {safeSuggestions.map((suggestion) => {
                  const isSelected = selectedSuggestionIdx === suggestion.index;
                  return (
                    <button
                      key={suggestion.index}
                      type="button"
                      className={`single-suggestion ${isSelected ? 'is-selected' : ''}`}
                      onClick={() => handleSelectCard(suggestion.index)}
                    >
                      <span className="single-suggestion__index">{suggestion.index + 1}</span>
                      <span className="single-suggestion__body">
                        <strong>{suggestion.title}</strong>
                        <span>{suggestion.synopsis}</span>
                        <small>{suggestion.mood} · {suggestion.hook}</small>
                      </span>
                    </button>
                  );
                })}
              </div>

              {selectedSuggestion && (
                <div className="single-confirm-strip" aria-labelledby="single-confirm-title">
                  <div className="single-confirm-strip__copy">
                    <span>Bước 3</span>
                    <h2 id="single-confirm-title">Sinh chi tiết</h2>
                    <p>Đã chọn: {selectedSuggestion.title}</p>
                  </div>

                  <label className="single-field single-confirm-strip__field">
                    <span>Loại chủ đề</span>
                    <select
                      value={effectiveTopicType}
                      onChange={(event) => setTopicTypeOverride?.(event.target.value as TopicType)}
                    >
                      {TOPIC_TYPE_OPTIONS.map(option => (
                        <option key={option.value} value={option.value}>{option.label} - {option.detail}</option>
                      ))}
                    </select>
                  </label>

                  <button
                    type="button"
                    className="single-action single-action--primary"
                    onClick={handleOpenProduction}
                    disabled={!canOpenOutput}
                  >
                    Sinh kịch bản chi tiết
                  </button>
                </div>
              )}
            </>
          )}
        </section>
      )}
    </section>
  );
}
