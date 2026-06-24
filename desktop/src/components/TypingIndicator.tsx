export function TypingIndicator() {
  return (
    <div className="message message-ai">
      <div className="message-avatar">AI</div>
      <div className="message-body">
        <div className="typing-dots">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    </div>
  );
}
