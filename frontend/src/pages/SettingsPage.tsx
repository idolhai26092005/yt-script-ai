import { useState } from 'react';
import { ModelSelector } from '../components/ModelSelector';
import type { GeminiTestResponse } from '../services/api';
import { safeStorage } from '../utils/secureStorage';

interface SettingsPageProps {
  appApiKey: string;
  setAppApiKey: (v: string) => void;
  showAppKey: boolean;
  setShowAppKey: (v: boolean) => void;
  appKeyValidating: boolean;
  appKeyError: string | null;
  handleSaveAppKey: () => void;
  isAppKeySaved: boolean;
  handleClearAppKey: () => void;
  apiKey: string;
  setApiKey: (v: string) => void;
  showKey: boolean;
  setShowKey: (v: boolean) => void;
  geminiKeyValidating: boolean;
  geminiKeyError: string | null;
  handleSaveKey: (modelName?: string) => void;
  isKeySaved: boolean;
  handleClearKey: () => void;
  testPrompt: string;
  setTestPrompt: (v: string) => void;
  testLoading: boolean;
  testResult: GeminiTestResponse | null;
  handleTestConnection: (modelName?: string) => void;
  defaultModel: string;
  setDefaultModel: (v: string) => void;
  defaultLanguage: string;
  setDefaultLanguage: (v: string) => void;
}

// Visibility icon guard: key fields keep a compact icon-only toggle while the
// title text preserves accessible intent for screen readers and tooltips.
function EyeIcon({ visible }: { visible: boolean }) {
  return visible ? (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M3 3l18 18" />
      <path d="M10.6 10.6a2 2 0 002.8 2.8" />
      <path d="M9.9 5.2A10.7 10.7 0 0112 5c5 0 8.5 4.2 9.5 7a12 12 0 01-2.1 3.4" />
      <path d="M6.6 6.6A12 12 0 002.5 12c1 2.8 4.5 7 9.5 7a10.5 10.5 0 004.2-.9" />
    </svg>
  ) : (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M2.5 12c1-2.8 4.5-7 9.5-7s8.5 4.2 9.5 7c-1 2.8-4.5 7-9.5 7s-8.5-4.2-9.5-7z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

// Settings status guard: key cards share one visual contract so saved,
// validating, missing, and error states stay readable without changing storage.
function keyStatus(saved: boolean, validating: boolean, error: string | null) {
  if (validating) return { tone: 'active', label: 'Đang xác thực', detail: 'Đang kiểm tra kết nối.' };
  if (error) return { tone: 'error', label: 'Cần kiểm tra', detail: error };
  if (saved) return { tone: 'done', label: 'Đã lưu', detail: 'Đang lưu trong trình duyệt.' };
  return { tone: 'warn', label: 'Chưa lưu', detail: 'Nhập và lưu key để dùng workflow.' };
}

// Settings page guard: this tab owns credentials and defaults, so the redesign
// changes only layout/classes and preserves every existing callback contract.
export function SettingsPage({
  appApiKey, setAppApiKey, showAppKey, setShowAppKey, appKeyValidating, appKeyError, handleSaveAppKey, isAppKeySaved, handleClearAppKey,
  apiKey, setApiKey, showKey, setShowKey, geminiKeyValidating, geminiKeyError, handleSaveKey, isKeySaved, handleClearKey,
  testPrompt, setTestPrompt, testLoading, testResult, handleTestConnection,
  defaultModel, setDefaultModel, defaultLanguage, setDefaultLanguage,
}: SettingsPageProps) {
  const [defaultsSaved, setDefaultsSaved] = useState(false);
  const appStatus = keyStatus(isAppKeySaved, appKeyValidating, appKeyError);
  const geminiStatus = keyStatus(isKeySaved, geminiKeyValidating, geminiKeyError);

  // Defaults save guard: Settings no longer exposes default duration, so saving
  // this panel must not overwrite the duration used by generation workflows.
  const handleSaveDefaults = () => {
    safeStorage.setItem('DEFAULT_MODEL', defaultModel);
    safeStorage.setItem('DEFAULT_LANGUAGE', defaultLanguage);
    setDefaultsSaved(true);
    window.setTimeout(() => setDefaultsSaved(false), 2000);
  };

  return (
    <div className="settings-page">
      <header className="settings-head">
        <div>
          <p className="settings-kicker">CÀI ĐẶT</p>
          <h1>Cài đặt</h1>
        </div>
        <p>Quản lý key, model mặc định và kiểm tra kết nối.</p>
      </header>

      <div className="settings-grid">
        <section className="settings-card settings-card--keys" aria-labelledby="settings-keys-title">
          <div className="settings-card__head">
            <div>
              <p className="settings-kicker">KHÓA TRUY CẬP</p>
              <h2 id="settings-keys-title">Khóa truy cập</h2>
            </div>
          </div>

          <div className="settings-key-grid">
            <div className="settings-key-status" data-tone={appStatus.tone}>
              <span />
              <strong>App key: {appStatus.label}</strong>
              <small>{appStatus.detail}</small>
            </div>
            <div className="settings-key-status" data-tone={geminiStatus.tone}>
              <span />
              <strong>Gemini key: {geminiStatus.label}</strong>
              <small>{geminiStatus.detail}</small>
            </div>
          </div>

          <div className="settings-form">
            <label className="settings-field">
              <span>App API Key</span>
              <div className="settings-input-wrap">
                <input
                  id="settings-app-api-key"
                  type={showAppKey ? 'text' : 'password'}
                  value={appApiKey}
                  onChange={(event) => setAppApiKey(event.target.value)}
                  placeholder="yt_ai_..."
                />
                <button
                  type="button"
                  className="settings-visibility"
                  onClick={() => setShowAppKey(!showAppKey)}
                  title={showAppKey ? 'Ẩn App API Key' : 'Hiện App API Key'}
                >
                  <EyeIcon visible={showAppKey} />
                </button>
              </div>
            </label>
            <div className="settings-actions">
              <button
                id="settings-save-app-key-btn"
                type="button"
                className="settings-action settings-action--primary"
                onClick={handleSaveAppKey}
                disabled={!appApiKey.trim() || appKeyValidating}
              >
                {appKeyValidating ? 'Đang xác thực...' : 'Lưu App Key'}
              </button>
              {isAppKeySaved && (
                <button type="button" className="settings-action" onClick={handleClearAppKey}>
                  Xóa
                </button>
              )}
            </div>

            <label className="settings-field">
              <span>Gemini API Key</span>
              <div className="settings-field__label-row">
                <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener noreferrer">
                  Lấy API Key
                </a>
              </div>
              <div className="settings-input-wrap">
                <input
                  id="settings-gemini-api-key"
                  type={showKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder="AIzaSy..."
                />
                <button
                  type="button"
                  className="settings-visibility"
                  onClick={() => setShowKey(!showKey)}
                  title={showKey ? 'Ẩn Gemini API Key' : 'Hiện Gemini API Key'}
                >
                  <EyeIcon visible={showKey} />
                </button>
              </div>
            </label>
            <div className="settings-actions">
              <button
                id="settings-save-gemini-key-btn"
                type="button"
                className="settings-action settings-action--primary"
                onClick={() => handleSaveKey(defaultModel)}
                disabled={!apiKey.trim() || geminiKeyValidating}
              >
                {geminiKeyValidating ? 'Đang xác thực...' : 'Lưu Gemini Key'}
              </button>
              {isKeySaved && (
                <button type="button" className="settings-action" onClick={handleClearKey}>
                  Xóa
                </button>
              )}
            </div>
          </div>
        </section>

        <div className="settings-side">
          <section className="settings-card" aria-labelledby="settings-defaults-title">
            <div className="settings-card__head">
              <div>
                <p className="settings-kicker">MẶC ĐỊNH</p>
                <h2 id="settings-defaults-title">Mặc định workflow</h2>
              </div>
            </div>
            <div className="settings-form">
              <label className="settings-field">
                <span>Model mặc định</span>
                <ModelSelector selectedModel={defaultModel} onModelChange={setDefaultModel} />
              </label>
              <label className="settings-field">
                <span>Ngôn ngữ mặc định</span>
                <select
                  id="settings-default-language"
                  value={defaultLanguage}
                  onChange={(event) => setDefaultLanguage(event.target.value)}
                >
                  <option value="bilingual">Song ngữ</option>
                  <option value="vi">Tiếng Việt</option>
                  <option value="en">Tiếng Anh</option>
                  <option value="zh">Tiếng Trung</option>
                  <option value="ja">Tiếng Nhật</option>
                  <option value="ko">Tiếng Hàn</option>
                  <option value="fr">Tiếng Pháp</option>
                  <option value="es">Tiếng Tây Ban Nha</option>
                  <option value="de">Tiếng Đức</option>
                </select>
              </label>
              <button
                id="settings-save-defaults-btn"
                type="button"
                className="settings-action settings-action--primary"
                onClick={handleSaveDefaults}
              >
                {defaultsSaved ? 'Đã lưu' : 'Lưu mặc định'}
              </button>
            </div>
          </section>

          {isKeySaved && (
            <section className="settings-card" aria-labelledby="settings-test-title">
              <div className="settings-card__head">
                <div>
                  <p className="settings-kicker">KIỂM TRA</p>
                  <h2 id="settings-test-title">Kiểm tra Gemini</h2>
                </div>
              </div>
              <div className="settings-form">
                <label className="settings-field">
                  <span>Prompt thử</span>
                  <textarea
                    id="settings-test-prompt"
                    rows={3}
                    value={testPrompt}
                    onChange={(event) => setTestPrompt(event.target.value)}
                    placeholder="Nhập prompt để kiểm tra kết nối Gemini..."
                  />
                </label>
                <button
                  id="settings-test-connection-btn"
                  type="button"
                  className="settings-action"
                  onClick={() => handleTestConnection(defaultModel)}
                  disabled={testLoading || !testPrompt.trim()}
                >
                  {testLoading ? 'Đang kết nối...' : 'Gửi prompt thử'}
                </button>
                {testResult && (
                  <div className="settings-test-result" data-success={testResult.success}>
                    <strong>{testResult.success ? 'Kết nối thành công' : 'Kết nối lỗi'}</strong>
                    <pre>{testResult.success ? testResult.response : testResult.error}</pre>
                  </div>
                )}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
