"""Wiki MCP — schemas 단위 테스트."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from dev_team_shared.wiki.schemas import (
    PageCreate,
    PageRead,
    PageRef,
    PageUpdate,
)


class TestPageCreate:
    def test_minimal(self) -> None:
        doc = PageCreate(slug="prd-x", title="PRD X")
        assert doc.content_md == ""
        assert doc.page_type is None
        assert doc.structured is None

    def test_full(self) -> None:
        doc = PageCreate(
            slug="prd-x",
            title="PRD X",
            content_md="# Body",
            page_type="prd",
            structured={"milestones": [{"name": "M1"}]},
        )
        assert doc.page_type == "prd"
        assert doc.structured == {"milestones": [{"name": "M1"}]}

    def test_slug_required(self) -> None:
        with pytest.raises(ValidationError):
            PageCreate(title="X")  # type: ignore[call-arg]

    def test_title_required(self) -> None:
        with pytest.raises(ValidationError):
            PageCreate(slug="x")  # type: ignore[call-arg]

    def test_extra_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            PageCreate(slug="x", title="t", junk=1)  # type: ignore[call-arg]


class TestPageUpdate:
    def test_all_optional(self) -> None:
        assert PageUpdate().model_dump(exclude_unset=True) == {}

    def test_partial(self) -> None:
        patch = PageUpdate(title="new")
        assert patch.model_dump(exclude_unset=True) == {"title": "new"}


class TestPageRead:
    def test_round_trip(self) -> None:
        now = datetime.now(UTC)
        read = PageRead(
            slug="prd-x",
            title="PRD X",
            content_md="# Body",
            page_type="prd",
            structured={"k": "v"},
            created_at=now,
            updated_at=now,
        )
        rehydrated = PageRead.model_validate(read.model_dump(mode="json"))
        assert rehydrated == read

    def test_minimal(self) -> None:
        read = PageRead(slug="x", title="X")
        assert read.content_md == ""
        assert read.page_type is None
        assert read.created_at is None


class TestPageRef:
    def test_ref(self) -> None:
        ref = PageRef(slug="x", title="X")
        assert PageRef.model_validate(ref.model_dump()) == ref
