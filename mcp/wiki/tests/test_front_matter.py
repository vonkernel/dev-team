"""Page metadata block (### 헤더 + yaml fence + *** 구분자) 라운드트립 검증."""

from __future__ import annotations

from datetime import UTC, datetime

from wiki_mcp.adapters.github._front_matter import decode, encode


def test_round_trip_simple() -> None:
    metadata = {"title": "GuestBook PRD", "page_type": "prd"}
    text = encode(metadata, "# Body\n\nContent.")
    # GitHub Wiki UI 친화적 양식: H3 헤더 시작
    assert text.startswith("### 📋 Page metadata\n")
    # yaml fence
    assert "```yaml\n" in text
    assert "\n```\n" in text
    # *** 구분자
    assert "\n***\n" in text

    parsed_meta, parsed_content = decode(text)
    assert parsed_meta["title"] == "GuestBook PRD"
    assert parsed_meta["page_type"] == "prd"
    assert parsed_content.startswith("# Body")


def test_round_trip_datetime_serialized_as_iso() -> None:
    now = datetime(2026, 5, 4, 17, 39, 0, tzinfo=UTC)
    text = encode({"updated_at": now}, "body")
    meta, _ = decode(text)
    assert meta["updated_at"] == "2026-05-04T17:39:00Z"


def test_round_trip_structured_dict() -> None:
    structured = {"milestones": [{"name": "M1"}], "in_scope": ["x", "y"]}
    text = encode({"title": "T", "structured": structured}, "")
    meta, _ = decode(text)
    assert meta["structured"] == structured


def test_no_metadata_block_returns_text_as_is() -> None:
    text = "# Just markdown\n\nNo metadata block here."
    meta, content = decode(text)
    assert meta == {}
    assert content == text


def test_partial_block_returns_text_as_is() -> None:
    """헤더만 있고 yaml fence 없으면 매칭 실패 → metadata 무시."""
    text = "### 📋 Page metadata\n\nbut no fence below"
    meta, content = decode(text)
    assert meta == {}
    assert content == text


def test_unclosed_fence_returns_text_as_is() -> None:
    text = "### 📋 Page metadata\n\n```yaml\ntitle: X\n# body without closing fence"
    meta, content = decode(text)
    assert meta == {}
    assert content == text


def test_missing_divider_returns_text_as_is() -> None:
    """`***` 구분자 없으면 매칭 실패."""
    text = "### 📋 Page metadata\n\n```yaml\ntitle: X\n```\n\n# body without divider"
    meta, content = decode(text)
    assert meta == {}
    assert content == text


def test_none_values_dropped_from_encoding() -> None:
    text = encode({"title": "T", "page_type": None, "structured": None}, "x")
    meta, _ = decode(text)
    assert meta == {"title": "T"}


def test_empty_content_ok() -> None:
    text = encode({"title": "T"}, "")
    meta, content = decode(text)
    assert meta == {"title": "T"}
    assert content == ""


def test_full_round_trip_preserves_all_domain_fields() -> None:
    """PRD / ADR 같은 실 케이스 — 모든 도메인 필드 라운드트립."""
    now = datetime(2026, 5, 6, 8, 54, 3, tzinfo=UTC)
    metadata = {
        "title": "GuestBook PRD",
        "created_at": now,
        "updated_at": now,
        "page_type": "prd",
        "structured": {
            "milestones": [{"name": "M1", "description": "..."}],
            "in_scope": ["A", "B"],
            "out_of_scope": ["C"],
        },
    }
    body = "# 배경\n\n사용자가 ...\n\n## 목표\n\n- ...\n"
    text = encode(metadata, body)
    parsed_meta, parsed_content = decode(text)
    assert parsed_meta["title"] == "GuestBook PRD"
    assert parsed_meta["page_type"] == "prd"
    assert parsed_meta["structured"]["milestones"] == [{"name": "M1", "description": "..."}]
    assert parsed_content == body
