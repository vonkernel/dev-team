"""IssueTracker — 외부 이슈 트래커 추상.

mcp/CLAUDE.md §0 (thin bridge) + §2.2 (API-client 패턴) 준수.

본 ABC 는 의미적 매핑 / 결정 로직을 가지지 않는다 — 호출자(LLM 에이전트)가
보낸 raw id 를 받아 도구에 그대로 전달하거나, 도구의 사실을 그대로 반환할 뿐.
새 backend (Jira / Linear 등) 추가는 본 ABC 를 상속한 새 어댑터 + factory.py
에 1줄 등록 (OCP).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from dev_team_shared.issue_tracker.schemas.issue import IssueCreate, IssueRead, IssueUpdate
from dev_team_shared.issue_tracker.schemas.refs import FieldRef, StatusRef, TypeRef


class IssueTracker(ABC):
    """외부 이슈 트래커 어댑터 추상 (13 op)."""

    # ---- issue CRUD (6 op, mcp/CLAUDE.md §1.5) ----

    @abstractmethod
    async def create(self, doc: IssueCreate) -> IssueRead:
        """이슈 생성. type_id / status_id 는 호출자가 list_* 결과로 결정."""

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
        """이슈 close (lifecycle 종료). ref 미존재 시 False."""

    @abstractmethod
    async def count(self, where: dict[str, Any] | None) -> int:
        """개수 조회 (페이지네이션 / 통계)."""

    # ---- status — discover + manage + transition ----

    @abstractmethod
    async def list_statuses(self) -> list[StatusRef]:
        """도구의 현재 status 목록 그대로 반환 (정규화 X)."""

    @abstractmethod
    async def create_status(self, name: str) -> StatusRef:
        """도구 안에 새 status 추가. 이름 중복 시 기존 항목 반환 (idempotent)."""

    @abstractmethod
    async def transition(self, ref: str, status_id: str) -> None:
        """status 전이. status_id 는 list_statuses() 결과의 id."""

    # ---- type — discover + manage ----

    @abstractmethod
    async def list_types(self) -> list[TypeRef]:
        """도구의 현재 type 목록 그대로 반환."""

    @abstractmethod
    async def create_type(self, name: str) -> TypeRef:
        """도구 안에 새 type 추가. 이름 중복 시 기존 항목 반환 (idempotent)."""

    # ---- field — board setup 도구 (PM 워크플로우 자율화) ----

    @abstractmethod
    async def list_fields(self) -> list[FieldRef]:
        """board 의 모든 field 목록. P 가 board 에 어떤 구조가 있는지 점검."""

    @abstractmethod
    async def create_field(self, name: str, kind: str = "single_select") -> FieldRef:
        """board 에 field 추가. 이름 중복 시 기존 항목 반환 (idempotent).

        지원 kind: `single_select` (기본). 우리 시스템의 status / type 도구는
        single_select 만 의미 있음. 다른 dataType (text / number / date / iteration)
        도 어댑터별로 지원 가능.
        """


__all__ = ["IssueTracker"]
