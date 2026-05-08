-- step: 005_drop_session_ended_at
-- #75 PR 3: session 은 종료 개념 없음 (사용자가 언제든 재개) — sessions.ended_at
-- 컬럼 폐기. SessionEndEvent / SessionEndProcessor / publish_session_end 도
-- 함께 제거됨. archive 가 필요해지면 별 컬럼 (archived_at) 으로.

ALTER TABLE sessions DROP COLUMN IF EXISTS ended_at;
