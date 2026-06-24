import type { Conversation } from "../types";

export function ConversationList({
  conversations,
  activeConversation,
  onSelect,
  onRefresh,
}: {
  conversations: Conversation[];
  activeConversation: string | null;
  onSelect: (convId: string) => void;
  onRefresh: () => void;
}) {
  return (
    <>
      <div className="sidebar-header">
        <span className="sidebar-title">历史对话</span>
        <button className="icon-btn" onClick={onRefresh} title="刷新">
          ↻
        </button>
      </div>
      <div className="conversation-list">
        {conversations.length > 0 ? (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conv-item ${activeConversation === conv.id ? "active" : ""}`}
              onClick={() => onSelect(conv.id)}
            >
              <div className="conv-title">{conv.title}</div>
              <div className="conv-preview">{conv.preview}</div>
              <div className="conv-meta">
                <span>{conv.date}</span>
                <span>{conv.messageCount} 条消息</span>
              </div>
            </div>
          ))
        ) : (
          <div className="empty-hint">暂无历史对话</div>
        )}
      </div>
    </>
  );
}
