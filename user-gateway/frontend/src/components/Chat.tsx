import { useCallback, useEffect, useRef, useState } from "react";
import { getHistory, openStream, sendChat } from "../api";
import type { ChatMessage, ChatStreamEvent } from "../types";
import { MessageBubble } from "./MessageBubble";

interface Props {
  sessionId: string;
  onSessionUpdated?: () => void;
}

/**
 * 단일 chat session 의 대화 view (#75 PR 4).
 *
 * - 마운트 시: GET /api/history 로 hydrate
 * - GET /api/stream 영속 SSE 연결 — chunk / message / done / error 처리
 * - POST /api/chat 으로 사용자 발화 제출 (202 ack)
 * - SSE 끊김 시: history hydrate + 새 SSE (D14 — 옵션 B)
 */
export function Chat({ sessionId, onSessionUpdated }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listEndRef = useRef<HTMLDivElement>(null);
  const sseRef = useRef<EventSource | null>(null);
  /** chats chain — 다음 user turn 의 prev_chat_id 로 보냄 (#75 PR 4). */
  const lastChatIdRef = useRef<string | null>(null);

  // 마운트 / sessionId 변경 시 hydrate + SSE 재연결
  useEffect(() => {
    let cancelled = false;

    const setup = async () => {
      try {
        const history = await getHistory(sessionId);
        if (cancelled) return;
        setMessages(
          history.map((c) => ({
            id: c.id,
            role: c.role,
            text: extractText(c.content),
            message_id: c.message_id || undefined,
            chat_id: c.id,
          })),
        );
        // last_chat_id 는 history 의 마지막 chat — 다음 user turn 의 prev_chat_id
        lastChatIdRef.current = history.length
          ? history[history.length - 1].id
          : null;
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }

      if (sseRef.current) sseRef.current.close();
      const es = openStream(sessionId);
      sseRef.current = es;
      es.onmessage = (ev) => handleSSEEvent(ev.data);
      es.onerror = () => {
        // EventSource native 가 auto-reconnect 하지만 우리 design 은
        // history hydrate + 새 SSE (D14). 단순화 — 첫 error 만 표시.
      };
    };

    void setup();

    return () => {
      cancelled = true;
      if (sseRef.current) sseRef.current.close();
      sseRef.current = null;
    };
  }, [sessionId]);

  // 새 메시지 / chunk 도착 시 맨 아래로 스크롤
  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSSEEvent = useCallback(
    (raw: string) => {
      let ev: ChatStreamEvent;
      try {
        ev = JSON.parse(raw) as ChatStreamEvent;
      } catch {
        return;
      }
      if (ev.type === "chunk") {
        const mid = ev.payload.message_id;
        const cid = ev.payload.chat_id;
        const text = ev.payload.text;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.message_id === mid && last.role === "agent" && last.streaming) {
            return [
              ...prev.slice(0, -1),
              { ...last, text: last.text + text, chat_id: cid ?? last.chat_id },
            ];
          }
          // 새 agent message — streaming 시작
          return [
            ...prev,
            {
              id: `agent-${mid}`,
              role: "agent",
              text,
              streaming: true,
              message_id: mid,
              chat_id: cid,
            },
          ];
        });
      } else if (ev.type === "message") {
        // 완성된 agent message — streaming 종료. (chunks 이미 보였으면 streaming 해제)
        const cid = ev.payload.chat_id;
        if (cid) lastChatIdRef.current = cid;  // 다음 user turn 의 prev_chat_id
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.message_id === ev.payload.message_id) {
            return [
              ...prev.slice(0, -1),
              {
                ...last,
                text: ev.payload.text,
                streaming: false,
                chat_id: cid ?? last.chat_id,
              },
            ];
          }
          return [
            ...prev,
            {
              id: `agent-${ev.payload.message_id}`,
              role: "agent",
              text: ev.payload.text,
              message_id: ev.payload.message_id,
              chat_id: cid,
            },
          ];
        });
      } else if (ev.type === "done") {
        setMessages((prev) =>
          prev.map((m) =>
            m.message_id && m.streaming ? { ...m, streaming: false } : m,
          ),
        );
        onSessionUpdated?.();
      } else if (ev.type === "error") {
        setError(ev.payload.message);
        setMessages((prev) =>
          prev.map((m) => (m.streaming ? { ...m, streaming: false, failed: true } : m)),
        );
      }
    },
    [onSessionUpdated],
  );

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);
    setError(null);
    const tempId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      { id: `user-${tempId}`, role: "user", text },
    ]);
    try {
      const ack = await sendChat(
        sessionId, text, undefined, lastChatIdRef.current ?? undefined,
      );
      // 서버가 user_chat_id 발급 — UI 버블의 chat_id 갱신 + last_chat_id 후보
      // (agent 응답이 도착하면 그게 last_chat_id 가 되지만, 사용자 발화도
      // chain 상 최신이므로 일단 갱신해 둠)
      if (ack.chat_id) {
        const userChatId = ack.chat_id;
        lastChatIdRef.current = userChatId;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === `user-${tempId}` ? { ...m, chat_id: userChatId } : m,
          ),
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setMessages((prev) =>
        prev.map((m) =>
          m.id === `user-${tempId}` ? { ...m, failed: true } : m,
        ),
      );
    } finally {
      setSending(false);
    }
  }, [input, sending, sessionId]);

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
          <div className="chat__empty">메시지를 입력해 대화를 시작하세요</div>
        )}
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        <div ref={listEndRef} />
      </div>
      {error && <div className="chat__error">⚠️ {error}</div>}
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
      <div className="chat__meta">session: {sessionId.slice(0, 8)}…</div>
    </div>
  );
}

function extractText(content: Array<{ text?: string }>): string {
  for (const p of content) {
    if (p.text) return p.text;
  }
  return "";
}
