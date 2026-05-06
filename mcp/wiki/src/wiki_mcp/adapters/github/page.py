"""GitHubPageOps — wiki repo 의 페이지 CRUD.

매 호출마다 임시 디렉터리에 wiki repo clone → 작업 → push → cleanup.
token leak 방지 위해 워크디렉터리는 매번 새로 만들고 작업 후 rmtree.

list / get / count 는 push 안 함 — clone + read 후 cleanup.
create / update / delete 는 commit + push.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dev_team_shared.wiki.schemas import (
    PageCreate,
    PageRead,
    PageRef,
    PageUpdate,
)

from wiki_mcp.adapters.base import PageOps
from wiki_mcp.adapters.github._ctx import _Ctx
from wiki_mcp.adapters.github._front_matter import decode as fm_decode
from wiki_mcp.adapters.github._front_matter import encode as fm_encode
from wiki_mcp.adapters.github._git import GitError, run_git

logger = logging.getLogger(__name__)


class GitHubPageOps(PageOps):
    def __init__(self, ctx: _Ctx) -> None:
        self._ctx = ctx

    # ---- public ----

    async def create(self, doc: PageCreate) -> PageRead:
        async with self._workdir() as workdir:
            path = self._slug_path(workdir, doc.slug)
            if path.exists():
                raise RuntimeError(
                    f"page {doc.slug!r} already exists — use update instead",
                )
            now = datetime.now(UTC)
            metadata = {
                "title": doc.title,
                "created_at": now,
                "updated_at": now,
                "page_type": doc.page_type,
                "structured": doc.structured,
            }
            path.write_text(fm_encode(metadata, doc.content_md), encoding="utf-8")
            await self._commit_and_push(workdir, f"create {doc.slug}")
            return PageRead(
                slug=doc.slug,
                title=doc.title,
                content_md=doc.content_md,
                page_type=doc.page_type,
                structured=doc.structured,
                created_at=now,
                updated_at=now,
            )

    async def update(self, slug: str, patch: PageUpdate) -> PageRead | None:
        async with self._workdir() as workdir:
            path = self._slug_path(workdir, slug)
            if not path.exists():
                return None
            existing_meta, existing_content = fm_decode(path.read_text(encoding="utf-8"))

            patch_dump = patch.model_dump(exclude_unset=True)
            new_title = patch_dump.get("title", existing_meta.get("title", ""))
            new_content = patch_dump.get("content_md", existing_content)
            new_page_type = patch_dump.get("page_type", existing_meta.get("page_type"))
            new_structured = patch_dump.get("structured", existing_meta.get("structured"))
            now = datetime.now(UTC)
            created_at = _parse_dt(existing_meta.get("created_at")) or now

            metadata = {
                "title": new_title,
                "created_at": created_at,
                "updated_at": now,
                "page_type": new_page_type,
                "structured": new_structured,
            }
            path.write_text(fm_encode(metadata, new_content), encoding="utf-8")
            await self._commit_and_push(workdir, f"update {slug}")
            return PageRead(
                slug=slug,
                title=new_title,
                content_md=new_content,
                page_type=new_page_type,
                structured=new_structured,
                created_at=created_at,
                updated_at=now,
            )

    async def get(self, slug: str) -> PageRead | None:
        async with self._workdir() as workdir:
            path = self._slug_path(workdir, slug)
            if not path.exists():
                return None
            return _parse_page(slug, path.read_text(encoding="utf-8"))

    async def list(self) -> list[PageRef]:
        async with self._workdir() as workdir:
            refs: list[PageRef] = []
            for path in sorted(Path(workdir).glob("*.md")):
                slug = path.stem
                meta, _ = fm_decode(path.read_text(encoding="utf-8"))
                title = str(meta.get("title") or slug)
                refs.append(PageRef(slug=slug, title=title))
            return refs

    async def delete(self, slug: str) -> bool:
        async with self._workdir() as workdir:
            path = self._slug_path(workdir, slug)
            if not path.exists():
                return False
            path.unlink()
            await self._commit_and_push(workdir, f"delete {slug}")
            return True

    async def count(self) -> int:
        async with self._workdir() as workdir:
            return sum(1 for _ in Path(workdir).glob("*.md"))

    # ---- internal ----

    @asynccontextmanager
    async def _workdir(self):
        """임시 디렉터리에 wiki repo shallow clone — 매 호출마다 new + cleanup."""
        workdir = tempfile.mkdtemp(prefix="wiki-mcp-")
        try:
            try:
                await run_git("clone", "--depth=1", self._ctx.wiki_url, workdir)
            except GitError as e:
                # wiki repo 가 비어있으면 GitHub 이 "remote: Repository is empty"
                # → init + remote add 로 fallback (첫 페이지 작성 케이스)
                if "empty" in e.stderr.lower() or "not found" in e.stderr.lower():
                    await self._init_empty(workdir)
                else:
                    raise
            await run_git("config", "user.email", self._ctx.author_email, cwd=workdir)
            await run_git("config", "user.name", self._ctx.author_name, cwd=workdir)
            yield workdir
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    async def _init_empty(self, workdir: str) -> None:
        """wiki repo 가 비어있을 때 init + remote add."""
        await run_git("init", "-b", "master", workdir)
        await run_git(
            "remote", "add", "origin", self._ctx.wiki_url, cwd=workdir,
        )

    async def _commit_and_push(self, workdir: str, message: str) -> None:
        await run_git("add", "-A", cwd=workdir)
        # 빈 commit 회피 — staged 변경 있는지 확인
        try:
            await run_git("diff", "--cached", "--quiet", cwd=workdir)
        except GitError:
            # diff --quiet 가 변경 있으면 exit 1 → GitError. 정상 흐름.
            await run_git("commit", "-m", message, cwd=workdir)
            try:
                await run_git("push", "origin", "HEAD:master", cwd=workdir)
            except GitError as e:
                msg = e.stderr.lower()
                if "repository not found" in msg or "wiki" in msg:
                    raise RuntimeError(
                        "GitHub Wiki repo not initialized. Create the first page "
                        "manually in GitHub UI (Wiki tab → 'Create the first page') "
                        "to bootstrap the wiki repo, then retry.",
                    ) from e
                raise

    def _slug_path(self, workdir: str, slug: str) -> Path:
        # GitHub Wiki 의 페이지 파일명 = `<slug>.md`. slash / .. 차단.
        if "/" in slug or ".." in slug or slug.startswith("."):
            raise ValueError(f"invalid slug: {slug!r}")
        return Path(workdir) / f"{slug}.md"


def _parse_page(slug: str, text: str) -> PageRead:
    metadata, content = fm_decode(text)
    return PageRead(
        slug=slug,
        title=str(metadata.get("title") or slug),
        content_md=content,
        page_type=_str_or_none(metadata.get("page_type")),
        structured=_dict_or_none(metadata.get("structured")),
        created_at=_parse_dt(metadata.get("created_at")),
        updated_at=_parse_dt(metadata.get("updated_at")),
    )


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _str_or_none(value: Any) -> str | None:
    return str(value) if value is not None else None


def _dict_or_none(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


__all__ = ["GitHubPageOps"]
