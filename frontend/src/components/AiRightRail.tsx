import { Bot, Copy, Download, PanelRightClose, PanelRightOpen, Printer, Settings } from "lucide-react";
import type { AiAnalysisResponse, AiAnalysisScope, AiProvider, ModuleDefinition } from "../types";

interface AiSettings {
  provider: AiProvider;
  model: string;
  apiKey: string;
}

interface AiRightRailProps {
  open: boolean;
  activePanel: "settings" | "ai" | null;
  settings: AiSettings;
  modules: ModuleDefinition[];
  activeModule: string;
  scope: AiAnalysisScope;
  moduleId: string;
  includeLatestRefresh: boolean;
  loading: boolean;
  error: string | null;
  result: AiAnalysisResponse | null;
  onToggleOpen: () => void;
  onSelectPanel: (panel: "settings" | "ai") => void;
  onSettingsChange: (settings: AiSettings) => void;
  onScopeChange: (scope: AiAnalysisScope) => void;
  onModuleIdChange: (moduleId: string) => void;
  onIncludeLatestRefreshChange: (enabled: boolean) => void;
  onRunAnalysis: () => void;
  onCopyReport: () => void;
  onPrintReport: () => void;
  onDownloadReport: () => void;
}

const defaultModels: Record<AiProvider, string> = {
  openai: "gpt-5",
  anthropic: "claude-sonnet-5",
  deepseek: "deepseek-v4-flash",
};

export function AiRightRail({
  open,
  activePanel,
  settings,
  modules,
  activeModule,
  scope,
  moduleId,
  includeLatestRefresh,
  loading,
  error,
  result,
  onToggleOpen,
  onSelectPanel,
  onSettingsChange,
  onScopeChange,
  onModuleIdChange,
  onIncludeLatestRefreshChange,
  onRunAnalysis,
  onCopyReport,
  onPrintReport,
  onDownloadReport,
}: AiRightRailProps) {
  const selectedPanel = activePanel ?? "ai";
  const selectedModule = moduleId || activeModule;

  return (
    <>
      <aside className="right-rail" aria-label="AI and settings rail">
        <button className="right-rail-toggle" type="button" onClick={onToggleOpen} title={open ? "Collapse right panel" : "Open right panel"}>
          {open ? <PanelRightClose aria-hidden="true" size={18} /> : <PanelRightOpen aria-hidden="true" size={18} />}
        </button>
        <button
          className={open && selectedPanel === "settings" ? "right-rail-button active" : "right-rail-button"}
          type="button"
          onClick={() => onSelectPanel("settings")}
          title="Settings"
        >
          <Settings aria-hidden="true" size={18} />
          <span>Settings</span>
        </button>
        <button
          className={open && selectedPanel === "ai" ? "right-rail-button active" : "right-rail-button"}
          type="button"
          onClick={() => onSelectPanel("ai")}
          title="AI"
        >
          <Bot aria-hidden="true" size={18} />
          <span>AI</span>
        </button>
      </aside>

      <aside className={open ? "right-panel open" : "right-panel"} aria-label="AI side panel">
        {selectedPanel === "settings" ? (
          <section className="right-panel-section">
            <div className="right-panel-heading">
              <span className="start-eyebrow">Session Settings</span>
              <h2>AI API</h2>
            </div>
            <label className="ai-field">
              <span>Provider</span>
              <select
                value={settings.provider}
                onChange={(event) => {
                  const provider = event.target.value as AiProvider;
                  onSettingsChange({ ...settings, provider, model: defaultModels[provider] });
                }}
              >
                <option value="openai">ChatGPT / OpenAI</option>
                <option value="anthropic">Claude</option>
                <option value="deepseek">DeepSeek</option>
              </select>
            </label>
            <label className="ai-field">
              <span>Model</span>
              <input value={settings.model} onChange={(event) => onSettingsChange({ ...settings, model: event.target.value })} />
            </label>
            <label className="ai-field">
              <span>API key</span>
              <input
                type="password"
                value={settings.apiKey}
                autoComplete="off"
                placeholder="Used once, not saved"
                onChange={(event) => onSettingsChange({ ...settings, apiKey: event.target.value })}
              />
            </label>
            <p className="right-panel-note">The key stays in this browser session state and the single backend request memory path.</p>
          </section>
        ) : (
          <section className="right-panel-section ai-analysis-panel">
            <div className="right-panel-heading">
              <span className="start-eyebrow">Realtime Analysis</span>
              <h2>AI Analyst</h2>
            </div>
            <label className="ai-field">
              <span>Analysis scope</span>
              <select value={scope} onChange={(event) => onScopeChange(event.target.value as AiAnalysisScope)}>
                <option value="current_page">Current Page</option>
                <option value="security_full">Security Full</option>
                <option value="module">Single Module</option>
                <option value="all_modules">All Modules</option>
              </select>
            </label>
            {scope === "module" && (
              <label className="ai-field">
                <span>Module</span>
                <select value={selectedModule} onChange={(event) => onModuleIdChange(event.target.value)}>
                  {modules.map((module) => (
                    <option key={module.id} value={module.id}>
                      {module.label}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="ai-toggle">
              <input
                type="checkbox"
                checked={includeLatestRefresh}
                onChange={(event) => onIncludeLatestRefreshChange(event.target.checked)}
              />
              <span>Include latest refresh</span>
            </label>
            <button className="primary-button" type="button" disabled={loading || !settings.apiKey.trim()} onClick={onRunAnalysis}>
              {loading ? "Analyzing" : "Run realtime analysis"}
            </button>
            {error && <div className="ai-error">{error}</div>}
            {result ? (
              <>
                <div className="ai-report-toolbar">
                  <button className="secondary-button" type="button" onClick={onCopyReport}>
                    <Copy aria-hidden="true" size={14} />
                    Copy
                  </button>
                  <button className="secondary-button" type="button" onClick={onPrintReport}>
                    <Printer aria-hidden="true" size={14} />
                    Print
                  </button>
                  <button className="secondary-button" type="button" onClick={onDownloadReport}>
                    <Download aria-hidden="true" size={14} />
                    HTML
                  </button>
                </div>
                <div className="ai-input-mode">Input: {result.input_mode}</div>
                <div className="ai-html-report" dangerouslySetInnerHTML={{ __html: result.report_html }} />
              </>
            ) : (
              <div className="ai-empty">Choose a scope and run analysis. The request uses structured content first and a best-effort workspace screenshot when supported.</div>
            )}
          </section>
        )}
      </aside>
    </>
  );
}
