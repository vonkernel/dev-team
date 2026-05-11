/** chat protocol SSE 이벤트 (서버 → FE). */
export type ChatStreamEvent =
  | { type: "meta"; payload: { session_id: string } }
  | { type: "queued"; payload: { message_id: string; queue_depth?: number } }
  | { type: "chunk"; payload: { text: string; message_id: string; chat_id?: string } }
  | {
      type: "message";
      payload: {
        message_id: string;
        chat_id?: string;
        prev_chat_id?: string | null;
        role: "user" | "agent" | "system";
        text: string;
      };
    }
  | { type: "done"; payload: { message_id: string } }
  | { type: "error"; payload: { message: string } };

export type Role = "user" | "agent" | "system";

/** sessions row (chat 대화창). */
export interface Session {
  id: string;
  agent_endpoint: string;
  initiator: string;
  counterpart: string;
  metadata: Record<string, unknown> & {
    title?: string;
    last_chat_at?: string;
    pinned?: boolean;
  };
  started_at: string;
}

/** /api/history 응답의 한 row. */
export interface HistoryChat {
  id: string;
  session_id: string;
  role: Role;
  sender: string;
  content: Array<{ text?: string }>;
  message_id?: string | null;
  created_at: string;
}

/** UI 상 한 chat 버블. */
export interface ChatMessage {
  id: string;
  role: Role;
  text: string;
  streaming?: boolean;
  failed?: boolean;
  message_id?: string;
  /** chats.id — last_chat_id 추적 (#75 PR 4). history hydrate / SSE 로 수집. */
  chat_id?: string;
}

/** /api/agent-card 응답 — 표시에 쓰는 최소 필드. */
export interface AgentCardSummary {
  name: string;
  description?: string;
  version?: string;
}
