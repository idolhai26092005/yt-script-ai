import { useEffect, useMemo, useRef, useState } from 'react';
import type { useProductionFlow } from '../hooks/useProductionFlow';
import type { CharacterPrompt, EmotionArcEntry, SceneScript, ScriptOutput } from '../services/api';
import { formatStepName } from '../utils/format';

type ProductionFlow = ReturnType<typeof useProductionFlow>;
type SceneTab = 'overview' | 'prompt' | 'negative' | 'notes';
type ArtifactTab = 'plan' | 'prompt0' | 'characters' | 'environment' | 'continuity' | 'reference';

interface SingleOutputPanelProps {
  apiKey: string;
  modelName: string;
  prodFlow: ProductionFlow;
  selectedTitle?: string;
  autoStart?: boolean;
  onBack?: () => void;
  backLabel?: string;
}

interface Prompt0CharacterLock {
  name?: unknown;
  description_en?: unknown;
}

const SCENE_TABS: Array<{ value: SceneTab; label: string }> = [
  { value: 'overview', label: 'Tổng quan' },
  { value: 'prompt', label: 'Veo prompt' },
  { value: 'negative', label: 'Negative' },
  { value: 'notes', label: 'Ghi chú' },
];

const ARTIFACT_TABS: Array<{ value: ArtifactTab; label: string }> = [
  { value: 'plan', label: 'Kế hoạch' },
  { value: 'prompt0', label: 'Prompt 0' },
  { value: 'characters', label: 'Nhân vật' },
  { value: 'environment', label: 'Môi trường' },
  { value: 'continuity', label: 'Continuity' },
  { value: 'reference', label: 'Tham khảo' },
];

// Text-format guard: production artifacts can contain unknown JSON shapes, so the
// output panel normalizes only strings before exposing copyable prompt text.
function textValue(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

// Prompt-0 guard: character locks are optional records from backend JSON, and
// this narrow check prevents unsafe property reads in the shared output panel.
function isPrompt0CharacterLock(value: unknown): value is Prompt0CharacterLock {
  return typeof value === 'object' && value !== null;
}

// Prompt-0 formatter guard: keep the full continuity board copyable without
// rendering raw JSON noise in the operator-facing output tab.
function formatPrompt0(prompt0: unknown): string {
  if (!prompt0 || typeof prompt0 !== 'object') return '';
  const p0 = prompt0 as Record<string, unknown>;
  const lines: string[] = ['Prompt 0', 'Identity / Species Lock', ''];

  if (textValue(p0.primary_subject_en)) lines.push(`Primary Subject: ${textValue(p0.primary_subject_en)}`, '');
  if (textValue(p0.hard_visual_lock_en)) lines.push('Hard Visual / Form Lock', textValue(p0.hard_visual_lock_en), '');
  if (textValue(p0.setting_lock_en)) lines.push('Setting / Habitat / World Lock', textValue(p0.setting_lock_en), '');
  if (Array.isArray(p0.character_lock)) {
    p0.character_lock.filter(isPrompt0CharacterLock).forEach((c) => {
      lines.push(`Character Lock - ${textValue(c.name)}`, textValue(c.description_en), '');
    });
  }
  if (textValue(p0.camera_lock_en)) lines.push('Camera Lock', textValue(p0.camera_lock_en), '');
  if (textValue(p0.voice_sound_lock_en)) lines.push('Voice / Sound Lock', textValue(p0.voice_sound_lock_en), '');
  if (textValue(p0.action_story_logic_en)) lines.push('Action / Story Logic', textValue(p0.action_story_logic_en), '');
  if (textValue(p0.scene_function_rules_en)) lines.push('Scene Function Rules', textValue(p0.scene_function_rules_en), '');
  if (textValue(p0.continuity_lock_en)) lines.push('Continuity Lock', textValue(p0.continuity_lock_en), '');
  if (textValue(p0.internal_logic_en)) lines.push('Internal Logic', textValue(p0.internal_logic_en), '');
  if (textValue(p0.negative_constraints_en)) lines.push('Negative Constraints', textValue(p0.negative_constraints_en), '');

  return lines.join('\n').trim();
}

// Plan formatter guard: the full-script copy path depends on a stable production
// plan order even though individual sections arrive incrementally over SSE.
function formatProductionPlan(scriptOutput: ScriptOutput): string {
  const sections: Array<[string, string | undefined]> = [
    ['Mạch câu chuyện', scriptOutput.storyline_vi || scriptOutput.overview_analysis_vi],
    ['Phân chia giai đoạn', scriptOutput.stages_vi],
    ['Tiến trình cảnh', scriptOutput.progression_vi],
    ['Chiến lược Camera', scriptOutput.camera_strategy_vi],
    ['Continuity Locks', scriptOutput.continuity_locks_vi],
    ['Hard Visual / Form Locks', scriptOutput.form_locks_vi],
    ['Age-Stage Locks', scriptOutput.age_stage_locks_vi],
    ['Main Location / Habitat Geometry', scriptOutput.geometry_locks_vi],
    ['Risk Logic', scriptOutput.risk_logic_vi],
    ['Voice / Sound Strategy', scriptOutput.voice_sound_strategy_vi],
  ];

  const lines = ['BẢN KẾ HOẠCH SẢN XUẤT', ''];
  sections.forEach(([title, value]) => {
    if (value) lines.push(title, '', value, '');
  });
  return lines.join('\n').trim();
}

// Full-copy guard: users expect one payload that matches the legacy sample
// format, while the visible UI is now split into navigator/detail tabs.
function formatSampleScript(scriptOutput: ScriptOutput): string {
  const plan = formatProductionPlan(scriptOutput);
  const prompt0 = formatPrompt0(scriptOutput.prompt_0);
  const scenes = (scriptOutput.scenes || [])
    .slice()
    .sort((a, b) => a.scene_number - b.scene_number)
    .map((scene) => `scene ${scene.scene_number}: ${scene.veo3_prompt_en}`)
    .join('\n\n');

  return [plan, prompt0, scenes].filter(Boolean).join('\n\n');
}

// Preview guard: the scene navigator stays compact while the detail panel keeps
// full action and prompt text available for copy/review.
function scenePreview(scene: SceneScript): string {
  return scene.action_detail_vi || scene.voice_over_vi || scene.voice_over_en || scene.veo3_prompt_en || 'Chưa có mô tả cảnh.';
}

// Status-label guard: stream groups are backend-oriented names, so the UI maps
// them to short operator labels without changing the stream contract.
function streamGroupLabel(group: string): string {
  if (group === 'metadata') return 'Cấu trúc & nhân vật';
  if (group === 'scenes') return 'Phân cảnh chi tiết';
  if (group === 'global') return 'Prompts bổ trợ';
  if (group === 'done') return 'Hoàn tất';
  return 'Đang xử lý';
}

// Topic badge guard: Single output keeps topic-type context visible without
// reintroducing the emoji-heavy production chrome.
function topicTypeLabel(type?: ScriptOutput['topic_type'] | ProductionFlow['topicTypeOverride']): string {
  switch (type) {
    case 'historical':
      return 'Lịch sử';
    case 'scientific':
      return 'Khoa học';
    case 'fictional_mythology':
      return 'Thần thoại';
    case 'fictional_original':
      return 'Sáng tác gốc';
    default:
      return 'Chưa phân loại';
  }
}

// Artifact-content guard: tabs must preserve every production artifact while
// avoiding the old long vertical stack of independent cards.
function getArtifactContent(scriptOutput: ScriptOutput | null, tab: ArtifactTab): string {
  if (!scriptOutput) return '';
  if (tab === 'plan') return formatProductionPlan(scriptOutput);
  if (tab === 'prompt0') return formatPrompt0(scriptOutput.prompt_0);
  if (tab === 'characters') {
    return (scriptOutput.characters || [])
      .map((char: CharacterPrompt) => [
        char.character_name,
        char.description_vi,
        char.description_en,
        char.key_identifiers_en ? `Key identifiers: ${char.key_identifiers_en}` : '',
      ].filter(Boolean).join('\n'))
      .join('\n\n');
  }
  if (tab === 'environment') return scriptOutput.environment_master_prompt_en || '';
  if (tab === 'continuity') {
    return [
      scriptOutput.continuity_prompt_en && `Continuity Prompt\n${scriptOutput.continuity_prompt_en}`,
      scriptOutput.global_negative_prompt_en && `Global Negative Prompt\n${scriptOutput.global_negative_prompt_en}`,
    ].filter(Boolean).join('\n\n');
  }
  if (tab === 'reference') {
    const refs = scriptOutput.reference_images;
    if (!refs) return '';
    return [
      refs.character_ref_prompt_en && `Character Reference\n${refs.character_ref_prompt_en}`,
      refs.background_ref_prompt_en && `Background Reference\n${refs.background_ref_prompt_en}`,
      refs.thumbnail_ref_prompt_en && `Thumbnail Reference\n${refs.thumbnail_ref_prompt_en}`,
    ].filter(Boolean).join('\n\n');
  }
  return '';
}

// Output workbench guard: SinglePage and legacy /generate share one production
// surface so scene navigation, copy behavior, and stream autostart cannot drift.
export function SingleOutputPanel({
  apiKey,
  modelName,
  prodFlow,
  selectedTitle,
  autoStart = true,
  onBack,
  backLabel = 'Quay lai',
}: SingleOutputPanelProps) {
  const {
    projectId,
    scriptOutput,
    emotionArc,
    status,
    generatingScript,
    generationError,
    streamProgress,
    presetStyle,
    customStyle,
    numScenes,
    sceneDuration,
    selectedSuggestionIdx,
    topicTypeOverride,
    suggestions,
    handleStartScriptGeneration,
  } = prodFlow;

  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [selectedSceneIdx, setSelectedSceneIdx] = useState(0);
  const [sceneTab, setSceneTab] = useState<SceneTab>('overview');
  const [artifactTab, setArtifactTab] = useState<ArtifactTab>('plan');
  const sceneSelectionPinnedRef = useRef(false);
  const prevProjectIdRef = useRef<number | null>(projectId);
  const prevSceneCountRef = useRef(0);

  const scenes = useMemo(
    () => (scriptOutput?.scenes || []).slice().sort((a, b) => a.scene_number - b.scene_number),
    [scriptOutput?.scenes],
  );
  const activeSceneIdx = scenes.length ? Math.min(selectedSceneIdx, scenes.length - 1) : 0;
  const selectedScene = scenes[activeSceneIdx] || null;
  const selectedSuggestionTitle = selectedTitle || suggestions.find(sug => sug.index === selectedSuggestionIdx)?.title;
  const outputTitle = selectedSuggestionTitle || (projectId ? `Kịch bản dự án #${projectId}` : 'Kịch bản video đơn');
  const hasContent = Boolean(scriptOutput && (
    scriptOutput.overview_analysis_vi ||
    (scriptOutput.characters || []).length > 0 ||
    scenes.length > 0
  ));
  const isRecoverable = !generatingScript && (status === 'generating_script' || status === 'script_failed');
  const activeArtifactText = getArtifactContent(scriptOutput, artifactTab);

  // Autostart guard: opening phase 3 should resume the legacy ProductionPage
  // behavior exactly once, while cached/generated projects stay read-only.
  useEffect(() => {
    if (!autoStart) return;
    if (projectId !== null && status === 'suggestions_generated' && !generatingScript && !scriptOutput?.overview_analysis_vi) {
      void handleStartScriptGeneration(apiKey, modelName);
    }
  }, [autoStart, projectId, status, generatingScript, scriptOutput, apiKey, modelName, handleStartScriptGeneration]);

  // Scene-selection guard: during streaming, follow the newest scene until the
  // operator manually pins a different scene for review.
  useEffect(() => {
    if (prevProjectIdRef.current !== projectId) {
      prevProjectIdRef.current = projectId;
      sceneSelectionPinnedRef.current = false;
      prevSceneCountRef.current = scenes.length;
      setSelectedSceneIdx(scenes.length ? scenes.length - 1 : 0);
      setSceneTab('overview');
      setArtifactTab('plan');
      return;
    }

    if (scenes.length > prevSceneCountRef.current && !sceneSelectionPinnedRef.current) {
      setSelectedSceneIdx(scenes.length - 1);
    }
    prevSceneCountRef.current = scenes.length;
  }, [projectId, scenes.length]);

  // Copy-feedback guard: all copy commands share one short-lived key so buttons
  // can acknowledge success without adding global toast state.
  const handleCopyToClipboard = async (text: string, key: string) => {
    if (!text) return;
    await navigator.clipboard.writeText(text);
    setCopiedKey(key);
    window.setTimeout(() => setCopiedKey(null), 2200);
  };

  // Manual-pin guard: selecting a scene stops automatic stream-follow so a long
  // generation cannot yank the operator away from the scene being inspected.
  const handleSelectScene = (index: number) => {
    sceneSelectionPinnedRef.current = true;
    setSelectedSceneIdx(index);
    setSceneTab('overview');
  };

  return (
    <section className="single-output" aria-labelledby="single-output-title">
      <div className="single-output__head">
        <div className="single-output__title">
          <p className="single-kicker">Xem & chỉnh sửa</p>
          <h2 id="single-output-title">{outputTitle}</h2>
          <div className="single-output__meta">
            <span>{topicTypeLabel(scriptOutput?.topic_type || topicTypeOverride)}</span>
            <span>{customStyle || presetStyle}</span>
            <span>{numScenes} cảnh</span>
            <span>{sceneDuration}s/cảnh</span>
          </div>
        </div>
        <div className="single-output__actions">
          {onBack && (
            <button className="single-action" type="button" onClick={onBack} disabled={generatingScript}>
              {backLabel}
            </button>
          )}
          <button
            className="single-action"
            type="button"
            onClick={() => scriptOutput && void handleCopyToClipboard(formatSampleScript(scriptOutput), 'full_script')}
            disabled={!scriptOutput}
          >
            {copiedKey === 'full_script' ? 'Đã sao chép' : 'Sao chép toàn bộ'}
          </button>
          {status === 'suggestions_generated' && !generatingScript && !hasContent && (
            <button
              className="single-action single-action--primary"
              type="button"
              onClick={() => void handleStartScriptGeneration(apiKey, modelName)}
            >
              Bắt đầu sinh
            </button>
          )}
        </div>
      </div>

      {(generatingScript || streamProgress.group !== 'idle') && (
        <div className="single-output-progress">
          <div>
            <span>{streamGroupLabel(streamProgress.group)}</span>
            <strong>{streamProgress.percent}%</strong>
          </div>
          <div className="single-output-progress__bar" aria-label="Tiến độ sinh kịch bản">
            <span style={{ width: `${Math.max(0, Math.min(100, streamProgress.percent))}%` }} />
          </div>
          <p>{formatStepName(streamProgress.step, numScenes)}</p>
        </div>
      )}

      {generationError && (
        <div className="single-alert single-alert--error" role="alert">
          <div>
            <strong>Stream bị lỗi</strong>
            <p>{generationError}</p>
          </div>
          <button
            type="button"
            className="single-action"
            onClick={() => void handleStartScriptGeneration(apiKey, modelName)}
            disabled={generatingScript}
            hidden={isRecoverable}
          >
            Thử lại
          </button>
        </div>
      )}

      {isRecoverable && (
        <div className="single-alert" role="status">
          <div>
            <strong>{status === 'script_failed' ? 'Lần sinh trước bị lỗi' : 'Project đang sinh dở'}</strong>
            <p>Tiếp tục sẽ dùng artifact đã lưu; sinh lại từ đầu sẽ giữ gợi ý đã chọn nhưng bỏ output cũ.</p>
          </div>
          <div className="single-output__actions">
            <button
              type="button"
              className="single-action single-action--primary"
              onClick={() => void handleStartScriptGeneration(apiKey, modelName, { restart: false })}
            >
              Tiếp tục sinh
            </button>
            <button
              type="button"
              className="single-action"
              onClick={() => void handleStartScriptGeneration(apiKey, modelName, { restart: true })}
            >
              Sinh lại từ đầu
            </button>
          </div>
        </div>
      )}

      {!hasContent && !generatingScript ? (
        <div className="single-output-empty">
          <h3>Chưa có output chi tiết</h3>
          <p>{isRecoverable ? 'Dùng nút recovery phía trên để tiếp tục hoặc sinh lại.' : 'Bắt đầu sinh để nhận kế hoạch sản xuất, cảnh và prompt.'}</p>
          {!isRecoverable && (
            <button
              type="button"
              className="single-action single-action--primary"
              onClick={() => void handleStartScriptGeneration(apiKey, modelName)}
            >
              Sinh kịch bản chi tiết
            </button>
          )}
        </div>
      ) : (
        <>
          {emotionArc.length > 0 && (
            <div className="single-emotion-strip" aria-label="Mạch cảm xúc">
              {emotionArc.map((entry: EmotionArcEntry) => (
                <button
                  key={entry.scene_number}
                  type="button"
                  className={scenes[activeSceneIdx]?.scene_number === entry.scene_number ? 'is-active' : ''}
                  onClick={() => {
                    const sceneIndex = scenes.findIndex(scene => scene.scene_number === entry.scene_number);
                    if (sceneIndex >= 0) handleSelectScene(sceneIndex);
                  }}
                >
                  <span>{String(entry.scene_number).padStart(2, '0')}</span>
                  <strong>{entry.emotion_label}</strong>
                  <small>{entry.camera_complexity}</small>
                </button>
              ))}
            </div>
          )}

          <div className="single-output-workbench">
            <div className="single-scene-nav" aria-label="Danh sách cảnh">
              {scenes.length === 0 ? (
                <p>Đang đợi cảnh đầu tiên...</p>
              ) : scenes.map((scene, index) => {
                const isFailed = scene.generation_failed === true || scene.generation_failed === 'true';
                return (
                  <button
                    key={`${scene.scene_number}-${scene.title || 'scene'}`}
                    type="button"
                    className={`single-scene-row ${activeSceneIdx === index ? 'is-active' : ''}`}
                    onClick={() => handleSelectScene(index)}
                    aria-pressed={activeSceneIdx === index}
                  >
                    <span>{String(scene.scene_number || index + 1).padStart(2, '0')}</span>
                    <strong>{scene.title || 'Untitled scene'}</strong>
                    <small>{scenePreview(scene).slice(0, 105)}</small>
                    <em>{isFailed ? 'Lỗi' : scene.needs_fact_check ? 'Fact' : scene.veo3_prompt_en ? 'Prompt' : 'Nháp'}</em>
                  </button>
                );
              })}
            </div>

            <article className="single-scene-detail">
              {selectedScene ? (
                <>
                  <header>
                    <div>
                      <span>{String(selectedScene.scene_number || activeSceneIdx + 1).padStart(2, '0')}</span>
                      <h3>{selectedScene.title || 'Untitled scene'}</h3>
                    </div>
                    <button
                      className="single-action"
                      type="button"
                      onClick={() => void handleCopyToClipboard(selectedScene.veo3_prompt_en || '', `scene_${activeSceneIdx}`)}
                      disabled={!selectedScene.veo3_prompt_en}
                    >
                      {copiedKey === `scene_${activeSceneIdx}` ? 'Đã sao chép' : 'Sao chép prompt'}
                    </button>
                  </header>

                  <div className="single-tablist single-tablist--scene" role="tablist" aria-label="Scene detail tabs">
                    {SCENE_TABS.map(tab => (
                      <button
                        key={tab.value}
                        type="button"
                        role="tab"
                        aria-selected={sceneTab === tab.value}
                        className={`single-tab ${sceneTab === tab.value ? 'is-active' : ''}`}
                        onClick={() => setSceneTab(tab.value)}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>

                  {sceneTab === 'overview' && (
                    <div className="single-scene-pane">
                      {selectedScene.action_detail_vi && <p>{selectedScene.action_detail_vi}</p>}
                      {(selectedScene.voice_over_en || selectedScene.voice_over_vi) && (
                        <blockquote>{selectedScene.voice_over_en || selectedScene.voice_over_vi}</blockquote>
                      )}
                      <div className="single-scene-grid">
                        {selectedScene.camera_movement_vi && <section><strong>Camera</strong><p>{selectedScene.camera_movement_vi}</p></section>}
                        {selectedScene.emotion_gesture_vi && <section><strong>Cảm xúc / cử chỉ</strong><p>{selectedScene.emotion_gesture_vi}</p></section>}
                        {selectedScene.transition_to_next_vi && <section><strong>Chuyển cảnh</strong><p>{selectedScene.transition_to_next_vi}</p></section>}
                        {selectedScene.veo3_prompt_vi && <section><strong>Giải thích prompt (VI)</strong><p>{selectedScene.veo3_prompt_vi}</p></section>}
                      </div>
                    </div>
                  )}

                  {sceneTab === 'prompt' && (
                    <div className="single-scene-pane">
                      <pre>{selectedScene.veo3_prompt_en || 'Chưa có Veo prompt.'}</pre>
                    </div>
                  )}

                  {sceneTab === 'negative' && (
                    <div className="single-scene-pane">
                      <pre>{[
                        selectedScene.negative_prompt_en && `Negative Prompt\n${selectedScene.negative_prompt_en}`,
                        selectedScene.scene_specific_negative_en && `Scene Specific Negative\n${selectedScene.scene_specific_negative_en}`,
                      ].filter(Boolean).join('\n\n') || 'Chưa có negative prompt.'}</pre>
                    </div>
                  )}

                  {sceneTab === 'notes' && (
                    <div className="single-scene-pane">
                      {selectedScene.generation_failed && (
                        <section className="single-note single-note--error">
                          <strong>Lỗi sinh cảnh</strong>
                          <p>{selectedScene.generation_error || 'Backend trả về lỗi khi sinh cảnh này.'}</p>
                        </section>
                      )}
                      {selectedScene.needs_fact_check && (
                        <section className="single-note">
                          <strong>Cần fact-check</strong>
                          <p>{selectedScene.fact_check_note_vi || 'Cần xác minh lại nội dung cảnh này.'}</p>
                        </section>
                      )}
                      {selectedScene.historical_basis_vi && (
                        <section className="single-note">
                          <strong>Cơ sở lịch sử / khoa học</strong>
                          <p>{selectedScene.historical_basis_vi}</p>
                        </section>
                      )}
                      {!selectedScene.generation_failed && !selectedScene.needs_fact_check && !selectedScene.historical_basis_vi && (
                        <p>Không có ghi chú riêng cho cảnh này.</p>
                      )}
                    </div>
                  )}
                </>
              ) : (
                <p>Chọn một cảnh để xem chi tiết.</p>
              )}
            </article>
          </div>

          <div className="single-artifact-tabs">
            <div className="single-tablist" role="tablist" aria-label="Production artifact tabs">
              {ARTIFACT_TABS.map(tab => (
                <button
                  key={tab.value}
                  type="button"
                  role="tab"
                  aria-selected={artifactTab === tab.value}
                  className={`single-tab ${artifactTab === tab.value ? 'is-active' : ''}`}
                  onClick={() => setArtifactTab(tab.value)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="single-artifact-pane">
              <div className="single-artifact-pane__head">
                <strong>{ARTIFACT_TABS.find(tab => tab.value === artifactTab)?.label}</strong>
                <button
                  type="button"
                  className="single-action"
                  onClick={() => void handleCopyToClipboard(activeArtifactText, `artifact_${artifactTab}`)}
                  disabled={!activeArtifactText}
                >
                  {copiedKey === `artifact_${artifactTab}` ? 'Đã sao chép' : 'Sao chép'}
                </button>
              </div>
              <pre>{activeArtifactText || 'Artifact này chưa có dữ liệu.'}</pre>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
