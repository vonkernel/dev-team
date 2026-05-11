"""Pydantic 스키마 단위 테스트 — DB / 컨테이너 의존 없음."""

from __future__ import annotations

from uuid import uuid4

import pytest
from dev_team_shared.doc_store.schemas import (
    A2AContextCreate,
    A2AMessageCreate,
    A2ATaskCreate,
    AssignmentCreate,
    ChatCreate,
    IssueCreate,
    SessionCreate,
    WikiPageCreate,
)
from pydantic import ValidationError


# ──────────────────────────────────────────────────────────────────────────
# Chat tier
# ──────────────────────────────────────────────────────────────────────────


class TestSessionCreate:
    def test_minimal(self) -> None:
        doc = SessionCreate(agent_endpoint="primary", counterpart="primary")
        assert doc.initiator == "user"
        assert doc.metadata == {}

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            SessionCreate(  # type: ignore[call-arg]
                agent_endpoint="primary", counterpart="primary", unknown=1,
            )


class TestChatCreate:
    def test_role_validation(self) -> None:
        for r in ("user", "agent", "system"):
            ChatCreate(
                id=uuid4(),
                session_id=uuid4(),
                role=r,  # type: ignore[arg-type]
                sender="primary",
                content=[{"text": "hi"}],
            )

    def test_invalid_role(self) -> None:
        with pytest.raises(ValidationError):
            ChatCreate(
                id=uuid4(),
                session_id=uuid4(),
                role="bot",  # type: ignore[arg-type]
                sender="x",
                content={},
            )


class TestAssignmentCreate:
    def test_minimal(self) -> None:
        doc = AssignmentCreate(title="hello")
        assert doc.status == "open"
        assert doc.metadata == {}
        assert doc.issue_refs == []

    def test_invalid_status(self) -> None:
        with pytest.raises(ValidationError):
            AssignmentCreate(title="x", status="bogus")  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────
# A2A tier
# ──────────────────────────────────────────────────────────────────────────


class TestA2AContextCreate:
    def test_minimal(self) -> None:
        doc = A2AContextCreate(
            id=uuid4(),
            initiator_agent="primary",
            counterpart_agent="engineer",
        )
        assert doc.trace_id is None
        assert doc.parent_session_id is None
        assert doc.parent_assignment_id is None


class TestA2AMessageCreate:
    def test_role_validation(self) -> None:
        for r in ("user", "agent", "system"):
            A2AMessageCreate(
                id=uuid4(),
                a2a_context_id=uuid4(),
                role=r,  # type: ignore[arg-type]
                sender="primary",
                parts=[{"kind": "text", "text": "hi"}],
            )

    def test_optional_task_id(self) -> None:
        # standalone Message — a2a_task_id 없음
        doc = A2AMessageCreate(
            id=uuid4(),
            a2a_context_id=uuid4(),
            role="agent",
            sender="primary",
            parts=[],
        )
        assert doc.a2a_task_id is None


class TestA2ATaskCreate:
    def test_default_state(self) -> None:
        doc = A2ATaskCreate(id=uuid4(), a2a_context_id=uuid4())
        assert doc.state == "SUBMITTED"

    def test_invalid_state(self) -> None:
        with pytest.raises(ValidationError):
            A2ATaskCreate(
                id=uuid4(),
                a2a_context_id=uuid4(),
                state="DRAFT",  # type: ignore[arg-type]
            )


# ──────────────────────────────────────────────────────────────────────────
# 도메인 산출물
# ──────────────────────────────────────────────────────────────────────────


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
