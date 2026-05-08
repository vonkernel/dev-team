"""Repository 통합 테스트 — 실 Postgres 사용.

`docker compose --profile mcp up -d` 가 띄운 Postgres `dev_team` DB 에 직접 연결.
독립 실행을 원하면 testcontainers 도입 (M5+).

CI 자동화를 위해 환경변수 `DOC_DB_TEST_DSN` 으로 별 DB 지정 가능.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio
from dev_team_shared.doc_store.schemas import (
    A2AContextCreate,
    A2AMessageCreate,
    A2ATaskCreate,
    AssignmentCreate,
    AssignmentUpdate,
    ChatCreate,
    IssueCreate,
    IssueUpdate,
    SessionCreate,
    WikiPageCreate,
)

from doc_store_mcp.repositories import (
    A2AContextRepository,
    A2AMessageRepository,
    A2ATaskRepository,
    AssignmentRepository,
    ChatRepository,
    IssueRepository,
    SessionRepository,
    WikiPageRepository,
)

_DSN = os.environ.get(
    "DOC_DB_TEST_DSN",
    "postgres://devteam:devteam_postgres@localhost:5432/dev_team",
)

_TRUNCATE_SQL = """
    TRUNCATE
        a2a_task_artifacts,
        a2a_task_status_updates,
        a2a_messages,
        a2a_tasks,
        a2a_contexts,
        chats,
        assignments,
        sessions,
        issues,
        wiki_pages
    RESTART IDENTITY CASCADE
"""


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    p = await asyncpg.create_pool(dsn=_DSN, min_size=1, max_size=2)
    try:
        async with p.acquire() as conn:
            await conn.execute(_TRUNCATE_SQL)
        yield p
    finally:
        await p.close()


# ──────────────────────────────────────────────────────────────────────────
# Chat tier
# ──────────────────────────────────────────────────────────────────────────


class TestSessionRepository:
    async def test_create_and_get(self, pool: asyncpg.Pool) -> None:
        repo = SessionRepository(pool)
        created = await repo.create(SessionCreate(
            agent_endpoint="primary", counterpart="primary",
        ))
        fetched = await repo.get(created.id)
        assert fetched is not None
        assert fetched.agent_endpoint == "primary"
        assert fetched.initiator == "user"


class TestChatRepository:
    async def test_chat_chain(self, pool: asyncpg.Pool) -> None:
        session_repo = SessionRepository(pool)
        chat_repo = ChatRepository(pool)
        sess = await session_repo.create(SessionCreate(
            agent_endpoint="primary", counterpart="primary",
        ))
        c1 = await chat_repo.create(ChatCreate(
            session_id=sess.id, role="user", sender="user",
            content=[{"text": "hi"}],
        ))
        c2 = await chat_repo.create(ChatCreate(
            session_id=sess.id, prev_chat_id=c1.id,
            role="agent", sender="primary",
            content=[{"text": "hello"}],
        ))
        chats = await chat_repo.list_by_session(sess.id)
        assert [c.id for c in chats] == [c1.id, c2.id]

    async def test_immutable_update_raises(self, pool: asyncpg.Pool) -> None:
        from pydantic import BaseModel

        class _Empty(BaseModel):
            pass

        chat_repo = ChatRepository(pool)
        with pytest.raises(NotImplementedError):
            await chat_repo.update(uuid.uuid4(), _Empty())


class TestAssignmentRepository:
    async def test_create_and_update(self, pool: asyncpg.Pool) -> None:
        repo = AssignmentRepository(pool)
        created = await repo.create(AssignmentCreate(title="결제 모듈"))
        assert created.status == "open"
        updated = await repo.update(
            created.id, AssignmentUpdate(status="in_progress"),
        )
        assert updated is not None
        assert updated.status == "in_progress"

    async def test_list_by_session(self, pool: asyncpg.Pool) -> None:
        session_repo = SessionRepository(pool)
        repo = AssignmentRepository(pool)
        sess = await session_repo.create(SessionCreate(
            agent_endpoint="primary", counterpart="primary",
        ))
        a = await repo.create(AssignmentCreate(
            title="A", root_session_id=sess.id,
        ))
        await repo.create(AssignmentCreate(title="B"))  # 다른 session 발
        listed = await repo.list_by_session(sess.id)
        assert [x.id for x in listed] == [a.id]


# ──────────────────────────────────────────────────────────────────────────
# A2A tier
# ──────────────────────────────────────────────────────────────────────────


class TestA2ATier:
    async def test_context_message_task_chain(self, pool: asyncpg.Pool) -> None:
        ctx_repo = A2AContextRepository(pool)
        msg_repo = A2AMessageRepository(pool)
        task_repo = A2ATaskRepository(pool)

        ctx = await ctx_repo.create(A2AContextCreate(
            context_id="ctx-1",
            initiator_agent="primary",
            counterpart_agent="engineer",
        ))
        # standalone Message
        m1 = await msg_repo.create(A2AMessageCreate(
            message_id="msg-1",
            a2a_context_id=ctx.id,
            role="user", sender="primary",
            parts=[{"kind": "text", "text": "안녕"}],
        ))
        # Task 생성 후 Task.history 의 message
        task = await task_repo.create(A2ATaskCreate(
            task_id="task-xyz", a2a_context_id=ctx.id,
        ))
        m2 = await msg_repo.create(A2AMessageCreate(
            message_id="msg-2",
            a2a_context_id=ctx.id,
            a2a_task_id=task.id,
            role="agent", sender="engineer",
            parts=[{"kind": "text", "text": "ok"}],
        ))
        # list_by_context 는 둘 다, list_by_task 는 m2 만
        all_msgs = await msg_repo.list_by_context(ctx.id)
        assert {m.id for m in all_msgs} == {m1.id, m2.id}
        task_msgs = await msg_repo.list_by_task(task.id)
        assert [m.id for m in task_msgs] == [m2.id]
        # find_by_context_id / find_by_task_id
        found_ctx = await ctx_repo.find_by_context_id("ctx-1")
        assert found_ctx is not None and found_ctx.id == ctx.id
        found_task = await task_repo.find_by_task_id("task-xyz")
        assert found_task is not None and found_task.id == task.id


# ──────────────────────────────────────────────────────────────────────────
# 도메인 산출물
# ──────────────────────────────────────────────────────────────────────────


class TestIssueRepository:
    async def test_create_with_optimistic_locking(self, pool: asyncpg.Pool) -> None:
        repo = IssueRepository(pool)
        created = await repo.create(IssueCreate(type="story", title="X", body_md="..."))
        assert created.version == 1
        upd = await repo.update_with_version(
            created.id,
            IssueUpdate(status="confirmed"),
            expected_version=1,
        )
        assert upd is not None
        assert upd.version == 2
        assert upd.status == "confirmed"


class TestWikiPageRepository:
    async def test_slug_unique_and_get_by_slug(self, pool: asyncpg.Pool) -> None:
        repo = WikiPageRepository(pool)
        slug = f"prd-{uuid.uuid4().hex[:8]}"
        await repo.create(WikiPageCreate(
            page_type="prd", slug=slug, title="T", content_md="body",
        ))
        with pytest.raises(asyncpg.UniqueViolationError):
            await repo.create(WikiPageCreate(
                page_type="prd", slug=slug, title="T2", content_md="body2",
            ))
        fetched = await repo.get_by_slug(slug)
        assert fetched is not None and fetched.slug == slug
