import { useState, useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import type {
  FileNode,
  Conversation,
  ChatMessage,
  ConversationRecord,
  Settings,
  HealthStatus,
  SkillInfo,
  DockerService,
  CitationGraphData,
  PaperCardData,
  QualityRadarData,
  KBDashboardData,
  ExperimentMetricsData,
  TimelineData,
} from "../types";
import { MessageBubble } from "./MessageBubble";
import { TypingIndicator } from "./TypingIndicator";
import { WelcomeScreen } from "./WelcomeScreen";
import { ChatInput } from "./ChatInput";
import { FileTree } from "./FileTree";
import { SkillPanel } from "./SkillPanel";
import { ConversationList } from "./ConversationList";
import { CitationGraph } from "./CitationGraph";
import { PaperReader } from "./PaperReader";
import { QualityRadar } from "./QualityRadar";
import { KBDashboard } from "./KBDashboard";
import { ExperimentMetrics } from "./ExperimentMetrics";
import { Timeline } from "./Timeline";

import { Plus, Settings as SettingsIcon, Circle } from "lucide-react";

// MCP Bridge: call scholar MCP tools directly from the shell
async function callScholarMcp(toolName: string, args: Record<string, unknown>): Promise<string> {
  return await invoke<string>("call_scholar_mcp", {
    toolName,
    args: JSON.stringify(args),
  });
}

type PreviewType = "text" | "citation_graph" | "paper_reader" | "quality_radar" | "kb_dashboard" | "experiment_metrics" | "timeline" | "markdown";

export function ChatView({
  settings,
  onOpenSettings,
}: {
  settings: Settings;
  onOpenSettings: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [files, setFiles] = useState<FileNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeConversation, setActiveConversation] = useState<string | null>(
    null
  );
  const [sessionId, setSessionId] = useState<string>(() =>
    crypto.randomUUID()
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [inputText, setInputText] = useState("");
  const [previewContent, setPreviewContent] = useState<{
    name: string;
    content: string;
  } | null>(null);
  const [previewType, setPreviewType] = useState<
    "text" | "citation_graph" | "paper_reader" | "quality_radar" | "kb_dashboard" | "experiment_metrics" | "timeline" | "markdown"
  >("text");
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [dockerServices, setDockerServices] = useState<DockerService[]>([]);
  const [sidebarTab, setSidebarTab] = useState<"files" | "skills">("files");
  const [fileFilter, setFileFilter] = useState<string>("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Refs for event handler access (to avoid stale closures)
  const messagesRef = useRef<ChatMessage[]>([]);
  const sessionIdRef = useRef(sessionId);
  const settingsRef = useRef(settings);
  const pendingSaveRef = useRef<{
    userMsg: ChatMessage;
    text: string;
  } | null>(null);

  // Route parsed JSON to the appropriate preview component type
  const routeToComponent = (parsed: Record<string, unknown>): PreviewType => {
    if (parsed.nodes && parsed.edges) return "citation_graph";
    if (parsed.sections_toc || parsed.paper_id) return "paper_reader";
    if (parsed.dimensions) return "quality_radar";
    if (parsed.by_year || parsed.parsed !== undefined) return "kb_dashboard";
    if (parsed.our_metrics || parsed.comparison) return "experiment_metrics";
    if (parsed.years && Array.isArray(parsed.years)) return "timeline";
    return "text";
  };

  // Visualize paper data by calling MCP tools directly from the shell
  const handleVisualize = async (tool: string, paperId: string) => {
    try {
      setPreviewContent({ name: "加载中...", content: "" });
      setPreviewType("text");
      const result = await callScholarMcp(tool, { paper_id: paperId });
      const parsed = JSON.parse(result);
      const toolNames: Record<string, string> = {
        scholar_get_citation_graph: "引用网络",
        scholar_get_paper_card: "论文详情",
        scholar_get_quality_radar: "质量评估",
        scholar_get_experiment_metrics: "实验指标",
        scholar_get_timeline: "时间线",
        scholar_get_kb_dashboard: "知识库",
      };
      const name = toolNames[tool] || tool;
      setPreviewContent({ name, content: JSON.stringify(parsed, null, 2) });
      setPreviewType(routeToComponent(parsed));
    } catch (e) {
      setPreviewContent({ name: "错误", content: `可视化失败: ${e}` });
      setPreviewType("text");
    }
  };

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);
  useEffect(() => {
    settingsRef.current = settings;
  }, [settings]);

  // Health check + skills + docker on mount and workDir change
  useEffect(() => {
    invoke<HealthStatus>("health_check", {
      workDir: settings.workDir,
    })
      .then(setHealth)
      .catch(() => {});
    invoke<SkillInfo[]>("list_skills")
      .then(setSkills)
      .catch(() => {});
    invoke<DockerService[]>("docker_status", {
      workDir: settings.workDir,
    })
      .then(setDockerServices)
      .catch(() => {});
  }, [settings.workDir]);

  useEffect(() => {
    loadFiles();
    loadConversations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings.workDir]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Streaming event listeners
  useEffect(() => {
    const unlistenChunk = listen<string>("chat-chunk", (event) => {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant" && last.streaming) {
          return [
            ...prev.slice(0, -1),
            { ...last, content: last.content + event.payload },
          ];
        }
        return [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: event.payload,
            timestamp: new Date().toISOString(),
            streaming: true,
          },
        ];
      });
    });

    const unlistenDone = listen("chat-done", () => {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        const updated = last?.streaming
          ? [...prev.slice(0, -1), { ...last, streaming: false }]
          : prev;
        messagesRef.current = updated;
        return updated;
      });
      setLoading(false);

      // Auto-detect structured JSON in assistant response
      const lastMsg = messagesRef.current[messagesRef.current.length - 1];
      if (lastMsg?.role === "assistant" && lastMsg.content) {
        const jsonBlockMatch = lastMsg.content.match(/```json\s*\n([\s\S]*?)\n```/);
        if (jsonBlockMatch) {
          try {
            const parsed = JSON.parse(jsonBlockMatch[1]);
            const detectedType = routeToComponent(parsed);
            if (detectedType !== "text") {
              setPreviewContent({ name: "检测结果", content: JSON.stringify(parsed, null, 2) });
              setPreviewType(detectedType);
            }
          } catch {
            // Not valid JSON, ignore
          }
        }
      }

      const pending = pendingSaveRef.current;
      if (pending) {
        const allMsgs = messagesRef.current;
        const firstUserMsg = allMsgs.find((m) => m.role === "user");
        invoke("save_conversation", {
          record: {
            id: sessionIdRef.current,
            title: firstUserMsg
              ? firstUserMsg.content.slice(0, 50)
              : pending.text.slice(0, 50),
            created_at:
              allMsgs[0]?.timestamp || pending.userMsg.timestamp,
            updated_at: new Date().toISOString(),
            work_dir: settingsRef.current.workDir,
            cli_ide: settingsRef.current.cliIde,
            session_id: sessionIdRef.current,
            messages: allMsgs,
          },
        })
          .then(() => {
            invoke<Conversation[]>("list_conversations", {
              workDir: settingsRef.current.workDir,
            })
              .then(setConversations)
              .catch(() => {});
          })
          .catch((e) => {
            console.warn("Save conversation failed:", e);
          });
        pendingSaveRef.current = null;
      }
    });

    const unlistenError = listen<string>("chat-error", (event) => {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `⚠️ ${event.payload}`,
          timestamp: new Date().toISOString(),
        },
      ]);
      setLoading(false);
      pendingSaveRef.current = null;
    });

    return () => {
      unlistenChunk.then((fn) => fn());
      unlistenDone.then((fn) => fn());
      unlistenError.then((fn) => fn());
    };
  }, []);

  const loadFiles = async () => {
    try {
      const result = await invoke<FileNode[]>("list_workspace_files", {
        workDir: settings.workDir,
      });
      setFiles(result);
    } catch (e) {
      console.error("Failed to load files:", e);
      setFiles([
        {
          name: "output",
          path: "output",
          is_dir: true,
          children: [
            { name: "drafts", path: "output/drafts", is_dir: true },
            { name: "notes", path: "output/notes", is_dir: true },
            { name: "logs", path: "output/logs", is_dir: true },
          ],
        },
      ]);
    }
  };

  const loadConversations = async () => {
    try {
      const result = await invoke<Conversation[]>("list_conversations", {
        workDir: settings.workDir,
      });
      setConversations(result);
    } catch (e) {
      console.error("Failed to load conversations:", e);
      setConversations([]);
    }
  };

  const handleSend = async (text: string) => {
    if (!text.trim() || loading) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };
    const isFirst = messages.length === 0;
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    pendingSaveRef.current = { userMsg, text };

    try {
      await invoke("chat_send", {
        message: text,
        cliIde: settings.cliIde,
        workDir: settings.workDir,
        cliPath: settings.cliPath || null,
        sessionId: sessionId,
        isFirst: isFirst,
      });
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `⚠️ ${e}`,
          timestamp: new Date().toISOString(),
        },
      ]);
      setLoading(false);
      pendingSaveRef.current = null;
    }
  };

  const handleFileClick = async (path: string, name: string) => {
    try {
      const content = await invoke<string>("read_file", {
        path,
        workDir: settings.workDir,
      });
      setPreviewContent({ name, content });

      // Detect content type for smart routing
      const lowerName = name.toLowerCase();
      if (lowerName.endsWith(".json")) {
        try {
          const parsed = JSON.parse(content);
          setPreviewType(routeToComponent(parsed));
        } catch {
          setPreviewType("text");
        }
      } else if (lowerName.endsWith(".md") || lowerName.endsWith(".tex")) {
        setPreviewType("markdown");
      } else {
        setPreviewType("text");
      }
    } catch (e) {
      setPreviewContent({ name, content: `无法读取文件: ${e}` });
      setPreviewType("text");
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setActiveConversation(null);
    setSessionId(crypto.randomUUID());
    pendingSaveRef.current = null;
  };

  const handleSelectConversation = async (convId: string) => {
    try {
      const record = await invoke<ConversationRecord>("load_conversation", {
        id: convId,
        workDir: settings.workDir,
      });
      setMessages(
        record.messages.map((m) => ({
          id: m.id,
          role: m.role as "user" | "assistant",
          content: m.content,
          timestamp: m.timestamp,
        }))
      );
      setSessionId(record.session_id || convId);
      setActiveConversation(convId);
    } catch (e) {
      console.error("Failed to load conversation:", e);
    }
  };

  const handleStop = async () => {
    try {
      await invoke("stop_generation", { sessionId: sessionId || null });
    } catch (e) {
      console.error(e);
    }
  };

  const handleSkillClick = (skill: SkillInfo) => {
    setInputText(`/${skill.name} `);
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        const len = skill.name.length + 2;
        textareaRef.current.setSelectionRange(len, len);
      }
    }, 0);
  };

  const handleFillInput = (text: string) => {
    setInputText(text);
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        const len = text.length;
        textareaRef.current.setSelectionRange(len, len);
      }
    }, 0);
  };

  return (
    <div className="app-layout">
      {/* Left: Sidebar with Tabs */}
      <aside className="sidebar-left">
        <div className="sidebar-tabs">
          <button
            className={`sidebar-tab ${sidebarTab === "files" ? "active" : ""}`}
            onClick={() => setSidebarTab("files")}
          >
            文件
          </button>
          <button
            className={`sidebar-tab ${sidebarTab === "skills" ? "active" : ""}`}
            onClick={() => setSidebarTab("skills")}
          >
            技能
          </button>
        </div>

        {sidebarTab === "files" ? (
          <FileTree
            files={files}
            fileFilter={fileFilter}
            setFileFilter={setFileFilter}
            onFileClick={handleFileClick}
            onRefresh={loadFiles}
          />
        ) : (
          <SkillPanel skills={skills} onSkillClick={handleSkillClick} />
        )}
      </aside>

      {/* Center: Chat */}
      <main className="chat-main">
        <header className="chat-header">
          <div className="chat-header-left">
            <button className="new-chat-btn" onClick={handleNewChat}>
              <Plus size={14} /> 新对话
            </button>
          </div>
          <div className="chat-header-center">
            <h1 className="app-title">Scholar Studio</h1>
            {settings.workDir && (
              <span className="workspace-badge" title={settings.workDir}>
                {settings.workDir.split(/[\\/]/).pop() || settings.workDir}
              </span>
            )}
          </div>
          <div className="chat-header-right">
            {health && (
              <button
                className={`health-badge ${health.overall ? "healthy" : "unhealthy"}`}
                title={health.overall ? "系统健康" : "部分组件不可用，点击设置查看"}
                onClick={onOpenSettings}
              >
                <Circle size={8} fill="currentColor" />
                <span>{health.overall ? "正常" : "异常"}</span>
              </button>
            )}
            {dockerServices.length > 0 &&
              dockerServices.map((svc) => (
                <span
                  key={svc.name}
                  className={`docker-indicator ${svc.running ? "running" : "stopped"}`}
                  title={`${svc.name}: ${svc.status}`}
                  onClick={onOpenSettings}
                />
              ))}
            <span className="backend-badge">
              {settings.cliIde === "qoder-cli" ? "Qoder CLI" : "Claude Code"}
            </span>
            <button
              className="icon-btn"
              onClick={onOpenSettings}
              title="设置"
            >
              <SettingsIcon size={16} />
            </button>
          </div>
        </header>

        <div className="messages-container">
          {messages.length === 0 ? (
            <WelcomeScreen
              onSend={handleSend}
              onFillInput={handleFillInput}
            />
          ) : (
            messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} onVisualize={handleVisualize} />
            ))
          )}
          {loading &&
            messages[messages.length - 1]?.role !== "assistant" && (
              <TypingIndicator />
            )}
          <div ref={messagesEndRef} />
        </div>

        <ChatInput
          text={inputText}
          setText={setInputText}
          onSend={handleSend}
          onStop={handleStop}
          loading={loading}
          textareaRef={textareaRef}
        />
      </main>

      {/* Right: Conversation History */}
      <aside className="sidebar-right">
        <ConversationList
          conversations={conversations}
          activeConversation={activeConversation}
          onSelect={handleSelectConversation}
          onRefresh={loadConversations}
        />
      </aside>

      {previewContent && (
        <div
          className="preview-overlay"
          onClick={() => setPreviewContent(null)}
        >
          <div
            className="preview-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="preview-header">
              <span className="preview-title">{previewContent.name}</span>
              <button
                className="icon-btn"
                onClick={() => setPreviewContent(null)}
              >
                ✕
              </button>
            </div>
            <div className="preview-content">
              {previewType === "citation_graph" && (
                <CitationGraph
                  data={JSON.parse(previewContent.content) as CitationGraphData}
                />
              )}
              {previewType === "paper_reader" && (
                <PaperReader
                  data={JSON.parse(previewContent.content) as PaperCardData}
                />
              )}
              {previewType === "quality_radar" && (
                <QualityRadar
                  data={JSON.parse(previewContent.content) as QualityRadarData}
                />
              )}
              {previewType === "kb_dashboard" && (
                <KBDashboard
                  data={JSON.parse(previewContent.content) as KBDashboardData}
                />
              )}
              {previewType === "experiment_metrics" && (
                <ExperimentMetrics
                  data={JSON.parse(previewContent.content) as ExperimentMetricsData}
                />
              )}
              {previewType === "timeline" && (
                <Timeline
                  data={JSON.parse(previewContent.content) as TimelineData}
                />
              )}
              {previewType === "markdown" && (
                <MessageBubble
                  message={{
                    id: "preview",
                    role: "assistant",
                    content: previewContent.content,
                    timestamp: new Date().toISOString(),
                  }}
                />
              )}
              {previewType === "text" && (
                <pre className="preview-text">{previewContent.content}</pre>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
