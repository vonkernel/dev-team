import type {
  AgentCardSummary,
  HistoryChat,
  Session,
} from "./types";

export async function fetchAgentCard(): Promise<AgentCardSummary> {
  const res = await fetch("/api/agent-card");
  if (!res.ok) throw new Error(`agent-card HTTP ${res.status}`);
  const raw = await res.json();
  return {
    name: raw.name ?? "(unknown)",
    description: raw.description,
    version: raw.version,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Sessions — chat 대화창 CRUD (#75 PR 4)
// ─────────────────────────────────────────────────────────────────────────────

export async function createSession(
  agentEndpoint: string = "primary",
): Promise<Session> {
  const res = await fetch("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_endpoint: agentEndpoint }),
  });
  if (!res.ok) throw new Error(`createSession HTTP ${res.status}`);
  return res.json();
}

export async function listSessions(): Promise<Session[]> {
  const res = await fetch("/api/sessions");
  if (!res.ok) throw new Error(`listSessions HTTP ${res.status}`);
  return res.json();
}

export async function getHistory(sessionId: string): Promise<HistoryChat[]> {
  const res = await fetch(`/api/history?session_id=${sessionId}`);
  if (!res.ok) throw new Error(`getHistory HTTP ${res.status}`);
  return res.json();
}

export async function patchSession(
  sessionId: string,
  metadata: Record<string, unknown>,
): Promise<Session> {
  const res = await fetch(`/api/sessions/${sessionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ metadata }),
  });
  if (!res.ok) throw new Error(`patchSession HTTP ${res.status}`);
  return res.json();
}

// ─────────────────────────────────────────────────────────────────────────────
// Chat — 발화 제출 + 영속 SSE
// ─────────────────────────────────────────────────────────────────────────────

export async function sendChat(
  sessionId: string,
  text: string,
  messageId?: string,
): Promise<{ status: string; message_id: string }> {
  const body: Record<string, unknown> = { session_id: sessionId, text };
  if (messageId) body.message_id = messageId;
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`sendChat HTTP ${res.status}`);
  return res.json();
}

/**
 * 영속 SSE 채널. EventSource native — auto-reconnect 미사용 (재연결은 caller 가
 * `getHistory` hydrate 후 새 EventSource — D14 정책).
 */
export function openStream(sessionId: string): EventSource {
  return new EventSource(`/api/stream?session_id=${sessionId}`);
}
