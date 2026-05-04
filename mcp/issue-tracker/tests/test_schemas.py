"""IssueTracker MCP — schemas 단위 테스트 (외부 의존 없음)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from dev_team_shared.issue_tracker.schemas import (
    IssueCreate,
    IssueRead,
    IssueUpdate,
    StatusRef,
    TypeRef,
)


class TestIssueCreate:
    def test_minimal(self) -> None:
        doc = IssueCreate(title="hello")
        assert doc.body is None
        assert doc.type_id is None
        assert doc.status_id is None

    def test_with_type_and_status(self) -> None:
        doc = IssueCreate(
            title="t", body="b", type_id="type-id", status_id="status-id",
        )
        assert doc.type_id == "type-id"
        assert doc.status_id == "status-id"

    def test_title_required(self) -> None:
        with pytest.raises(ValidationError):
            IssueCreate(body="x")  # type: ignore[call-arg]

    def test_title_empty_rejected(self) -> None:
        with pytest.raises(ValidationError):
            IssueCreate(title="")

    def test_extra_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            IssueCreate(title="t", unknown=1)  # type: ignore[call-arg]


class TestIssueUpdate:
    def test_all_optional(self) -> None:
        patch = IssueUpdate()
        assert patch.model_dump(exclude_unset=True) == {}

    def test_partial_update_excludes_unset(self) -> None:
        patch = IssueUpdate(title="new")
        assert patch.model_dump(exclude_unset=True) == {"title": "new"}


class TestIssueRead:
    def test_round_trip(self) -> None:
        now = datetime.now(UTC)
        read = IssueRead(
            ref="42",
            title="t",
            body="b",
            type=TypeRef(id="ti", name="epic"),
            status=StatusRef(id="si", name="Ready"),
            closed=False,
            created_at=now,
            updated_at=now,
        )
        dumped = read.model_dump(mode="json")
        rehydrated = IssueRead.model_validate(dumped)
        assert rehydrated == read

    def test_status_and_type_optional(self) -> None:
        now = datetime.now(UTC)
        read = IssueRead(
            ref="1",
            title="t",
            created_at=now,
            updated_at=now,
        )
        assert read.status is None
        assert read.type is None


class TestRefs:
    def test_status_ref_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            StatusRef(id="x")  # type: ignore[call-arg]

    def test_type_ref_round_trip(self) -> None:
        ref = TypeRef(id="t1", name="Epic")
        assert TypeRef.model_validate(ref.model_dump()) == ref
