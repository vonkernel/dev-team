import { useEffect, useState } from "react";
import { Chat } from "./components/Chat";
import { Sidebar } from "./components/Sidebar";
import { fetchAgentCard } from "./api";
import type { AgentCardSummary } from "./types";

const ACTIVE_SESSION_KEY = "activeSessionId";

export function App() {
  const [card, setCard] = useState<AgentCardSummary | null>(null);
  const [cardError, setCardError] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(
    () => localStorage.getItem(ACTIVE_SESSION_KEY),
  );
  const [sidebarRefreshKey, setSidebarRefreshKey] = useState(0);

  useEffect(() => {
    fetchAgentCard()
      .then(setCard)
      .catch((e) => setCardError(e instanceof Error ? e.message : String(e)));
  }, []);

  useEffect(() => {
    if (activeSessionId) {
      localStorage.setItem(ACTIVE_SESSION_KEY, activeSessionId);
    }
  }, [activeSessionId]);

  return (
    <div className="app">
      <header className="app__header">
        <h1>dev-team</h1>
        {card ? (
          <div className="app__agent">
            <strong>{card.name}</strong>
            {card.version ? <span> · v{card.version}</span> : null}
          </div>
        ) : cardError ? (
          <div className="app__agent app__agent--error">
            AgentCard 조회 실패: {cardError}
          </div>
        ) : (
          <div className="app__agent">에이전트 정보 불러오는 중…</div>
        )}
      </header>
      <div className="app__body">
        <Sidebar
          activeSessionId={activeSessionId}
          onSelect={setActiveSessionId}
          refreshKey={sidebarRefreshKey}
        />
        <main className="app__main">
          {activeSessionId ? (
            <Chat
              key={activeSessionId}
              sessionId={activeSessionId}
              onSessionUpdated={() => setSidebarRefreshKey((k) => k + 1)}
            />
          ) : (
            <div className="app__welcome">
              왼쪽에서 대화를 선택하거나 + 새 대화 를 눌러 시작하세요.
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
