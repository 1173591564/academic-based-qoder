import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import type {
  Settings,
  HealthStatus,
  DockerService,
  DotfilesStatus,
  DistributionResult,
} from "../types";
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  FolderOpen,
  Upload,
  Hexagon,
  Terminal,
  Play,
  Square as SquareIcon,
} from "lucide-react";

function shortenPath(p: string): string {
  if (!p) return "";
  const parts = p.replace(/\\/g, "/").split("/");
  return parts.length > 3 ? ".../" + parts.slice(-2).join("/") : p;
}

export function SettingsPage({
  settings,
  onSave,
  onCancel,
}: {
  settings: Settings;
  onSave: (s: Settings) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<Settings>(settings);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [workspaceInfo, setWorkspaceInfo] = useState("");
  const [recentWorkspaces] = useState<string[]>(() => {
    try {
      return JSON.parse(
        localStorage.getItem("scholar-recent-workspaces") || "[]"
      );
    } catch {
      return [];
    }
  });
  const [dockerServices, setDockerServices] = useState<DockerService[]>([]);
  const [dotfilesStatus, setDotfilesStatus] =
    useState<DotfilesStatus | null>(null);
  const [distributing, setDistributing] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: "ok" | "error" } | null>(null);

  const showToast = (msg: string, type: "ok" | "error" = "ok") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  useEffect(() => {
    invoke<HealthStatus>("health_check", {
      workDir: form.workDir,
    })
      .then(setHealth)
      .catch(() => {});
    invoke<DockerService[]>("docker_status", {
      workDir: form.workDir,
    })
      .then(setDockerServices)
      .catch(() => {});
    invoke<DotfilesStatus>("check_dotfiles_status", {
      workDir: form.workDir,
    })
      .then(setDotfilesStatus)
      .catch(() => {});
  }, []);

  const handleDockerToggle = async (service: string, start: boolean) => {
    try {
      await invoke("docker_toggle", {
        service,
        workDir: form.workDir,
        start,
      });
      const updated = await invoke<DockerService[]>("docker_status", {
        workDir: form.workDir,
      });
      setDockerServices(updated);
    } catch (e) {
      showToast(`Docker 操作失败: ${e}`, "error");
    }
  };

  const handleDistributeDotfiles = async () => {
    if (!form.workDir) {
      showToast("请先选择工作目录", "error");
      return;
    }
    setDistributing(true);
    try {
      const result = await invoke<DistributionResult>("distribute_dotfiles", {
        workDir: form.workDir,
      });
      showToast(result.message);
      const status = await invoke<DotfilesStatus>("check_dotfiles_status", {
        workDir: form.workDir,
      });
      setDotfilesStatus(status);
    } catch (e) {
      showToast(`分发失败: ${e}`, "error");
    } finally {
      setDistributing(false);
    }
  };

  const handleDetectCli = async () => {
    try {
      const path = await invoke<string>("detect_cli", {
        cliIde: form.cliIde,
      });
      setForm({ ...form, cliPath: path });
    } catch (e) {
      showToast(`未检测到 CLI：${e}`, "error");
    }
  };

  const handleSelectDir = async () => {
    try {
      const selected = await open({ directory: true, multiple: false });
      if (selected) {
        setForm({ ...form, workDir: selected });
        try {
          const info = await invoke<{ valid: boolean; message: string }>(
            "validate_workspace",
            { path: selected }
          );
          setWorkspaceInfo(info.message);
        } catch (e) {
          setWorkspaceInfo(`验证失败: ${e}`);
        }
      }
    } catch (e) {
      console.error("Directory selection failed:", e);
    }
  };

  const handleSelectRecent = (path: string) => {
    setForm({ ...form, workDir: path });
    setWorkspaceInfo("");
  };

  const handleSave = async () => {
    if (!form.workDir.trim()) {
      showToast("请选择工作目录", "error");
      return;
    }
    let list: string[] = [];
    try {
      list = JSON.parse(
        localStorage.getItem("scholar-recent-workspaces") || "[]"
      );
    } catch {
      list = [];
    }
    const filtered = list.filter((p: string) => p !== form.workDir);
    localStorage.setItem(
      "scholar-recent-workspaces",
      JSON.stringify([form.workDir, ...filtered].slice(0, 5))
    );

    if (!dotfilesStatus?.has_claude) {
      setDistributing(true);
      try {
        await invoke<DistributionResult>("distribute_dotfiles", {
          workDir: form.workDir,
        });
      } catch (e) {
        console.warn("Auto-distribute failed:", e);
      } finally {
        setDistributing(false);
      }
    }

    onSave(form);
  };

  const healthItems = health
    ? [
        { label: "Scholar CLI", ok: health.scholar_exe, detail: health.scholar_exe_path },
        { label: "Python", ok: health.python, detail: health.python_path },
        { label: "Claude Code CLI", ok: health.claude_cli, detail: health.claude_cli_path },
        { label: "Qoder CLI", ok: health.qoder_cli, detail: health.qoder_cli_path },
        { label: "MCP Server", ok: health.mcp_importable, detail: "" },
        { label: "Rules 目录", ok: health.rules_dir, detail: `${health.skills_count} skills` },
        { label: "Output 目录", ok: health.output_dir, detail: "" },
        { label: "PostgreSQL", ok: health.pg_running, detail: health.pg_running ? ":5433" : "未启动" },
        { label: "Neo4j", ok: health.neo4j_running, detail: health.neo4j_running ? ":7474" : "未启动" },
      ]
    : [];

  return (
    <div className="settings-page">
      <div className="settings-card">
        <div className="settings-back-row">
          <button className="settings-back-btn" onClick={onCancel}>
            <ArrowLeft size={16} />
            返回聊天
          </button>
        </div>

        <h2 className="settings-title">配置</h2>
        <p className="settings-desc">选择 CLI IDE 后端并配置工作环境</p>

        {health && (
          <div className="settings-group">
            <label className="settings-label">系统健康检查</label>
            <div className="health-panel">
              {healthItems.map((item) => (
                <div key={item.label} className={`health-item ${item.ok ? "ok" : "fail"}`}>
                  <span className="health-icon">
                    {item.ok ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                  </span>
                  <span className="health-label">{item.label}</span>
                  {item.detail && (
                    <span className="health-detail" title={item.detail}>
                      {shortenPath(item.detail)}
                    </span>
                  )}
                </div>
              ))}
            </div>
            {!health.overall && (
              <div className="health-warning">部分组件不可用，可能影响功能</div>
            )}
          </div>
        )}

        {dockerServices.length > 0 && (
          <div className="settings-group">
            <label className="settings-label">Docker 服务</label>
            <div className="docker-panel">
              {dockerServices.map((svc) => (
                <div key={svc.name} className="docker-item">
                  <span className={`docker-status ${svc.running ? "running" : "stopped"}`} />
                  <span className="docker-name">{svc.name}</span>
                  <span className="docker-state">{svc.status}</span>
                  <button className="docker-btn" onClick={() => handleDockerToggle(svc.name, !svc.running)}>
                    {svc.running ? (
                      <><SquareIcon size={10} fill="currentColor" /> 停止</>
                    ) : (
                      <><Play size={10} fill="currentColor" /> 启动</>
                    )}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="settings-group">
          <label className="settings-label">CLI IDE 后端</label>
          <div className="ide-selector">
            {(
              [
                { value: "claude-code", name: "Claude Code", icon: <Hexagon size={24} />, desc: "Anthropic CLI · 兼容 CCSwitch 模型切换" },
                { value: "qoder-cli", name: "Qoder CLI", icon: <Terminal size={24} />, desc: "Qoder IDE CLI · 支持 skills/commands" },
              ] as const
            ).map((ide) => (
              <div
                key={ide.value}
                className={`ide-option ${form.cliIde === ide.value ? "selected" : ""}`}
                onClick={() => setForm({ ...form, cliIde: ide.value })}
                style={{ cursor: "pointer" }}
              >
                <div className="ide-icon">{ide.icon}</div>
                <div className="ide-info">
                  <div className="ide-name">{ide.name}</div>
                  <div className="ide-desc">{ide.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="settings-group">
          <label className="settings-label">工作目录</label>
          <div className="workspace-selector">
            <button className="workspace-picker-btn" onClick={handleSelectDir}>
              <FolderOpen size={14} /> 选择目录
            </button>
            <span className="workspace-path">{form.workDir || "未选择"}</span>
          </div>
          {workspaceInfo && <div className="settings-hint">{workspaceInfo}</div>}

          {dotfilesStatus && form.workDir && (
            <div className="dotfiles-status">
              <div className="dotfiles-summary">
                <span className={`dotfiles-badge ${dotfilesStatus.has_claude ? "ok" : "missing"}`}>
                  .claude/ {dotfilesStatus.has_claude ? `✓ ${dotfilesStatus.total_files} files` : "✕ 缺失"}
                </span>
                <span className={`dotfiles-badge ${dotfilesStatus.has_qoder ? "ok" : "missing"}`}>
                  .qoder/ {dotfilesStatus.has_qoder ? `✓ ${dotfilesStatus.qoder_total} files` : "✕ 缺失"}
                </span>
                <span className="dotfiles-meta">
                  {dotfilesStatus.last_distributed === "never"
                    ? "从未分发"
                    : `上次分发: ${new Date(parseInt(dotfilesStatus.last_distributed) * 1000).toLocaleString("zh-CN")}`}
                </span>
              </div>
              <button className="distribute-btn" onClick={handleDistributeDotfiles} disabled={distributing}>
                {distributing ? "分发中..." : <><Upload size={14} /> 分发 .claude + .qoder 到此目录</>}
              </button>
              <div className="settings-hint">
                分发后，此目录将包含 15 个 skills + 7 个 rules + 定制化的 CLAUDE.md/mcp.json。
                Claude Code 或 Qoder CLI 打开此目录时会自动发现并加载所有配置。
              </div>
            </div>
          )}

          {recentWorkspaces.length > 0 && (
            <div className="recent-workspaces">
              <div className="settings-hint">最近使用：</div>
              {recentWorkspaces.map((path) => (
                <div
                  key={path}
                  className={`recent-workspace ${form.workDir === path ? "active" : ""}`}
                  onClick={() => handleSelectRecent(path)}
                >
                  {path}
                </div>
              ))}
            </div>
          )}
          <div className="settings-hint">Scholar Studio 将在此目录下读写 output/、data/ 等数据</div>
        </div>

        <div className="settings-group">
          <label className="settings-label">CLI 路径（留空自动检测）</label>
          <div className="cli-path-row">
            <input
              type="text"
              className="settings-input"
              placeholder="自动检测…"
              value={form.cliPath}
              onChange={(e) => setForm({ ...form, cliPath: e.target.value })}
            />
            <button className="detect-btn" onClick={handleDetectCli}>检测</button>
          </div>
          <div className="settings-hint">Claude Code CLI 路径 · 兼容 CCSwitch 模型切换，无需单独 API Key</div>
        </div>

        <div className="settings-actions">
          <button className="btn-secondary" onClick={onCancel}>取消</button>
          <button className="btn-primary" onClick={handleSave}>保存</button>
        </div>

        <div className="settings-version">Scholar Studio v0.1.0</div>
      </div>
      {toast && (
        <div
          className={`toast-notification ${toast.type}`}
          style={{
            position: "fixed", bottom: "2rem", right: "2rem",
            padding: "0.75rem 1.5rem", borderRadius: "8px",
            background: toast.type === "ok" ? "#43b581" : "#e74c3c",
            color: "#fff", fontSize: "0.9rem", zIndex: 9999,
            boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
          }}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}
