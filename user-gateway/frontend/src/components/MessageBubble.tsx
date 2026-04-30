import type { ChatMessage } from "../types";

interface Props {
  message: ChatMessage;
  /** 실패한 agent 버블에 한해 "다시 시도" 버튼을 노출할 때 제공. */
  onRetry?: () => void;
  retryDisabled?: boolean;
}

export function MessageBubble({ message, onRetry, retryDisabled }: Props) {
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
      {message.failed && onRetry && (
        <button
          className="bubble__retry"
          onClick={onRetry}
          disabled={retryDisabled}
          type="button"
        >
          {retryDisabled ? "전송 중…" : "↻ 다시 시도"}
        </button>
      )}
    </div>
  );
}
