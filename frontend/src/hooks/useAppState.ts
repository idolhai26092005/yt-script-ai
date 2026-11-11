import { useState, useEffect } from 'react';
import type { PageId } from '../components/Sidebar';
import { useApiKeys } from './useApiKeys';
import { safeStorage } from '../utils/secureStorage';

export type HistoryFilter = 'all' | 'single' | 'series';

// Route mapping guard: the app keeps its lightweight state router while new
// tabs are introduced incrementally without pulling in a router dependency.
const PAGE_PATHS: Record<PageId, string> = {
  home: '/',
  single: '/single',
  generate: '/generate',
  history: '/history',
  projects: '/projects',
  series: '/series',
  seriesHistory: '/series-history',
  settings: '/settings',
  intro: '/intro',
  guide: '/guide',
  disclaimer: '/disclaimer',
  admin: '/admin',
};

// Legacy history alias guard: old project/series URLs keep working while the
// sidebar has a single History destination.
const HISTORY_ALIAS_FILTERS: Partial<Record<PageId, HistoryFilter>> = {
  projects: 'single',
  seriesHistory: 'series',
};

type RouteState = {
  page: PageId;
  historyFilter?: HistoryFilter;
};

// Path parser guard: unknown deep links return to Home, and legacy history
// links resolve to the unified History page with the matching segment active.
function routeStateFromPath(pathname: string): RouteState {
  const normalized = pathname.replace(/\/+$/, '') || '/';
  const match = (Object.entries(PAGE_PATHS) as [PageId, string][])
    .find(([, path]) => path === normalized);
  const page = match?.[0] || 'home';
  if (page === 'projects' || page === 'seriesHistory') {
    return { page: 'history', historyFilter: HISTORY_ALIAS_FILTERS[page] };
  }
  return { page };
}

export function useAppState() {
  // Sidebar & Page states
  const [activePage, setActivePage] = useState<PageId>(() => {
    return routeStateFromPath(window.location.pathname).page;
  });
  const [historyFilter, setHistoryFilter] = useState<HistoryFilter>(() => {
    return routeStateFromPath(window.location.pathname).historyFilter || 'all';
  });
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);
  const [sidebarMobileOpen, setSidebarMobileOpen] = useState<boolean>(false);
  const [activeSeriesId, setActiveSeriesId] = useState<number | null>(null);
  const [productionReturnPage, setProductionReturnPage] = useState<PageId>('single');
  const [copiedText, setCopiedText] = useState<{ [key: string]: boolean }>({});

  // Synchronize URL pathname with activePage
  useEffect(() => {
    const handlePopState = () => {
      const routeState = routeStateFromPath(window.location.pathname);
      setActivePage(routeState.page);
      if (routeState.historyFilter) {
        setHistoryFilter(routeState.historyFilter);
      }
      setSidebarMobileOpen(false);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Update URL path when activePage changes
  useEffect(() => {
    const currentPath = window.location.pathname;
    const targetPath = PAGE_PATHS[activePage] || '/';
    if (currentPath !== targetPath) {
      window.history.pushState({}, '', targetPath);
    }
  }, [activePage]);

  // 1. Delegate API Keys logic
  const {
    apiKeysState,
    setApiKeysState,
    handleSaveKey,
    handleClearKey,
    handleSaveAppKey,
    handleClearAppKey,
    handleTestConnection,
  } = useApiKeys();

  // 2. Defaults configuration state managed directly
  const [defaults, setDefaults] = useState({
    model: safeStorage.getItem('DEFAULT_MODEL') || 'gemini-3.1-flash-lite',
    language: safeStorage.getItem('DEFAULT_LANGUAGE') || 'bilingual',
    duration: safeStorage.getItem('DEFAULT_DURATION') || '05:00',
  });

  const [modelName, setModelName] = useState<string>(() => {
    return defaults.model;
  });

  return {
    activePage,
    setActivePage,
    historyFilter,
    setHistoryFilter,
    sidebarCollapsed,
    setSidebarCollapsed,
    sidebarMobileOpen,
    setSidebarMobileOpen,
    activeSeriesId,
    setActiveSeriesId,
    productionReturnPage,
    setProductionReturnPage,
    copiedText,
    setCopiedText,
    modelName,
    setModelName,
    
    // Defaults configuration
    defaultModel: defaults.model,
    setDefaultModel: (val: string) => {
      setDefaults(prev => ({ ...prev, model: val }));
      setModelName(val);
    },
    defaultLanguage: defaults.language,
    setDefaultLanguage: (val: string) => setDefaults(prev => ({ ...prev, language: val })),
    defaultDuration: defaults.duration,
    setDefaultDuration: (val: string) => setDefaults(prev => ({ ...prev, duration: val })),

    // API Keys state
    apiKey: apiKeysState.apiKey,
    setApiKey: (val: string) => setApiKeysState(prev => ({ ...prev, apiKey: val })),
    showKey: apiKeysState.showKey,
    setShowKey: (val: boolean) => setApiKeysState(prev => ({ ...prev, showKey: val })),
    isKeySaved: apiKeysState.isKeySaved,
    geminiKeyError: apiKeysState.geminiKeyError,
    geminiKeyValidating: apiKeysState.geminiKeyValidating,
    appApiKey: apiKeysState.appApiKey,
    setAppApiKey: (val: string) => setApiKeysState(prev => ({ ...prev, appApiKey: val })),
    showAppKey: apiKeysState.showAppKey,
    setShowAppKey: (val: boolean) => setApiKeysState(prev => ({ ...prev, showAppKey: val })),
    isAppKeySaved: apiKeysState.isAppKeySaved,
    appKeyError: apiKeysState.appKeyError,
    appKeyValidating: apiKeysState.appKeyValidating,
    testPrompt: apiKeysState.testPrompt,
    setTestPrompt: (val: string) => setApiKeysState(prev => ({ ...prev, testPrompt: val })),
    testLoading: apiKeysState.testLoading,
    testResult: apiKeysState.testResult,
    
    // API Keys handlers
    handleSaveKey,
    handleClearKey,
    handleSaveAppKey,
    handleClearAppKey,
    handleTestConnection,
  };
}

export type AppState = ReturnType<typeof useAppState>;
