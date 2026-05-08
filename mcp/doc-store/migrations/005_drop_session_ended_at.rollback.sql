-- step: 005_drop_session_ended_at.rollback
-- ended_at 컬럼 복원 (rollback). 기존 row 는 NULL 로.

ALTER TABLE sessions ADD COLUMN IF NOT EXISTS ended_at TIMESTAMPTZ;
