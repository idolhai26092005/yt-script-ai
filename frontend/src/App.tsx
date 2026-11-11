import { useAppState } from './hooks/useAppState';
import type { AppState } from './hooks/useAppState';
import type { ReactNode } from 'react';
import { Sidebar } from './components/Sidebar';
import type { PageId } from './components/Sidebar';
import { SettingsPage } from './pages/SettingsPage';
import { IntroPage } from './pages/IntroPage';
import { GuidePage } from './pages/GuidePage';
import { DisclaimerPage } from './pages/DisclaimerPage';
import { AdminPanel } from './components/AdminPanel';

import SinglePage from './pages/SinglePage';
import ProductionPage from './pages/ProductionPage';
import { SeriesPage } from './pages/SeriesPage';
import { HistoryPage } from './pages/HistoryPage';
import { HomePage } from './pages/HomePage';
import { useProductionFlow } from './hooks/useProductionFlow';

interface ActivePageContentProps {
  activePage: PageId;
  state: AppState;
  prodFlow: ReturnType<typeof useProductionFlow>;
}

// Route switch guard: shell and route state are wired before each tab is
// redesigned so old workflows keep working through the phased rollout.
function ActivePageContent({ activePage, state, prodFlow }: ActivePageContentProps) {
  // Home renderer guard: the dashboard is a route hub and status surface only;
  // it must not reset drafts or revalidate keys on mount.
  const renderHome = (): ReactNode => (
    <HomePage
      appKeySaved={state.isAppKeySaved}
      appKeyValidating={state.appKeyValidating}
      appKeyError={state.appKeyError}
      geminiKeySaved={state.isKeySaved}
      geminiKeyValidating={state.geminiKeyValidating}
      geminiKeyError={state.geminiKeyError}
      modelName={state.modelName}
      defaultLanguage={state.defaultLanguage}
      onNavigateSingle={() => state.setActivePage('single')}
      onNavigateSeries={() => {
        state.setActiveSeriesId(null);
        state.setActivePage('series');
      }}
      onNavigateHistory={() => {
        state.setHistoryFilter('all');
        state.setActivePage('history');
      }}
      onNavigateSettings={() => state.setActivePage('settings')}
    />
  );

  // Single-flow renderer guard: Video đơn is now a manual-idea workbench; legacy
  // topic/YouTube project rows still restore through the same production hook.
  const renderSingle = (): ReactNode => (
    <SinglePage
      apiKey={state.apiKey}
      modelName={state.modelName}
      prodFlow={prodFlow}
      inputContent={prodFlow.inputContent}
      setInputContent={prodFlow.setInputContent}
      presetStyle={prodFlow.presetStyle}
      setPresetStyle={prodFlow.setPresetStyle}
      customStyle={prodFlow.customStyle}
      setCustomStyle={prodFlow.setCustomStyle}
      numScenes={prodFlow.numScenes}
      setNumScenes={prodFlow.setNumScenes}
      aspectRatio={prodFlow.aspectRatio}
      setAspectRatio={prodFlow.setAspectRatio}
      sceneDuration={prodFlow.sceneDuration}
      setSceneDuration={prodFlow.setSceneDuration}
      generationMode={prodFlow.generationMode}
      projectId={prodFlow.projectId}
      suggestions={prodFlow.suggestions}
      selectedSuggestionIdx={prodFlow.selectedSuggestionIdx}
      status={prodFlow.status}
      loadingSuggestions={prodFlow.loadingSuggestions}
      suggestionsError={prodFlow.suggestionsError}
      resetRevision={prodFlow.resetRevision}
      topicTypeOverride={prodFlow.topicTypeOverride}
      setTopicTypeOverride={prodFlow.setTopicTypeOverride}
      handleGenerateSuggestions={prodFlow.handleGenerateSuggestions}
      handleSelectSuggestion={prodFlow.handleSelectSuggestion}
      onNavigateToHistory={() => {
        state.setHistoryFilter('single');
        state.setActivePage('history');
      }}
      handleReset={prodFlow.handleReset}
      handleReturnToSingleIntake={prodFlow.handleReturnToSingleIntake}
      handleLoadProject={prodFlow.handleLoadProject}
    />
  );

  // Unified history guard: legacy project and series-history tabs now converge
  // on one archive surface without changing backend contracts.
  const renderHistory = (): ReactNode => (
    <HistoryPage
      geminiApiKey={state.apiKey}
      hasAppApiKey={state.isAppKeySaved}
      filter={state.historyFilter}
      onFilterChange={state.setHistoryFilter}
      onNavigateToSettings={() => state.setActivePage('settings')}
      onOpenProject={async (projectId: number, status: string) => {
        await prodFlow.handleLoadProject(state.apiKey, projectId);
        if (status === 'script_generated' || status === 'generating_script' || status === 'script_failed') {
          state.setActivePage('single');
          return;
        }
        state.setActivePage('single');
      }}
      onOpenSeries={(seriesId: number) => {
        state.setActiveSeriesId(seriesId);
        state.setActivePage('series');
      }}
    />
  );

  switch (activePage) {
    case 'home':
    default:
      return renderHome();
    case 'single':
      return renderSingle();
    case 'history':
      return renderHistory();
    case 'projects':
      return renderHistory();
    case 'seriesHistory':
      return renderHistory();
    case 'generate':
      return (
        <ProductionPage
          apiKey={state.apiKey}
          modelName={state.modelName}
          prodFlow={prodFlow}
          onBack={() => state.setActivePage(state.productionReturnPage)}
        />
      );
    case 'settings':
      return (
        <SettingsPage
          appApiKey={state.appApiKey}
          setAppApiKey={state.setAppApiKey}
          showAppKey={state.showAppKey}
          setShowAppKey={state.setShowAppKey}
          appKeyValidating={state.appKeyValidating}
          appKeyError={state.appKeyError}
          handleSaveAppKey={state.handleSaveAppKey}
          isAppKeySaved={state.isAppKeySaved}
          handleClearAppKey={state.handleClearAppKey}
          apiKey={state.apiKey}
          setApiKey={state.setApiKey}
          showKey={state.showKey}
          setShowKey={state.setShowKey}
          geminiKeyValidating={state.geminiKeyValidating}
          geminiKeyError={state.geminiKeyError}
          handleSaveKey={state.handleSaveKey}
          isKeySaved={state.isKeySaved}
          handleClearKey={state.handleClearKey}
          testPrompt={state.testPrompt}
          setTestPrompt={state.setTestPrompt}
          testLoading={state.testLoading}
          testResult={state.testResult}
          handleTestConnection={state.handleTestConnection}
          defaultModel={state.defaultModel}
          setDefaultModel={state.setDefaultModel}
          defaultLanguage={state.defaultLanguage}
          setDefaultLanguage={state.setDefaultLanguage}
        />
      );
    case 'intro':
      return <IntroPage />;
    case 'guide':
      return <GuidePage />;
    case 'disclaimer':
      return <DisclaimerPage />;
    case 'admin':
      return (
        <AdminPanel
          navigate={(path: string) => state.setActivePage(path === '/admin' ? 'admin' : 'home')}
        />
      );
    case 'series':
      return (
        <SeriesPage
          apiKey={state.apiKey}
          modelName={state.modelName}
          initialSeriesId={state.activeSeriesId}
          onNavigateToHistory={() => {
            state.setHistoryFilter('series');
            state.setActivePage('history');
          }}
        />
      );
  }
}

// App shell guard: the global frame owns responsive navigation and route
// chrome, leaving each tab to evolve independently in later UI passes.
function App() {
  const state = useAppState();
  const prodFlow = useProductionFlow();

  // Sidebar navigation guard: entering History from chrome always starts at the
  // combined archive, while deep links can still select a narrower segment.
  // Single-sidebar guard: clicking Video đơn is an explicit fresh-start action,
  // independent of any suggestion/output phase currently held in memory.
  // Series-sidebar guard: clicking Chuỗi video starts a new intake; old series
  // workbenches are reopened explicitly from History.
  const handleSidebarNavigate = (page: PageId) => {
    if (page === 'history') {
      state.setHistoryFilter('all');
    }
    if (page === 'single') {
      prodFlow.handleReset();
    }
    if (page === 'series') {
      state.setActiveSeriesId(null);
    }
    state.setActivePage(page);
  };

  return (
    <div className="app-shell">
      <button
        type="button"
        className="app-mobile-menu-button"
        onClick={() => state.setSidebarMobileOpen(true)}
        aria-label="Mở điều hướng"
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7h16M4 12h16M4 17h16" />
        </svg>
        Menu
      </button>
      {state.sidebarMobileOpen && (
        <button
          type="button"
          className="app-mobile-backdrop"
          onClick={() => state.setSidebarMobileOpen(false)}
          aria-label="Đóng điều hướng"
        />
      )}
      <Sidebar
        activePage={state.activePage}
        onNavigate={handleSidebarNavigate}
        collapsed={state.sidebarCollapsed}
        onToggleCollapse={() => state.setSidebarCollapsed(!state.sidebarCollapsed)}
        mobileOpen={state.sidebarMobileOpen}
        onCloseMobile={() => state.setSidebarMobileOpen(false)}
      />

      <div className="app-main-wrap">
        <main className="app-main">
          <ActivePageContent
            activePage={state.activePage}
            state={state}
            prodFlow={prodFlow}
          />
        </main>

        <footer className="app-footer">
          <p suppressHydrationWarning>© {new Date().getFullYear()} ScriptForge AI. Được xây dựng để dịch và tối ưu hóa kịch bản đa ngôn ngữ.</p>
        </footer>
      </div>
    </div>
  );
}

export default App;
