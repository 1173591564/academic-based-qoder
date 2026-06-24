import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";
import type { ChatMessage } from "../types";

// Detect paper IDs in text (ULID or arXiv ID)
function detectPaperIds(content: string): string[] {
  const ulidPattern = /01K[0-9A-Z]{23}/g;
  const arxivPattern = /\b\d{4}\.\d{4,5}\b/g;
  const ids = new Set<string>();
  content.match(ulidPattern)?.forEach((id) => ids.add(id));
  content.match(arxivPattern)?.forEach((id) => ids.add(id));
  return Array.from(ids);
}

export function MessageBubble({
  message,
  onVisualize,
}: {
  message: ChatMessage;
  onVisualize?: (tool: string, paperId: string) => void;
}) {
  const isUser = message.role === "user";
  const paperIds = !isUser && onVisualize ? detectPaperIds(message.content) : [];
  const firstPaperId = paperIds[0];

  return (
    <div className={`message ${isUser ? "message-user" : "message-ai"}`}>
      <div className="message-avatar">{isUser ? "你" : "AI"}</div>
      <div className="message-body">
        {isUser ? (
          <div className="message-content">{message.content}</div>
        ) : (
          <div className="message-content markdown-body">
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkMath]}
              rehypePlugins={[rehypeHighlight, rehypeKatex]}
            >
              {message.content}
            </ReactMarkdown>
            {message.streaming && <span className="streaming-cursor">▋</span>}
            {firstPaperId && !message.streaming && (
              <div className="viz-buttons">
                <button className="viz-btn" onClick={() => onVisualize!("scholar_get_citation_graph", firstPaperId)}>
                  引用网络
                </button>
                <button className="viz-btn" onClick={() => onVisualize!("scholar_get_paper_card", firstPaperId)}>
                  论文详情
                </button>
                <button className="viz-btn" onClick={() => onVisualize!("scholar_get_quality_radar", firstPaperId)}>
                  质量评估
                </button>
                <button className="viz-btn" onClick={() => onVisualize!("scholar_get_experiment_metrics", firstPaperId)}>
                  实验指标
                </button>
              </div>
            )}
          </div>
        )}
        <div className="message-time">
          {new Date(message.timestamp).toLocaleTimeString("zh-CN", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      </div>
    </div>
  );
}
