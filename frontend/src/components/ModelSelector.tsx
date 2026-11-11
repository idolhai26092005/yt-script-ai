import React, { useCallback, useEffect, useRef, useState } from 'react';
import { fetchAvailableModels, getErrorMessage } from '../services/api';
import type { ModelInfo } from '../services/api';

interface ModelSelectorProps {
  selectedModel: string;
  onModelChange: (modelId: string) => void;
  className?: string;
}

// Quota tone guard: model usage bars stay semantic without leaking Tailwind
// utility colors back into the token-based settings redesign.
function quotaTone(remaining: number, total: number): 'ok' | 'warn' | 'danger' | 'idle' {
  if (total <= 0) return 'idle';
  const percent = (remaining / total) * 100;
  if (percent > 50) return 'ok';
  if (percent > 20) return 'warn';
  return 'danger';
}

// Model selector guard: settings owns the current default model, while this
// component only presents available quota states and keeps old callback wiring.
export const ModelSelector: React.FC<ModelSelectorProps> = ({
  selectedModel,
  onModelChange,
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Outside-click guard: the custom popover should close like a native select
  // without changing the selected model or refetching model data.
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Model loading guard: manual refresh and mount share one fetch path so quota
  // errors appear in the dropdown instead of breaking Settings render.
  const loadModels = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const res = await fetchAvailableModels();
      if (res.success) {
        setModels(res.models);
      } else {
        setError(res.error || 'Khong the tai danh sach model');
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Loi ket noi khi tai model'));
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  // Mount fetch guard: defer one tick to avoid competing with parent Settings
  // mount work while still showing fresh quota when the panel opens.
  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadModels();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadModels]);

  const currentModel = models.find((model) => model.id === selectedModel);
  const fastModels = models.filter((model) => model.group === 'fast');
  const qualityModels = models.filter((model) => model.group === 'quality');
  const backupModels = models.filter((model) => model.group === 'backup' || model.group === 'fallback');
  const hasNonPopularModels = models.some((model) => !model.popular);

  const shouldShowModel = (model: ModelInfo) => {
    if (showAll) return true;
    return model.popular || model.id === selectedModel;
  };

  const handleRefresh = (event: React.MouseEvent) => {
    event.stopPropagation();
    void loadModels();
  };

  const renderModelItem = (model: ModelInfo) => {
    const isSelected = model.id === selectedModel;
    const isExhausted = model.status === 'exhausted' || model.remaining_rpd <= 0;
    const isCooldown = model.status === 'cooldown';
    const isDisabled = isExhausted || isCooldown;
    const percent = model.rpd > 0 ? Math.max(0, Math.min(100, (model.remaining_rpd / model.rpd) * 100)) : 0;

    return (
      <button
        key={model.id}
        type="button"
        disabled={isDisabled}
        onClick={() => {
          onModelChange(model.id);
          setIsOpen(false);
        }}
        className="model-selector__item"
        data-selected={isSelected}
      >
        <span className="model-selector__item-head">
          <span className="model-selector__item-main">
            <strong>{model.display_name}</strong>
            <small>{model.id}</small>
          </span>
          <span className="model-selector__status">
            {isExhausted ? 'Het luot' : isCooldown ? 'Cooldown' : `Con ${model.remaining_rpd}/${model.rpd}`}
          </span>
        </span>
        <span className="model-selector__description">{model.description}</span>
        <span className="model-selector__bar" aria-hidden="true">
          <span
            className="model-selector__bar-fill"
            data-tone={quotaTone(model.remaining_rpd, model.rpd)}
            style={{ width: `${percent}%` }}
          />
        </span>
      </button>
    );
  };

  const renderGroup = (title: string, groupModels: ModelInfo[]) => {
    const visibleModels = groupModels.filter(shouldShowModel);
    if (visibleModels.length === 0) return null;

    return (
      <div className="model-selector__group">
        <span className="model-selector__group-label">{title}</span>
        <div className="model-selector__items">{visibleModels.map(renderModelItem)}</div>
      </div>
    );
  };

  return (
    <div className={`model-selector ${className}`} ref={dropdownRef}>
      <div className="model-selector__trigger-row">
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="model-selector__trigger"
          aria-expanded={isOpen}
        >
          <span className="model-selector__trigger-main">
            <small>Mo hinh AI</small>
            <strong>{currentModel?.display_name || selectedModel}</strong>
          </span>
          <span className="model-selector__trigger-meta">
            {currentModel ? (
              currentModel.remaining_rpd <= 0 ? 'Het luot' : `${currentModel.remaining_rpd}/${currentModel.rpd}`
            ) : (
              'Dang tai'
            )}
          </span>
          <svg className={isOpen ? 'is-open' : ''} aria-hidden="true" viewBox="0 0 24 24">
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={loading}
          title="Lam moi quota"
          className="model-selector__refresh"
        >
          <svg aria-hidden="true" viewBox="0 0 24 24">
            <path d="M20 11a8 8 0 10-2.3 5.7" />
            <path d="M20 4v7h-7" />
          </svg>
        </button>
      </div>

      {isOpen && (
        <div className="model-selector__dropdown">
          <div className="model-selector__dropdown-head">
            <strong>Chon model kha dung</strong>
            <button type="button" onClick={handleRefresh} disabled={loading}>
              Lam moi
            </button>
          </div>

          <div className="model-selector__list">
            {loading && models.length === 0 ? (
              <div className="model-selector__state">Dang dong bo danh sach...</div>
            ) : error && models.length === 0 ? (
              <div className="model-selector__state model-selector__state--error">
                <span>{error}</span>
                <button type="button" onClick={() => void loadModels()}>
                  Thu lai
                </button>
              </div>
            ) : (
              <>
                {renderGroup('Nhanh', fastModels)}
                {renderGroup('Chat luong', qualityModels)}
                {renderGroup('Du phong', backupModels)}
                {hasNonPopularModels && (
                  <button type="button" className="model-selector__more" onClick={() => setShowAll(!showAll)}>
                    {showAll ? 'Thu gon danh sach' : 'Xem them model'}
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
