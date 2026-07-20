import { Bot, CheckCircle2, Copy, Download, PanelRightClose, PanelRightOpen, Printer, Settings, XCircle } from "lucide-react";
import type { PointerEvent as ReactPointerEvent } from "react";
import type { AiAnalysisResponse, AiAnalysisScope, AiCheckResponse, AiProvider, ModuleDefinition } from "../types";

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
  checking: boolean;
  error: string | null;
  checkResult: AiCheckResponse | null;
  result: AiAnalysisResponse | null;
  onToggleOpen: () => void;
  onSelectPanel: (panel: "settings" | "ai") => void;
  onSettingsChange: (settings: AiSettings) => void;
  onCheckConnection: () => void;
  onPrintWorkspace: () => void;
  onScopeChange: (scope: AiAnalysisScope) => void;
  onModuleIdChange: (moduleId: string) => void;
  onIncludeLatestRefreshChange: (enabled: boolean) => void;
  onRunAnalysis: () => void;
  onCopyReport: () => void;
  onPrintReport: () => void;
  onDownloadReport: () => void;
  panelWidth: number;
  onPanelWidthChange: (width: number) => void;
  onPanelWidthReset: () => void;
}

export const aiDefaultModels: Record<AiProvider, string> = {
  openai: "gpt-5.6",
  anthropic: "claude-sonnet-5",
  deepseek: "deepseek-v4-pro",
};

const modelPresets: Record<AiProvider, Array<{ value: string; label?: string }>> = {
  openai: [
    { value: "gpt-5.6" },
    { value: "gpt-5.6-sol" },
    { value: "gpt-5.6-terra" },
    { value: "gpt-5.6-luna" },
    { value: "gpt-5.5" },
    { value: "gpt-5.5-pro" },
    { value: "gpt-4.1" },
  ],
  anthropic: [
    { value: "claude-sonnet-5" },
    { value: "claude-opus-4.1" },
    { value: "claude-3-7-sonnet-latest" },
  ],
  deepseek: [
    { value: "deepseek-v4-pro" },
    { value: "deepseek-v4-flash" },
    { value: "deepseek-chat", label: "deprecated after 2026-07-24 UTC" },
    { value: "deepseek-reasoner", label: "deprecated after 2026-07-24 UTC" },
  ],
};

const deprecatedModels = new Set(["deepseek-chat", "deepseek-reasoner"]);

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
  checking,
  error,
  checkResult,
  result,
  onToggleOpen,
  onSelectPanel,
  onSettingsChange,
  onCheckConnection,
  onPrintWorkspace,
  onScopeChange,
  onModuleIdChange,
  onIncludeLatestRefreshChange,
  onRunAnalysis,
  onCopyReport,
  onPrintReport,
  onDownloadReport,
  panelWidth,
  onPanelWidthChange,
  onPanelWidthReset,
}: AiRightRailProps) {
  const selectedPanel = activePanel ?? "ai";
  const selectedModule = moduleId || activeModule;
  const modelListId = `ai-model-presets-${settings.provider}`;

  function handleResizeStart(event: ReactPointerEvent<HTMLDivElement>) {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = panelWidth;
    const minWidth = 360;
    const maxWidth = Math.min(960, Math.max(360, window.innerWidth - 420));
    const handlePointerMove = (moveEvent: globalThis.PointerEvent) => {
      const nextWidth = Math.min(maxWidth, Math.max(minWidth, startWidth + startX - moveEvent.clientX));
      onPanelWidthChange(Math.round(nextWidth));
    };
    const handlePointerUp = () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
  }

  return (
    <>
      <aside className="right-rail" aria-label="AI and settings rail">
        <button className="right-rail-toggle" type="button" onClick={onToggleOpen} title={open ? "Collapse right panel" : "Open right panel"}>
          {open ? <PanelRightClose aria-hidden="true" size={18} /> : <PanelRightOpen aria-hidden="true" size={18} />}
        </button>
        <button className="right-rail-button" type="button" onClick={onPrintWorkspace} title="PDF Print" aria-label="PDF Print">
          <Printer aria-hidden="true" size={18} />
        </button>
        <button
          className={open && selectedPanel === "settings" ? "right-rail-button active" : "right-rail-button"}
          type="button"
          onClick={() => onSelectPanel("settings")}
          title="Settings"
          aria-label="Settings"
        >
          <Settings aria-hidden="true" size={18} />
        </button>
        <button
          className={open && selectedPanel === "ai" ? "right-rail-button active" : "right-rail-button"}
          type="button"
          onClick={() => onSelectPanel("ai")}
          title="AI"
          aria-label="AI"
        >
          <Bot aria-hidden="true" size={18} />
        </button>
      </aside>

      <aside className={open ? "right-panel open" : "right-panel"} aria-label="AI side panel">
        <div
          className="right-panel-resize-handle"
          role="separator"
          aria-orientation="vertical"
          title="Drag to resize. Double-click to reset."
          onPointerDown={handleResizeStart}
          onDoubleClick={onPanelWidthReset}
        />
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
                  onSettingsChange({ ...settings, provider, model: aiDefaultModels[provider] });
                }}
              >
                <option value="openai">ChatGPT / OpenAI</option>
                <option value="anthropic">Claude</option>
                <option value="deepseek">DeepSeek</option>
              </select>
            </label>
            <label className="ai-field">
              <span>Model</span>
              <input
                list={modelListId}
                value={settings.model}
                onChange={(event) => onSettingsChange({ ...settings, model: event.target.value })}
              />
              <datalist id={modelListId}>
                {modelPresets[settings.provider].map((preset) => (
                  <option key={preset.value} value={preset.value} label={preset.label} />
                ))}
              </datalist>
            </label>
            {deprecatedModels.has(settings.model) && (
              <div className="ai-warning">Deprecated after 2026-07-24 UTC. Keep only for short-term compatibility.</div>
            )}
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
            <button className="secondary-button ai-check-button" type="button" disabled={checking || !settings.apiKey.trim()} onClick={onCheckConnection}>
              {checking ? "Checking" : "Check connection"}
            </button>
            {checkResult && (
              <div className={checkResult.ok ? "ai-check-result ok" : "ai-check-result bad"}>
                {checkResult.ok ? <CheckCircle2 aria-hidden="true" size={15} /> : <XCircle aria-hidden="true" size={15} />}
                <span>{checkResult.message} ({checkResult.latency_ms}ms)</span>
              </div>
            )}
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
            <button className="primary-button" type="button" disabled={loading || checking || !settings.apiKey.trim()} onClick={onRunAnalysis}>
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
