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

from document_db_mcp.repositories import (
    AgentItemRepository,
    AgentSessionRepository,
    AgentTaskRepository,
    IssueRepository,
    WikiPageRepository,
)
from document_db_mcp.schemas import (
    AgentItemCreate,
    AgentSessionCreate,
    AgentTaskCreate,
    AgentTaskUpdate,
    IssueCreate,
    IssueUpdate,
    WikiPageCreate,
)

_DSN = os.environ.get(
    "DOC_DB_TEST_DSN",
    "postgres://devteam:devteam_postgres@localhost:5432/dev_team",
)


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    p = await asyncpg.create_pool(dsn=_DSN, min_size=1, max_size=2)
    try:
        # 각 테스트 시작 시 전체 정리 (간단한 인프라 — production 와 충돌 X 가정)
        async with p.acquire() as conn:
            await conn.execute(
                "TRUNCATE agent_items, agent_sessions, agent_tasks, "
                "issues, wiki_pages RESTART IDENTITY CASCADE",
            )
        yield p
    finally:
        await p.close()


class TestAgentTaskRepository:
    async def test_create_and_get(self, pool: asyncpg.Pool) -> None:
        repo = AgentTaskRepository(pool)
        created = await repo.create(AgentTaskCreate(title="t1"))
        fetched = await repo.get(created.id)
        assert fetched is not None
        assert fetched.title == "t1"
        assert fetched.status == "open"

    async def test_update_patch(self, pool: asyncpg.Pool) -> None:
        repo = AgentTaskRepository(pool)
        created = await repo.create(AgentTaskCreate(title="t1"))
        updated = await repo.update(created.id, AgentTaskUpdate(status="done"))
        assert updated is not None
        assert updated.status == "done"
        assert updated.title == "t1"   # patch 는 명시 필드만

    async def test_list_count_delete(self, pool: asyncpg.Pool) -> None:
        repo = AgentTaskRepository(pool)
        await repo.create(AgentTaskCreate(title="a"))
        await repo.create(AgentTaskCreate(title="b"))
        assert await repo.count() == 2
        items = await repo.list()
        assert len(items) == 2
        deleted = await repo.delete(items[0].id)
        assert deleted is True
        assert await repo.count() == 1


class TestIssueRepository:
    async def test_create_with_optimistic_locking(self, pool: asyncpg.Pool) -> None:
        repo = IssueRepository(pool)
        created = await repo.create(IssueCreate(type="story", title="X", body_md="..."))
        assert created.version == 1
        # 정상 update
        upd = await repo.update_with_version(
            created.id,
            IssueUpdate(status="confirmed"),
            expected_version=1,
        )
        assert upd is not None
        assert upd.version == 2
        assert upd.status == "confirmed"


class TestAgentSessionAndItem:
    async def test_chronicler_chain(self, pool: asyncpg.Pool) -> None:
        task_repo = AgentTaskRepository(pool)
        session_repo = AgentSessionRepository(pool)
        item_repo = AgentItemRepository(pool)

        task = await task_repo.create(AgentTaskCreate(title="conv"))
        session = await session_repo.create(AgentSessionCreate(
            agent_task_id=task.id,
            initiator="user",
            counterpart="primary",
            context_id="ctx-1",
        ))
        item1 = await item_repo.create(AgentItemCreate(
            agent_session_id=session.id,
            role="user",
            sender="user",
            content={"text": "hi"},
        ))
        item2 = await item_repo.create(AgentItemCreate(
            agent_session_id=session.id,
            prev_item_id=item1.id,
            role="agent",
            sender="primary",
            content={"text": "hello"},
        ))
        items = await item_repo.list_by_session(session.id)
        assert [i.id for i in items] == [item1.id, item2.id]
        # 특수 쿼리
        found = await session_repo.find_by_context("ctx-1")
        assert found is not None and found.id == session.id


class TestWikiPageRepository:
    async def test_slug_unique_and_get_by_slug(self, pool: asyncpg.Pool) -> None:
        repo = WikiPageRepository(pool)
        slug = f"prd-{uuid.uuid4().hex[:8]}"
        await repo.create(WikiPageCreate(
            page_type="prd", slug=slug, title="T", content_md="body",
        ))
        # 같은 slug 재시도 → 무결성 위반
        with pytest.raises(asyncpg.UniqueViolationError):
            await repo.create(WikiPageCreate(
                page_type="prd", slug=slug, title="T2", content_md="body2",
            ))
        # get_by_slug
        fetched = await repo.get_by_slug(slug)
        assert fetched is not None and fetched.slug == slug
