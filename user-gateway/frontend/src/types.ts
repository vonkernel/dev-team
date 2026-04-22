/** UG backend 가 /api/chat SSE 로 보내는 이벤트 포맷. */
export type ChatEvent =
  | { type: "meta"; contextId: string }
  | { type: "chunk"; text: string }
  | { type: "done" }
  | { type: "error"; message: string };

export type Role = "user" | "agent";

export interface ChatMessage {
  id: string;
  role: Role;
  text: string;
  streaming?: boolean;
  failed?: boolean;
}

/** /api/agent-card 응답 — 표시에 쓰는 최소 필드만 추출. */
export interface AgentCardSummary {
  name: string;
  description?: string;
  version?: string;
}
