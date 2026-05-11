import { useEffect, useState } from "react";
import { createSession, listSessions } from "../api";
import type { Session } from "../types";

interface Props {
  activeSessionId: string | null;
  onSelect: (sessionId: string) => void;
  refreshKey: number; // bump to force refresh
}

/**
 * Chat session 사이드바 — 목록 / 새 대화 / 선택.
 *
 * D15 표준 키 (`title`, `last_chat_at`, `pinned`) 를 이용해 표시 / 정렬.
 * pinned 우선 → last_chat_at desc → started_at desc.
 */
export function Sidebar({ activeSessionId, onSelect, refreshKey }: Props) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    listSessions()
      .then((rows) => {
        setSessions(sortSessions(rows));
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [refreshKey]);

  const handleNew = async () => {
    try {
      const s = await createSession("primary");
      setSessions((prev) => sortSessions([s, ...prev]));
      onSelect(s.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <aside className="sidebar">
      <div className="sidebar__header">
        <button className="sidebar__new" onClick={handleNew}>
          + 새 대화
        </button>
      </div>
      {loading && <div className="sidebar__loading">로딩 중…</div>}
      {error && <div className="sidebar__error">⚠️ {error}</div>}
      <ul className="sidebar__list">
        {sessions.length === 0 && !loading && (
          <li className="sidebar__empty">대화가 없습니다</li>
        )}
        {sessions.map((s) => (
          <li
            key={s.id}
            className={
              "sidebar__item" +
              (s.id === activeSessionId ? " sidebar__item--active" : "")
            }
            onClick={() => onSelect(s.id)}
          >
            <div className="sidebar__title">
              {s.metadata.pinned ? "📌 " : ""}
              {s.metadata.title || `대화 ${s.id.slice(0, 6)}`}
            </div>
            <div className="sidebar__meta">
              {s.agent_endpoint} ·{" "}
              {formatRelative(
                (s.metadata.last_chat_at as string | undefined) || s.started_at,
              )}
            </div>
          </li>
        ))}
      </ul>
    </aside>
  );
}

function sortSessions(rows: Session[]): Session[] {
  return [...rows].sort((a, b) => {
    const pa = a.metadata.pinned ? 1 : 0;
    const pb = b.metadata.pinned ? 1 : 0;
    if (pa !== pb) return pb - pa;
    const ka = String(a.metadata.last_chat_at || a.started_at);
    const kb = String(b.metadata.last_chat_at || b.started_at);
    return kb.localeCompare(ka);
  });
}

function formatRelative(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const diff = Date.now() - t;
  const m = Math.floor(diff / 60_000);
  if (m < 1) return "방금";
  if (m < 60) return `${m}분 전`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}시간 전`;
  const d = Math.floor(h / 24);
  return `${d}일 전`;
}
