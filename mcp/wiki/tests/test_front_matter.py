"""YAML front matter encode / decode 라운드트립 검증."""

from __future__ import annotations

from datetime import UTC, datetime

from wiki_mcp.adapters.github._front_matter import decode, encode


def test_round_trip_simple() -> None:
    metadata = {"title": "GuestBook PRD", "page_type": "prd"}
    text = encode(metadata, "# Body\n\nContent.")
    assert text.startswith("---\n")
    parsed_meta, parsed_content = decode(text)
    assert parsed_meta["title"] == "GuestBook PRD"
    assert parsed_meta["page_type"] == "prd"
    assert parsed_content.startswith("# Body")


def test_round_trip_datetime_serialized_as_iso() -> None:
    now = datetime(2026, 5, 4, 17, 39, 0, tzinfo=UTC)
    text = encode({"updated_at": now}, "body")
    meta, _ = decode(text)
    # ISO Z 포맷으로 직렬화됨 → string 으로 round-trip
    assert meta["updated_at"] == "2026-05-04T17:39:00Z"


def test_round_trip_structured_dict() -> None:
    structured = {"milestones": [{"name": "M1"}], "in_scope": ["x", "y"]}
    text = encode({"title": "T", "structured": structured}, "")
    meta, _ = decode(text)
    assert meta["structured"] == structured


def test_no_front_matter_returns_text_as_is() -> None:
    text = "# Just markdown\n\nNo front matter here."
    meta, content = decode(text)
    assert meta == {}
    assert content == text


def test_unclosed_front_matter_returns_text_as_is() -> None:
    text = "---\ntitle: oops\nno closing delim"
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
