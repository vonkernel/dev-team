"""subprocess git wrapper.

표준 git binary (Dockerfile 에 apt install git). 외부 라이브러리 (dulwich 등)
미사용 — 일관성 / 디버깅 용이.

shell=True 사용 X — args 는 list 로 전달 (injection 회피).
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class GitError(RuntimeError):
    """git 명령이 비-0 종료. stderr / returncode 첨부.

    `git_args` 로 명명 — `BaseException.args` (message tuple) 와 분리.
    `self.args = ...` 로 덮으면 RuntimeError str() 이 깨져 stderr 디테일 유실.
    """

    def __init__(self, args: tuple[str, ...], returncode: int, stderr: str) -> None:
        super().__init__(
            f"git {' '.join(args[:3])}... failed (code={returncode}): {stderr[:500]}",
        )
        self.git_args = args
        self.returncode = returncode
        self.stderr = stderr


async def run_git(*args: str, cwd: str | None = None) -> str:
    """git 명령 실행. stdout 반환. 비-0 면 GitError."""
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise GitError(args, proc.returncode or -1, err.decode(errors="replace"))
    return out.decode(errors="replace")


__all__ = ["GitError", "run_git"]
