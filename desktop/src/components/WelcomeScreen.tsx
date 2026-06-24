import { Search, BookOpen, PenTool, Database, type LucideIcon } from "lucide-react";

const QUICK_ACTIONS: {
  label: string;
  desc: string;
  icon: LucideIcon;
  prompt: string;
  direct?: boolean;
}[] = [
  { label: "调研", desc: "系统性文献综述", icon: Search, prompt: "帮我调研以下主题：" },
  { label: "精读", desc: "深度论文分析", icon: BookOpen, prompt: "帮我深度分析这篇论文：" },
  { label: "写作", desc: "学术论文撰写", icon: PenTool, prompt: "帮我撰写学术论文：" },
  { label: "知识库", desc: "查看统计概览", icon: Database, prompt: "显示知识库统计信息", direct: true },
];

export function WelcomeScreen({
  onSend,
  onFillInput,
}: {
  onSend: (text: string) => void;
  onFillInput: (text: string) => void;
}) {
  return (
    <div className="welcome-screen">
      <div className="welcome-logo-icon">
        <BookOpen size={40} strokeWidth={1.5} />
      </div>
      <div className="welcome-logo">Scholar Studio</div>
      <p className="welcome-subtitle">AI 学术研究助手 · 开箱即用</p>
      <div className="quick-actions">
        {QUICK_ACTIONS.map((action) => (
          <button
            key={action.label}
            className="quick-action-btn"
            onClick={() =>
              action.direct ? onSend(action.prompt) : onFillInput(action.prompt)
            }
          >
            <action.icon size={18} className="quick-action-icon" />
            <div className="quick-action-text">
              <div className="quick-action-label">{action.label}</div>
              <div className="quick-action-desc">{action.desc}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
