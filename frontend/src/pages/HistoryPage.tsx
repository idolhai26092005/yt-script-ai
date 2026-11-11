import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { HistoryFilter } from '../hooks/useAppState';
import {
  deleteProject,
  deleteSeries,
  fetchHistoryPage,
  getErrorMessage,
  type HistoryItemResponse,
  type HistoryTotals,
} from '../services/api';

const PAGE_SIZE = 20;
const EMPTY_TOTALS: HistoryTotals = { all: 0, single: 0, series: 0 };

type LoadMode = 'replace' | 'append';

interface HistoryPageProps {
  geminiApiKey: string;
  hasAppApiKey: boolean;
  filter: HistoryFilter;
  onFilterChange: (filter: HistoryFilter) => void;
  onOpenProject: (projectId: number, status: string) => Promise<void>;
  onOpenSeries: (seriesId: number) => void;
  onNavigateToSettings: () => void;
}

const FILTER_OPTIONS: { value: HistoryFilter; label: string }[] = [
  { value: 'all', label: 'Tất cả' },
  { value: 'single', label: 'Video đơn' },
  { value: 'series', label: 'Chuỗi video' },
];

// Responsive mode guard: the first render chooses desktop pagination when the
// viewport is wide enough, then media-query events keep the mode current.
function readDesktopMode(): boolean {
  if (typeof window === 'undefined') return true;
  return window.matchMedia('(min-width: 768px)').matches;
}

// Date label guard: history rows stay compact and tolerate old records without
// timestamps instead of rendering Invalid Date in the dashboard.
function formatDate(value?: string | null): string {
  if (!value) return 'Chưa rõ thời gian';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'Chưa rõ thời gian';
  return parsed.toLocaleString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// Status copy guard: backend status identifiers stay visible but common states
// get short Vietnamese labels for dense rows.
function statusLabel(item: HistoryItemResponse): string {
  if (item.kind === 'series') {
    switch (item.status) {
      case 'active':
        return 'Đang mở';
      case 'completed':
        return 'Hoàn thành';
      case 'draft':
        return 'Nháp';
      default:
        return item.status || 'Series';
    }
  }

  switch (item.status) {
    case 'script_generated':
      return 'Đã sinh';
    case 'generating_script':
      return 'Đang sinh / tiếp tục';
    case 'script_failed':
      return 'Lỗi, có thể tiếp tục';
    case 'suggestions_generated':
      return 'Gợi ý';
    case 'draft':
      return 'Nháp';
    default:
      return item.status || 'Nháp';
  }
}

// Page-number guard: desktop pagination stays scannable on narrow tablets by
// showing first/last/current-neighbor pages instead of every page.
function compactPageNumbers(currentPage: number, totalPages: number): number[] {
  const candidates = new Set([0, totalPages - 1, currentPage - 1, currentPage, currentPage + 1]);
  return Array.from(candidates)
    .filter(page => page >= 0 && page < totalPages)
    .sort((a, b) => a - b);
}

// Filter total guard: badge counts come from the unified backend totals rather
// than the current page length.
function countForFilter(totals: HistoryTotals, filter: HistoryFilter): number {
  return filter === 'all' ? totals.all : totals[filter];
}

export function HistoryPage({
  geminiApiKey,
  hasAppApiKey,
  filter,
  onFilterChange,
  onOpenProject,
  onOpenSeries,
  onNavigateToSettings,
}: HistoryPageProps) {
  const [items, setItems] = useState<HistoryItemResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [totals, setTotals] = useState<HistoryTotals>(EMPTY_TOTALS);
  const [pageIndex, setPageIndex] = useState(0);
  const [isDesktop, setIsDesktop] = useState(readDesktopMode);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const [openingKey, setOpeningKey] = useState<string | null>(null);
  const requestSeqRef = useRef(0);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pageNumbers = useMemo(() => compactPageNumbers(pageIndex, totalPages), [pageIndex, totalPages]);
  const hasMore = items.length < total;

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const media = window.matchMedia('(min-width: 768px)');
    const handleChange = (event: MediaQueryListEvent) => setIsDesktop(event.matches);
    media.addEventListener('change', handleChange);
    return () => media.removeEventListener('change', handleChange);
  }, []);

  // History loader guard: every request carries a sequence id so quick filter
  // switches cannot paint stale rows from a slower previous response.
  const loadHistory = useCallback(async (
    targetFilter: HistoryFilter,
    targetPage: number,
    mode: LoadMode,
  ) => {
    if (!hasAppApiKey) return;
    const requestId = requestSeqRef.current + 1;
    requestSeqRef.current = requestId;
    const skip = targetPage * PAGE_SIZE;

    setLoading(true);
    setError(null);
    try {
      const page = await fetchHistoryPage(geminiApiKey, targetFilter, skip, PAGE_SIZE);
      if (requestSeqRef.current !== requestId) return;
      setTotals(page.totals);
      setTotal(page.total);
      setPageIndex(Math.floor(page.skip / PAGE_SIZE));
      setItems(current => mode === 'append' ? [...current, ...page.items] : page.items);
    } catch (err: unknown) {
      if (requestSeqRef.current === requestId) {
        setError(getErrorMessage(err, 'Không thể tải lịch sử chung.'));
      }
    } finally {
      if (requestSeqRef.current === requestId) {
        setLoading(false);
      }
    }
  }, [geminiApiKey, hasAppApiKey]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadHistory(filter, 0, 'replace');
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [filter, isDesktop, loadHistory]);

  // Filter guard: changing segment clears stale rows immediately; the effect
  // then loads page one using the new backend filter.
  const handleFilterChange = (nextFilter: HistoryFilter) => {
    if (nextFilter === filter) return;
    setItems([]);
    setTotal(0);
    setPageIndex(0);
    onFilterChange(nextFilter);
  };

  // Delete guard: each row deletes through its own endpoint, then the unified
  // page refreshes through `/history` so counts and ordering stay consistent.
  const handleDelete = async (item: HistoryItemResponse) => {
    const label = item.kind === 'series' ? 'chuỗi video' : 'dự án video đơn';
    if (!window.confirm(`Xóa ${label} này?`)) return;
    const key = `${item.kind}:${item.id}`;
    setDeletingKey(key);
    setError(null);
    try {
      if (item.kind === 'series') {
        await deleteSeries(geminiApiKey, item.id);
      } else {
        await deleteProject(geminiApiKey, item.id);
      }
      await loadHistory(filter, isDesktop ? pageIndex : 0, 'replace');
    } catch (err: unknown) {
      setError(getErrorMessage(err, `Không thể xóa ${label}.`));
    } finally {
      setDeletingKey(null);
    }
  };

  // Open guard: single rows restore production state by id, while series rows
  // hand the selected series id to the workbench route.
  const handleOpen = async (item: HistoryItemResponse) => {
    const key = `${item.kind}:${item.id}`;
    setOpeningKey(key);
    setError(null);
    try {
      if (item.kind === 'series') {
        onOpenSeries(item.id);
      } else {
        await onOpenProject(item.id, item.status);
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Không thể mở mục lịch sử.'));
    } finally {
      setOpeningKey(null);
    }
  };

  if (!hasAppApiKey) {
    return (
      <section className="history-page">
        <div className="history-empty">
          <p className="history-kicker">Lịch sử</p>
          <h1>Cần App API Key</h1>
          <p>Lưu App API Key trong Cài đặt để tải lịch sử video đơn và chuỗi video.</p>
          <button type="button" className="history-action history-action--primary" onClick={onNavigateToSettings}>
            Mở Cài đặt
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="history-page" aria-labelledby="history-title">
      <header className="history-head">
        <div>
          <p className="history-kicker">Lưu trữ</p>
          <h1 id="history-title">Lịch sử</h1>
          <p>Toàn bộ video đơn và chuỗi video nằm chung một nơi.</p>
        </div>
        <button
          type="button"
          className="history-action"
          onClick={() => void loadHistory(filter, isDesktop ? pageIndex : 0, 'replace')}
          disabled={loading}
        >
          {loading ? 'Đang tải' : 'Làm mới'}
        </button>
      </header>

      <div className="history-toolbar">
        <div className="history-segment" role="tablist" aria-label="Lọc lịch sử">
          {FILTER_OPTIONS.map(option => (
            <button
              key={option.value}
              type="button"
              role="tab"
              aria-selected={filter === option.value}
              className={`history-segment__item ${filter === option.value ? 'is-active' : ''}`}
              onClick={() => handleFilterChange(option.value)}
            >
              <span>{option.label}</span>
              <strong>{countForFilter(totals, option.value)}</strong>
            </button>
          ))}
        </div>
        <div className="history-stats" aria-label="Thống kê lịch sử">
          <span><strong>{totals.all}</strong> tổng</span>
          <span><strong>{totals.single}</strong> video đơn</span>
          <span><strong>{totals.series}</strong> chuỗi</span>
        </div>
      </div>

      {error && <div className="history-alert">{error}</div>}

      {loading && items.length === 0 ? (
        <div className="history-skeleton">Đang tải lịch sử...</div>
      ) : items.length === 0 ? (
        <div className="history-empty">
          <p className="history-kicker">Trống</p>
          <h2>Chưa có mục phù hợp</h2>
          <p>Đổi filter hoặc tạo kịch bản mới để lịch sử xuất hiện tại đây.</p>
        </div>
      ) : (
        <>
          <div className="history-list">
            {items.map(item => {
              const key = `${item.kind}:${item.id}`;
              const isBusy = openingKey === key || deletingKey === key;
              return (
                <article key={key} className="history-row">
                  <div className="history-row__main">
                    <div className="history-row__topline">
                      <span className={`history-kind history-kind--${item.kind}`}>
                        {item.kind === 'series' ? 'Chuỗi video' : 'Video đơn'}
                      </span>
                      <span className={`history-status history-status--${item.kind}`}>
                        {statusLabel(item)}
                      </span>
                    </div>
                    <h2>{item.title}</h2>
                    <p>{item.preview}</p>
                  </div>
                  <div className="history-row__meta">
                    <span>{item.meta}</span>
                    <time dateTime={item.updated_at || item.created_at}>
                      {formatDate(item.updated_at || item.created_at)}
                    </time>
                  </div>
                  <div className="history-row__actions">
                    <button
                      type="button"
                      className="history-action history-action--primary"
                      onClick={() => void handleOpen(item)}
                      disabled={isBusy}
                    >
                      {openingKey === key ? 'Đang mở' : item.kind === 'series' ? 'Mở series' : 'Mở dự án'}
                    </button>
                    <button
                      type="button"
                      className="history-action history-action--danger"
                      onClick={() => void handleDelete(item)}
                      disabled={isBusy}
                    >
                      {deletingKey === key ? 'Đang xóa' : 'Xóa'}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>

          <nav className="history-pagination history-pagination--desktop" aria-label="Phân trang lịch sử">
            <button
              type="button"
              className="history-action"
              onClick={() => void loadHistory(filter, Math.max(0, pageIndex - 1), 'replace')}
              disabled={loading || pageIndex === 0}
            >
              Trước
            </button>
            <div className="history-page-numbers">
              {pageNumbers.map((page, index) => {
                const previous = pageNumbers[index - 1];
                return (
                  <span key={page} className="history-page-number-group">
                    {previous !== undefined && page - previous > 1 && (
                      <span className="history-page-ellipsis">...</span>
                    )}
                    <button
                      type="button"
                      className={`history-page-number ${pageIndex === page ? 'is-active' : ''}`}
                      onClick={() => void loadHistory(filter, page, 'replace')}
                      disabled={loading}
                      aria-current={pageIndex === page ? 'page' : undefined}
                    >
                      {page + 1}
                    </button>
                  </span>
                );
              })}
            </div>
            <button
              type="button"
              className="history-action"
              onClick={() => void loadHistory(filter, Math.min(totalPages - 1, pageIndex + 1), 'replace')}
              disabled={loading || pageIndex >= totalPages - 1}
            >
              Sau
            </button>
          </nav>

          <div className="history-pagination history-pagination--mobile">
            <button
              type="button"
              className="history-action history-action--primary"
              onClick={() => void loadHistory(filter, pageIndex + 1, 'append')}
              disabled={loading || !hasMore}
            >
              {hasMore ? loading ? 'Đang tải' : 'Tải thêm' : 'Đã hết'}
            </button>
          </div>
        </>
      )}
    </section>
  );
}
