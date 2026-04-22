import type { ChatMessage } from "../types";

export function MessageBubble({ message }: { message: ChatMessage }) {
  const side = message.role === "user" ? "bubble--user" : "bubble--agent";
  const status = message.failed
    ? " bubble--failed"
    : message.streaming
      ? " bubble--streaming"
      : "";
  return (
    <div className={`bubble ${side}${status}`}>
      <div className="bubble__role">{message.role === "user" ? "나" : "Primary"}</div>
      <div className="bubble__text">
        {message.text || (message.streaming ? "…" : "")}
      </div>
    </div>
  );
}
