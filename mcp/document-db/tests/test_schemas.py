"""Pydantic 스키마 단위 테스트 — DB / 컨테이너 의존 없음."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from dev_team_shared.document_db.schemas import (
    AgentItemCreate,
    AgentSessionCreate,
    AgentTaskCreate,
    IssueCreate,
    WikiPageCreate,
)


class TestAgentTaskCreate:
    def test_minimal(self) -> None:
        doc = AgentTaskCreate(title="hello")
        assert doc.status == "open"
        assert doc.metadata == {}
        assert doc.issue_refs == []

    def test_invalid_status(self) -> None:
        with pytest.raises(ValidationError):
            AgentTaskCreate(title="x", status="bogus")  # type: ignore[arg-type]

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            AgentTaskCreate(title="x", unknown_field=1)  # type: ignore[call-arg]


class TestIssueCreate:
    def test_type_required(self) -> None:
        with pytest.raises(ValidationError):
            IssueCreate(title="t", body_md="b")  # type: ignore[call-arg]

    def test_valid_types(self) -> None:
        for t in ("epic", "story", "task"):
            doc = IssueCreate(type=t, title="t", body_md="b")  # type: ignore[arg-type]
            assert doc.status == "draft"

    def test_invalid_type(self) -> None:
        with pytest.raises(ValidationError):
            IssueCreate(type="bug", title="t", body_md="b")  # type: ignore[arg-type]


class TestWikiPageCreate:
    def test_all_page_types_accepted(self) -> None:
        types = (
            "prd", "business_rule", "data_model",
            "adr", "api_contract",
            "glossary", "runbook", "generic",
        )
        for t in types:
            WikiPageCreate(
                page_type=t,  # type: ignore[arg-type]
                slug=f"slug-{t}",
                title="t",
                content_md="body",
            )

    def test_unknown_page_type(self) -> None:
        with pytest.raises(ValidationError):
            WikiPageCreate(
                page_type="meeting_minutes",  # type: ignore[arg-type]
                slug="x",
                title="t",
                content_md="b",
            )


class TestAgentSessionCreate:
    def test_minimal(self) -> None:
        doc = AgentSessionCreate(
            agent_task_id=uuid4(),
            initiator="user",
            counterpart="primary",
            context_id="ctx-1",
        )
        assert doc.trace_id is None


class TestAgentItemCreate:
    def test_role_validation(self) -> None:
        for r in ("user", "agent", "system"):
            AgentItemCreate(
                agent_session_id=uuid4(),
                role=r,  # type: ignore[arg-type]
                sender="primary",
                content={"text": "hi"},
            )

    def test_invalid_role(self) -> None:
        with pytest.raises(ValidationError):
            AgentItemCreate(
                agent_session_id=uuid4(),
                role="bot",  # type: ignore[arg-type]
                sender="x",
                content={},
            )
