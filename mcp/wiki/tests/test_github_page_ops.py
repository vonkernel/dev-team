"""GitHubPageOps 단위 테스트.

`_workdir` (clone + cleanup) 와 `_commit_and_push` (commit + push) 를 monkeypatch
로 무력화 — file 시스템 단위 동작만 검증. 실 git 호출 / 외부 GitHub API 의존
없음.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from dev_team_shared.wiki.schemas import PageCreate, PageUpdate

from wiki_mcp.adapters.github._ctx import _Ctx
from wiki_mcp.adapters.github._front_matter import decode, encode
from wiki_mcp.adapters.github.page import GitHubPageOps


@pytest.fixture
def patched_ops(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[GitHubPageOps, Path]:
    """clone / push 가 무력화된 GitHubPageOps + 공유 workdir."""
    ctx = _Ctx(owner="acme", repo="repo", token="t")
    ops = GitHubPageOps(ctx)

    @asynccontextmanager
    async def fake_workdir():
        yield str(tmp_path)

    async def fake_commit_and_push(workdir: str, message: str) -> None:
        pass

    monkeypatch.setattr(ops, "_workdir", fake_workdir)
    monkeypatch.setattr(ops, "_commit_and_push", fake_commit_and_push)
    return ops, tmp_path


# ----------------------------------------------------------------------
# create
# ----------------------------------------------------------------------


async def test_create_writes_file_with_front_matter(
    patched_ops: tuple[GitHubPageOps, Path],
) -> None:
    ops, workdir = patched_ops
    doc = PageCreate(
        slug="prd-guestbook",
        title="GuestBook PRD",
        content_md="# Body\n\nContent.",
        page_type="prd",
        structured={"milestones": [{"name": "M1"}]},
    )
    result = await ops.create(doc)

    path = workdir / "prd-guestbook.md"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    meta, content = decode(text)
    assert meta["title"] == "GuestBook PRD"
    assert meta["page_type"] == "prd"
    assert meta["structured"] == {"milestones": [{"name": "M1"}]}
    assert content.startswith("# Body")
    # 반환값 일치
    assert result.slug == "prd-guestbook"
    assert result.title == "GuestBook PRD"


async def test_create_rejects_existing_slug(
    patched_ops: tuple[GitHubPageOps, Path],
) -> None:
    ops, workdir = patched_ops
    (workdir / "x.md").write_text(encode({"title": "X"}, ""), encoding="utf-8")
    with pytest.raises(RuntimeError, match="already exists"):
        await ops.create(PageCreate(slug="x", title="X"))


def test_create_rejects_invalid_slug(
    patched_ops: tuple[GitHubPageOps, Path],
) -> None:
    """slug 에 path traversal 차단 — 동기 검증, op 호출 전."""
    ops, _ = patched_ops
    with pytest.raises(ValueError, match="invalid slug"):
        ops._slug_path("/tmp", "../etc/passwd")


# ----------------------------------------------------------------------
# get / list / count
# ----------------------------------------------------------------------


async def test_get_returns_none_when_missing(
    patched_ops: tuple[GitHubPageOps, Path],
) -> None:
    ops, _ = patched_ops
    assert await ops.get("nope") is None


async def test_get_parses_front_matter(
    patched_ops: tuple[GitHubPageOps, Path],
) -> None:
    ops, workdir = patched_ops
    text = encode(
        {"title": "T", "page_type": "adr", "structured": {"k": "v"}},
        "# Body",
    )
    (workdir / "x.md").write_text(text, encoding="utf-8")

    page = await ops.get("x")
    assert page is not None
    assert page.title == "T"
    assert page.page_type == "adr"
    assert page.structured == {"k": "v"}
    assert page.content_md.startswith("# Body")


async def test_list_returns_refs(
    patched_ops: tuple[GitHubPageOps, Path],
) -> None:
    ops, workdir = patched_ops
    (workdir / "a.md").write_text(encode({"title": "A"}, ""), encoding="utf-8")
    (workdir / "b.md").write_text(encode({"title": "B"}, ""), encoding="utf-8")

    refs = await ops.list()
    names = sorted((r.slug, r.title) for r in refs)
    assert names == [("a", "A"), ("b", "B")]


async def test_list_falls_back_to_slug_when_title_missing(
    patched_ops: tuple[GitHubPageOps, Path],
) -> None:
    ops, workdir = patched_ops
    (workdir / "no-fm.md").write_text("just markdown", encoding="utf-8")
    refs = await ops.list()
    assert refs == [type(refs[0])(slug="no-fm", title="no-fm")]


async def test_count(patched_ops: tuple[GitHubPageOps, Path]) -> None:
    ops, workdir = patched_ops
    (workdir / "a.md").write_text("x", encoding="utf-8")
    (workdir / "b.md").write_text("y", encoding="utf-8")
    assert await ops.count() == 2


# ----------------------------------------------------------------------
# update
# ----------------------------------------------------------------------


async def test_update_partial_preserves_unchanged_fields(
    patched_ops: tuple[GitHubPageOps, Path],
) -> None:
    ops, workdir = patched_ops
    text = encode(
        {"title": "Original", "page_type": "prd", "structured": {"k": "v"}},
        "# Original Body",
    )
    (workdir / "x.md").write_text(text, encoding="utf-8")

    result = await ops.update("x", PageUpdate(content_md="# New Body"))
    assert result is not None
    assert result.title == "Original"          # 변경 없음 — 보존
    assert result.page_type == "prd"           # 변경 없음 — 보존
    assert result.structured == {"k": "v"}     # 변경 없음 — 보존
    assert result.content_md.startswith("# New Body")


async def test_update_returns_none_when_missing(
    patched_ops: tuple[GitHubPageOps, Path],
) -> None:
    ops, _ = patched_ops
    assert await ops.update("nope", PageUpdate(title="x")) is None


# ----------------------------------------------------------------------
# delete
# ----------------------------------------------------------------------


async def test_delete_removes_file(
    patched_ops: tuple[GitHubPageOps, Path],
) -> None:
    ops, workdir = patched_ops
    (workdir / "x.md").write_text("x", encoding="utf-8")
    assert await ops.delete("x") is True
    assert not (workdir / "x.md").exists()


async def test_delete_returns_false_when_missing(
    patched_ops: tuple[GitHubPageOps, Path],
) -> None:
    ops, _ = patched_ops
    assert await ops.delete("nope") is False
