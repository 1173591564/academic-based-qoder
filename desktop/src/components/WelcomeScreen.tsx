const QUICK_ACTIONS: { label: string; prompt: string; direct?: boolean }[] = [
  { label: "调研", prompt: "帮我调研以下主题：" },
  { label: "精读", prompt: "帮我深度分析这篇论文：" },
  { label: "写作", prompt: "帮我撰写学术论文：" },
  { label: "知识库", prompt: "显示知识库统计信息", direct: true },
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
            {action.label}
          </button>
        ))}
      </div>
    </div>
  );
}
