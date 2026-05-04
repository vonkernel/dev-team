"""IssueTracker — 외부 이슈 트래커 추상.

mcp/CLAUDE.md §0 (thin bridge) + §2.2 (API-client 패턴) 준수.

본 모듈은 ISP (Interface Segregation Principle) 적용 — 한 인터페이스에 17 op
몰아넣지 않고 책임별 좁은 ABC 4개 + 컴포지트 1개:

- `IssueOps`  — 이슈 lifecycle (8 op)
- `StatusOps` — board 의 Status field option 메타데이터 (3 op)
- `TypeOps`   — board 의 Issue Type field option 메타데이터 (3 op)
- `FieldOps`  — board 의 field 자체 (3 op, board setup 자율화용)
- `IssueTracker` — 위 4 ops 의 컴포지트 (어댑터 진입점)

호출자는 좁은 ops 에만 의존 가능 (예: P 가 issue 작업만 할 때 `IssueOps` 만
type-annotate). 새 backend (Jira / Linear) 추가는 4 ops 각각 구현 + 컴포지트
1개 작성 + factory.py 1줄 등록 (OCP).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from dev_team_shared.issue_tracker.schemas.issue import (
    IssueCreate,
    IssueRead,
    IssueUpdate,
)
from dev_team_shared.issue_tracker.schemas.refs import (
    FieldRef,
    StatusRef,
    TypeRef,
)


class IssueOps(ABC):
    """이슈 lifecycle (8 op).

    `close` 와 `delete` 의미 차이:
    - `close(ref)` — 가벼운 lifecycle 종료 (보존)
    - `delete(ref)` — 영구 삭제 (admin 권한 필요할 수 있음)
    """

    @abstractmethod
    async def create(self, doc: IssueCreate) -> IssueRead:
        """이슈 생성. type_id / status_id 는 호출자가 list 결과로 결정."""

    @abstractmethod
    async def update(self, ref: str, patch: IssueUpdate) -> IssueRead | None:
        """제목 / body / type 갱신. ref 미존재 시 None."""

    @abstractmethod
    async def get(self, ref: str) -> IssueRead | None:
        """단건 조회. ref 미존재 시 None."""

    @abstractmethod
    async def list(
        self,
        where: dict[str, Any] | None,
        limit: int,
        offset: int,
        order_by: str,
    ) -> list[IssueRead]:
        """목록 조회. where 는 어댑터별 단순 equality 필터."""

    @abstractmethod
    async def close(self, ref: str) -> bool:
        """이슈 close (lifecycle 종료, 보존). ref 미존재 시 False."""

    @abstractmethod
    async def delete(self, ref: str) -> bool:
        """이슈 영구 삭제. admin 권한 필요할 수 있음 (없으면 RuntimeError).
        ref 미존재 시 False."""

    @abstractmethod
    async def count(self, where: dict[str, Any] | None) -> int:
        """개수 조회 (페이지네이션 / 통계)."""

    @abstractmethod
    async def transition(self, ref: str, status_id: str) -> None:
        """status 전이. status_id 는 `StatusOps.list()` 결과의 id."""


class StatusOps(ABC):
    """status field 메타데이터 (3 op).

    GitHub 어댑터 기준: Project board 의 `Status` single-select field 의 options.
    """

    @abstractmethod
    async def list(self) -> list[StatusRef]:
        """도구의 현재 status 목록 그대로 반환 (정규화 X)."""

    @abstractmethod
    async def create(self, name: str) -> StatusRef:
        """새 status 추가. 이름 중복 시 기존 항목 반환 (idempotent)."""

    @abstractmethod
    async def delete(self, status_id: str) -> bool:
        """status option 삭제. 미존재 시 False.
        사용 중인 option 삭제 시 도구 동작 (issue 의 status 가 unset 등)."""


class TypeOps(ABC):
    """type field 메타데이터 (3 op).

    GitHub 어댑터 기준: Project board 의 `Issue Type` single-select field options.
    (`Type` 은 GitHub native issue types reserved word 라 회피.)
    """

    @abstractmethod
    async def list(self) -> list[TypeRef]: ...

    @abstractmethod
    async def create(self, name: str) -> TypeRef: ...

    @abstractmethod
    async def delete(self, type_id: str) -> bool: ...


class FieldOps(ABC):
    """board field 자체 (3 op) — PM 워크플로우 자율 setup 용.

    P 가 board 에 어떤 field 가 있는지 조회 + 부족하면 직접 추가 / 정리.
    사람이 board UI 에서 사전 셋업 안 해도 됨.
    """

    @abstractmethod
    async def list(self) -> list[FieldRef]:
        """board 의 모든 field. P 가 board 에 어떤 구조가 있는지 점검."""

    @abstractmethod
    async def create(self, name: str, kind: str = "single_select") -> FieldRef:
        """board 에 field 추가. 이름 중복 시 기존 항목 반환 (idempotent).

        지원 kind: `single_select` (기본). 우리 시스템의 status / type 도구는
        single_select 만 의미 있음. 다른 dataType (text / number / date / iteration)
        도 어댑터별로 지원 가능.
        """

    @abstractmethod
    async def delete(self, field_id: str) -> bool:
        """board field 영구 삭제. board default field (Title 등) 는 도구가
        거부할 수 있음. 미존재 시 False."""


class IssueTracker(ABC):
    """4 ops 의 컴포지트 — 어댑터 진입점.

    호출자가 좁은 인터페이스에 의존 가능 (ISP):

        adapter: IssueTracker = factory(...)
        # P 가 issue 작업만 할 때
        issues: IssueOps = adapter.issues
    """

    @property
    @abstractmethod
    def issues(self) -> IssueOps: ...

    @property
    @abstractmethod
    def statuses(self) -> StatusOps: ...

    @property
    @abstractmethod
    def types(self) -> TypeOps: ...

    @property
    @abstractmethod
    def fields(self) -> FieldOps: ...


__all__ = [
    "FieldOps",
    "IssueOps",
    "IssueTracker",
    "StatusOps",
    "TypeOps",
]
