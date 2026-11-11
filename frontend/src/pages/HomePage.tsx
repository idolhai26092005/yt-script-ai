type KeyTone = 'ready' | 'warning' | 'error' | 'loading';

interface HomePageProps {
  appKeySaved: boolean;
  appKeyValidating: boolean;
  appKeyError: string | null;
  geminiKeySaved: boolean;
  geminiKeyValidating: boolean;
  geminiKeyError: string | null;
  modelName: string;
  defaultLanguage: string;
  onNavigateSingle: () => void;
  onNavigateSeries: () => void;
  onNavigateHistory: () => void;
  onNavigateSettings: () => void;
}

interface KeyState {
  tone: KeyTone;
  label: string;
  detail: string;
}

// Header metadata guard: stored defaults can be terse internal values, but
// Home should read as operator-facing text without changing persisted settings.
function displayLanguageLabel(value: string): string {
  switch (value.trim().toLowerCase()) {
    case 'vi':
      return 'Tiếng Việt';
    case 'en':
      return 'English';
    case 'bilingual':
      return 'Song ngữ';
    default:
      return value || 'Chưa chọn';
  }
}

// Key-state guard: Home mirrors saved/validating/error state without issuing
// background validation requests when the user lands on the dashboard.
// Review trim guard: saved keys stay neutral as "da luu" so Home avoids a
// redundant ready banner while still showing the connection state.
function keyStateLabel(name: string, saved: boolean, validating: boolean, error: string | null): KeyState {
  if (validating) {
    return { tone: 'loading', label: `${name}: đang xác thực`, detail: 'Đợi kiểm tra từ Cài đặt hoàn tất.' };
  }
  if (error) {
    return { tone: 'error', label: `${name}: lỗi`, detail: error };
  }
  if (!saved) {
    return { tone: 'warning', label: `${name}: chưa lưu`, detail: 'Mở Cài đặt để nhập và lưu key.' };
  }
  return { tone: 'ready', label: `${name}: đã lưu`, detail: 'Đã lưu trong trình duyệt.' };
}

// Home page guard: this dashboard is navigation and status only; it does not
// reset drafts, ping keys, or start generation on mount.
// Review trim guard: Home remains a compact hub; recent work resumes through
// History, not through session-only draft or topic shortcut panels.
// Metadata trim guard: duration stays in workflow settings, while Home shows
// only routing-relevant defaults to keep the header compact.
export function HomePage({
  appKeySaved,
  appKeyValidating,
  appKeyError,
  geminiKeySaved,
  geminiKeyValidating,
  geminiKeyError,
  modelName,
  defaultLanguage,
  onNavigateSingle,
  onNavigateSeries,
  onNavigateHistory,
  onNavigateSettings,
}: HomePageProps) {
  const appState = keyStateLabel('App key', appKeySaved, appKeyValidating, appKeyError);
  const geminiState = keyStateLabel('Gemini key', geminiKeySaved, geminiKeyValidating, geminiKeyError);
  const hasKeyAlert = appState.tone !== 'ready' || geminiState.tone !== 'ready';
  const alertTone = [appState, geminiState].some(state => state.tone === 'error')
    ? 'error'
    : [appState, geminiState].some(state => state.tone === 'loading')
      ? 'loading'
      : 'warning';

  return (
    <section className="home-page" aria-labelledby="home-title">
      <header className="home-head">
        <div className="home-head__copy">
          <p className="home-kicker">Bảng điều khiển</p>
          <h1 id="home-title">ScriptForge AI</h1>
          <p>Điểm vào gọn cho video đơn, chuỗi video, lịch sử và cấu hình key.</p>
        </div>
        <div className="home-head__status" aria-label="Cấu hình mặc định">
          <span>
            <small>Model</small>
            <b>{modelName}</b>
          </span>
          <span>
            <small>Ngôn ngữ</small>
            <b>{displayLanguageLabel(defaultLanguage)}</b>
          </span>
        </div>
      </header>

      <div className="home-status-grid" aria-label="API key status">
        {[appState, geminiState].map(state => (
          <div key={state.label} className={`home-status home-status--${state.tone}`}>
            <span className="home-status__dot" aria-hidden="true" />
            <div>
              <strong>{state.label}</strong>
              <p>{state.detail}</p>
            </div>
          </div>
        ))}
      </div>

      {hasKeyAlert && (
        <div className="home-alert" data-tone={alertTone} role="alert">
          <div>
            <strong>Cần kiểm tra key trước khi sinh</strong>
            <p>Trang chủ không tự ping key. Trạng thái này lấy từ lần lưu hoặc kiểm tra gần nhất trong Cài đặt.</p>
          </div>
          <button type="button" className="home-action home-action--primary" onClick={onNavigateSettings}>
            Mở Cài đặt
          </button>
        </div>
      )}

      <div className="home-command-grid" aria-label="Lối tắt chính">
        <button type="button" className="home-command" data-variant="primary" onClick={onNavigateSingle}>
          <span className="home-command__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M6 5h12v14H6zM9 9h6M9 13h4" />
            </svg>
          </span>
          <strong>Video đơn</strong>
          <p>Viết ý tưởng, cấu hình cảnh, sinh gợi ý.</p>
          <span className="home-command__cue">Bắt đầu</span>
        </button>
        <button type="button" className="home-command" data-variant="secondary" onClick={onNavigateSeries}>
          <span className="home-command__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M5 7h14M7 12h10M9 17h6" />
            </svg>
          </span>
          <strong>Chuỗi video</strong>
          <p>Tạo hoặc mở lại workbench chuỗi video.</p>
        </button>
        <button type="button" className="home-command" data-variant="utility" onClick={onNavigateHistory}>
          <span className="home-command__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M4 6h16v12H4zM8 10h8M8 14h5" />
            </svg>
          </span>
          <strong>Lịch sử</strong>
          <p>Xem lại video đơn và chuỗi video đã lưu.</p>
        </button>
        <button type="button" className="home-command" data-variant="utility" onClick={onNavigateSettings}>
          <span className="home-command__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M12 8v8M8 12h8M5 5h14v14H5z" />
            </svg>
          </span>
          <strong>Cài đặt</strong>
          <p>Key, model mặc định và kiểm tra kết nối.</p>
        </button>
      </div>
    </section>
  );
}
