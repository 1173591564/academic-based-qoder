import { useState, useEffect, Component, type ReactNode } from "react";
import type { Settings } from "./types";
import { ChatView } from "./components/ChatView";
import { SettingsPage } from "./components/SettingsPage";

// Error Boundary: prevents white-screen crashes from component errors
class ErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; error: Error | null }
> {
  state = { hasError: false, error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: "2rem", textAlign: "center", color: "#ccc" }}>
          <h2>应用发生错误</h2>
          <p style={{ color: "#e74c3c", fontSize: "0.9rem" }}>
            {this.state.error?.message || "未知错误"}
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop: "1rem", padding: "0.5rem 1.5rem",
              background: "#5865F2", color: "#fff", border: "none",
              borderRadius: "4px", cursor: "pointer",
            }}
          >
            刷新页面
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const DEFAULT_SETTINGS: Settings = {
  cliIde: "claude-code",
  workDir: "",
  cliPath: "",
};

function App() {
  const [view, setView] = useState<"chat" | "settings">("chat");
  const [settings, setSettings] = useState<Settings>(() => {
    const saved = localStorage.getItem("scholar-settings");
    if (!saved) return DEFAULT_SETTINGS;
    try {
      const parsed = { ...DEFAULT_SETTINGS, ...JSON.parse(saved) };
      const validCliIde = (v: string): v is Settings["cliIde"] =>
        v === "claude-code" || v === "qoder-cli";
      if (!validCliIde(parsed.cliIde)) {
        parsed.cliIde = "claude-code";
      }
      return parsed;
    } catch {
      return DEFAULT_SETTINGS;
    }
  });

  useEffect(() => {
    if (!settings.workDir && !localStorage.getItem("scholar-settings")) {
      setView("settings");
    }
  }, []);

  const saveSettings = (s: Settings) => {
    setSettings(s);
    localStorage.setItem("scholar-settings", JSON.stringify(s));
    setView("chat");
  };

  if (view === "settings") {
    return (
      <ErrorBoundary>
        <SettingsPage
          settings={settings}
          onSave={saveSettings}
          onCancel={() => setView("chat")}
        />
      </ErrorBoundary>
    );
  }

  return (
    <ErrorBoundary>
      <ChatView
        settings={settings}
        onOpenSettings={() => setView("settings")}
      />
    </ErrorBoundary>
  );
}

export default App;
