import type { AgentCardSummary, ChatEvent } from "./types";

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

/**
 * /api/chat POST → SSE 스트림을 파싱하여 비동기 이벤트 iterator 로 내놓는다.
 * 브라우저 EventSource 는 GET 만 되어 사용 불가 — fetch + ReadableStream 으로 직접 파싱.
 */
export async function* streamChat(
  text: string,
  contextId: string | null,
  signal: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ text, context_id: contextId }),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`chat HTTP ${res.status}`);
  }
  const decoder = new TextDecoder();
  const reader = res.body.getReader();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    // SSE 이벤트는 빈 줄("\n\n") 로 구분.
    let splitAt;
    while ((splitAt = buf.indexOf("\n\n")) !== -1) {
      const raw = buf.slice(0, splitAt);
      buf = buf.slice(splitAt + 2);
      const dataLines = raw
        .split("\n")
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).trim());
      if (dataLines.length === 0) continue;
      const payload = dataLines.join("\n");
      try {
        yield JSON.parse(payload) as ChatEvent;
      } catch {
        // skip malformed
      }
    }
  }
}
