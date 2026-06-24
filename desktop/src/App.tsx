import { useState, useEffect } from "react";
import type { Settings } from "./types";
import { ChatView } from "./components/ChatView";
import { SettingsPage } from "./components/SettingsPage";

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
      <SettingsPage
        settings={settings}
        onSave={saveSettings}
        onCancel={() => setView("chat")}
      />
    );
  }

  return (
    <ChatView
      settings={settings}
      onOpenSettings={() => setView("settings")}
    />
  );
}

export default App;
