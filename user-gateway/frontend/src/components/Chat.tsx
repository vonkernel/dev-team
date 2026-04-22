import { useCallback, useEffect, useRef, useState } from "react";
import { streamChat } from "../api";
import type { ChatMessage } from "../types";
import { MessageBubble } from "./MessageBubble";

export function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [contextId, setContextId] = useState<string | null>(null);
  const listEndRef = useRef<HTMLDivElement>(null);

  // 새 메시지 / 스트림 chunk 도착 시 맨 아래로 스크롤
  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const updateMessage = useCallback(
    (id: string, updater: (m: ChatMessage) => ChatMessage) => {
      setMessages((prev) => prev.map((m) => (m.id === id ? updater(m) : m)));
    },
    [],
  );

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || sending) return;

    const userId = crypto.randomUUID();
    const agentId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", text },
      { id: agentId, role: "agent", text: "", streaming: true },
    ]);
    setInput("");
    setSending(true);

    const ctrl = new AbortController();
    try {
      for await (const evt of streamChat(text, contextId, ctrl.signal)) {
        if (evt.type === "meta") {
          if (!contextId) setContextId(evt.contextId);
        } else if (evt.type === "chunk") {
          updateMessage(agentId, (m) => ({ ...m, text: m.text + evt.text }));
        } else if (evt.type === "done") {
          updateMessage(agentId, (m) => ({ ...m, streaming: false }));
          break;
        } else if (evt.type === "error") {
          updateMessage(agentId, (m) => ({
            ...m,
            text: m.text ? `${m.text}\n\n⚠️ ${evt.message}` : `⚠️ ${evt.message}`,
            streaming: false,
            failed: true,
          }));
          break;
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      updateMessage(agentId, (m) => ({
        ...m,
        text: m.text ? `${m.text}\n\n⚠️ ${msg}` : `⚠️ ${msg}`,
        streaming: false,
        failed: true,
      }));
    } finally {
      setSending(false);
    }
  }, [input, sending, contextId, updateMessage]);

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  };

  return (
    <div className="chat">
      <div className="chat__list">
        {messages.length === 0 && (
          <div className="chat__empty">메시지를 입력해 Primary 와 대화해 보세요.</div>
        )}
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        <div ref={listEndRef} />
      </div>
      <div className="chat__input">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Enter 전송 · Shift+Enter 줄바꿈"
          rows={2}
          disabled={sending}
        />
        <button onClick={() => void send()} disabled={sending || !input.trim()}>
          {sending ? "…" : "전송"}
        </button>
      </div>
      {contextId && (
        <div className="chat__meta">thread: {contextId.slice(0, 8)}…</div>
      )}
    </div>
  );
}
