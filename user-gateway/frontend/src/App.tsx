import { useEffect, useState } from "react";
import { Chat } from "./components/Chat";
import { fetchAgentCard } from "./api";
import type { AgentCardSummary } from "./types";

export function App() {
  const [card, setCard] = useState<AgentCardSummary | null>(null);
  const [cardError, setCardError] = useState<string | null>(null);

  useEffect(() => {
    fetchAgentCard()
      .then(setCard)
      .catch((e) => setCardError(e instanceof Error ? e.message : String(e)));
  }, []);

  return (
    <div className="app">
      <header className="app__header">
        <h1>dev-team User Gateway</h1>
        {card ? (
          <div className="app__agent">
            <strong>{card.name}</strong>
            {card.version ? <span> · v{card.version}</span> : null}
            {card.description ? <p>{card.description}</p> : null}
          </div>
        ) : cardError ? (
          <div className="app__agent app__agent--error">
            AgentCard 조회 실패: {cardError}
          </div>
        ) : (
          <div className="app__agent">에이전트 정보 불러오는 중…</div>
        )}
      </header>
      <main className="app__main">
        <Chat />
      </main>
    </div>
  );
}
