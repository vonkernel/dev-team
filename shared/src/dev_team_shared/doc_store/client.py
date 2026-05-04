"""DocStoreClient — Document DB MCP 의 typed 클라이언트.

호출자는 Pydantic 모델 입출력만 다룸. wire-level 디테일 (도구명 / dict 래핑 /
JSON parse) 모두 본 클래스 안에 격리.

사용:

    async with StreamableMCPClient.connect(url) as mcp:
        db = DocStoreClient(mcp)
        item = await db.agent_item_create(AgentItemCreate(...))   # → AgentItemRead
"""

from __future__ import annotations

from typing import Any, TypeVar
from uuid import UUID

from pydantic import BaseModel

from dev_team_shared.doc_store.schemas import (
    AgentItemCreate,
    AgentItemRead,
    AgentSessionCreate,
    AgentSessionRead,
    AgentSessionUpdate,
    AgentTaskCreate,
    AgentTaskRead,
    AgentTaskUpdate,
    IssueCreate,
    IssueRead,
    IssueUpdate,
    WikiPageCreate,
    WikiPageRead,
    WikiPageUpdate,
)
from dev_team_shared.doc_store.tool_names import (
    AgentItemTools,
    AgentSessionTools,
    AgentTaskTools,
    IssueTools,
    WikiPageTools,
)
from dev_team_shared.mcp_client import StreamableMCPClient

T = TypeVar("T", bound=BaseModel)


class DocStoreClient:
    """Typed wrapper around `StreamableMCPClient` for Document DB MCP 도구.

    각 collection × op 마다 1 메서드. 모든 입력은 Pydantic 모델, 모든 반환은
    Pydantic 모델 / scalar 또는 None. dict / 문자열은 본 클래스 외부로 새지 않음.
    """

    def __init__(self, mcp: StreamableMCPClient) -> None:
        self._mcp = mcp

    # ──────────────────────────────────────────────────────────────────
    # agent_task
    # ──────────────────────────────────────────────────────────────────

    async def agent_task_create(self, doc: AgentTaskCreate) -> AgentTaskRead:
        return await self._call(
            AgentTaskTools.CREATE, _doc(doc), AgentTaskRead,
        )

    async def agent_task_update(
        self, id: UUID, patch: AgentTaskUpdate,
    ) -> AgentTaskRead | None:
        return await self._call_optional(
            AgentTaskTools.UPDATE, _id_patch(id, patch), AgentTaskRead,
        )

    async def agent_task_get(self, id: UUID) -> AgentTaskRead | None:
        return await self._call_optional(
            AgentTaskTools.GET, {"id": str(id)}, AgentTaskRead,
        )

    async def agent_task_list(
        self,
        *,
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> list[AgentTaskRead]:
        return await self._call_list(
            AgentTaskTools.LIST,
            _list_args(where, limit, offset, order_by),
            AgentTaskRead,
        )

    async def agent_task_delete(self, id: UUID) -> bool:
        return await self._call_scalar(AgentTaskTools.DELETE, {"id": str(id)})

    async def agent_task_count(self, *, where: dict[str, Any] | None = None) -> int:
        return await self._call_scalar(
            AgentTaskTools.COUNT, _where_args(where),
        )

    # ──────────────────────────────────────────────────────────────────
    # agent_session
    # ──────────────────────────────────────────────────────────────────

    async def agent_session_create(self, doc: AgentSessionCreate) -> AgentSessionRead:
        return await self._call(AgentSessionTools.CREATE, _doc(doc), AgentSessionRead)

    async def agent_session_update(
        self, id: UUID, patch: AgentSessionUpdate,
    ) -> AgentSessionRead | None:
        return await self._call_optional(
            AgentSessionTools.UPDATE, _id_patch(id, patch), AgentSessionRead,
        )

    async def agent_session_get(self, id: UUID) -> AgentSessionRead | None:
        return await self._call_optional(
            AgentSessionTools.GET, {"id": str(id)}, AgentSessionRead,
        )

    async def agent_session_list(
        self,
        *,
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "started_at DESC",
    ) -> list[AgentSessionRead]:
        return await self._call_list(
            AgentSessionTools.LIST,
            _list_args(where, limit, offset, order_by),
            AgentSessionRead,
        )

    async def agent_session_delete(self, id: UUID) -> bool:
        return await self._call_scalar(AgentSessionTools.DELETE, {"id": str(id)})

    async def agent_session_count(self, *, where: dict[str, Any] | None = None) -> int:
        return await self._call_scalar(AgentSessionTools.COUNT, _where_args(where))

    async def agent_session_list_by_task(
        self, agent_task_id: UUID,
    ) -> list[AgentSessionRead]:
        return await self._call_list(
            AgentSessionTools.LIST_BY_TASK,
            {"agent_task_id": str(agent_task_id)},
            AgentSessionRead,
        )

    async def agent_session_find_by_context(
        self, context_id: str,
    ) -> AgentSessionRead | None:
        return await self._call_optional(
            AgentSessionTools.FIND_BY_CONTEXT,
            {"context_id": context_id},
            AgentSessionRead,
        )

    # ──────────────────────────────────────────────────────────────────
    # agent_item (immutable — no update)
    # ──────────────────────────────────────────────────────────────────

    async def agent_item_create(self, doc: AgentItemCreate) -> AgentItemRead:
        return await self._call(AgentItemTools.CREATE, _doc(doc), AgentItemRead)

    async def agent_item_get(self, id: UUID) -> AgentItemRead | None:
        return await self._call_optional(
            AgentItemTools.GET, {"id": str(id)}, AgentItemRead,
        )

    async def agent_item_list(
        self,
        *,
        where: dict[str, Any] | None = None,
        limit: int = 200,
        offset: int = 0,
        order_by: str = "created_at",
    ) -> list[AgentItemRead]:
        return await self._call_list(
            AgentItemTools.LIST,
            _list_args(where, limit, offset, order_by),
            AgentItemRead,
        )

    async def agent_item_delete(self, id: UUID) -> bool:
        return await self._call_scalar(AgentItemTools.DELETE, {"id": str(id)})

    async def agent_item_count(self, *, where: dict[str, Any] | None = None) -> int:
        return await self._call_scalar(AgentItemTools.COUNT, _where_args(where))

    async def agent_item_list_by_session(
        self, agent_session_id: UUID,
    ) -> list[AgentItemRead]:
        return await self._call_list(
            AgentItemTools.LIST_BY_SESSION,
            {"agent_session_id": str(agent_session_id)},
            AgentItemRead,
        )

    # ──────────────────────────────────────────────────────────────────
    # issue
    # ──────────────────────────────────────────────────────────────────

    async def issue_create(self, doc: IssueCreate) -> IssueRead:
        return await self._call(IssueTools.CREATE, _doc(doc), IssueRead)

    async def issue_update(
        self,
        id: UUID,
        patch: IssueUpdate,
        *,
        expected_version: int | None = None,
    ) -> IssueRead | None:
        args = _id_patch(id, patch)
        if expected_version is not None:
            args["expected_version"] = expected_version
        return await self._call_optional(IssueTools.UPDATE, args, IssueRead)

    async def issue_get(self, id: UUID) -> IssueRead | None:
        return await self._call_optional(
            IssueTools.GET, {"id": str(id)}, IssueRead,
        )

    async def issue_list(
        self,
        *,
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> list[IssueRead]:
        return await self._call_list(
            IssueTools.LIST,
            _list_args(where, limit, offset, order_by),
            IssueRead,
        )

    async def issue_delete(self, id: UUID) -> bool:
        return await self._call_scalar(IssueTools.DELETE, {"id": str(id)})

    async def issue_count(self, *, where: dict[str, Any] | None = None) -> int:
        return await self._call_scalar(IssueTools.COUNT, _where_args(where))

    # ──────────────────────────────────────────────────────────────────
    # wiki_page
    # ──────────────────────────────────────────────────────────────────

    async def wiki_page_create(self, doc: WikiPageCreate) -> WikiPageRead:
        return await self._call(WikiPageTools.CREATE, _doc(doc), WikiPageRead)

    async def wiki_page_update(
        self,
        id: UUID,
        patch: WikiPageUpdate,
        *,
        expected_version: int | None = None,
    ) -> WikiPageRead | None:
        args = _id_patch(id, patch)
        if expected_version is not None:
            args["expected_version"] = expected_version
        return await self._call_optional(WikiPageTools.UPDATE, args, WikiPageRead)

    async def wiki_page_get(self, id: UUID) -> WikiPageRead | None:
        return await self._call_optional(
            WikiPageTools.GET, {"id": str(id)}, WikiPageRead,
        )

    async def wiki_page_list(
        self,
        *,
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> list[WikiPageRead]:
        return await self._call_list(
            WikiPageTools.LIST,
            _list_args(where, limit, offset, order_by),
            WikiPageRead,
        )

    async def wiki_page_delete(self, id: UUID) -> bool:
        return await self._call_scalar(WikiPageTools.DELETE, {"id": str(id)})

    async def wiki_page_count(self, *, where: dict[str, Any] | None = None) -> int:
        return await self._call_scalar(WikiPageTools.COUNT, _where_args(where))

    async def wiki_page_get_by_slug(self, slug: str) -> WikiPageRead | None:
        return await self._call_optional(
            WikiPageTools.GET_BY_SLUG, {"slug": slug}, WikiPageRead,
        )

    # ──────────────────────────────────────────────────────────────────
    # 내부 — wire 호출 + 직렬화/역직렬화
    # ──────────────────────────────────────────────────────────────────

    async def _call(
        self, name: str, args: dict[str, Any], return_type: type[T],
    ) -> T:
        """Pydantic 모델 반환. structuredContent 가 모델 dict 자체."""
        sc = await self._invoke(name, args)
        return return_type.model_validate(sc)

    async def _call_optional(
        self, name: str, args: dict[str, Any], return_type: type[T],
    ) -> T | None:
        """Optional[Model] — FastMCP 가 항상 `{"result": <model_dict_or_None>}` 로 wrap.

        (이유: FastMCP 의 structured content 규약 — return type 이 Pydantic 모델
        한 종(non-optional) 일 때만 unwrapped, 그 외 (Optional 포함) 는 result key
        wrap. None 이 dict 가 아니라 wrap 강제.)
        """
        sc = await self._invoke(name, args)
        inner = sc.get("result")
        if inner is None:
            return None
        return return_type.model_validate(inner)

    async def _call_list(
        self, name: str, args: dict[str, Any], item_type: type[T],
    ) -> list[T]:
        """list[T] — FastMCP 가 {"result": [...]} 로 wrap."""
        sc = await self._invoke(name, args)
        items = sc.get("result") or []
        return [item_type.model_validate(it) for it in items]

    async def _call_scalar(self, name: str, args: dict[str, Any]) -> Any:
        """bool / int / str 등 — FastMCP 가 {"result": <scalar>} 로 wrap."""
        sc = await self._invoke(name, args)
        return sc.get("result")

    async def _invoke(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """MCP 도구 호출 → structuredContent 반환.

        FastMCP 는 모든 응답에 structuredContent 를 채움 (MCP spec 2025-06-18):
        - Pydantic 모델 → 모델 dict 그대로
        - list / scalar / None → `{"result": <value>}` 로 wrap (MCP 의 structured
          content 는 dict 만 허용하기 때문)
        """
        result = await self._mcp.call_tool(name, args)
        return result.structuredContent or {}


# ──────────────────────────────────────────────────────────────────────
# 내부 헬퍼 — args 조립을 한 곳에서
# ──────────────────────────────────────────────────────────────────────


def _doc(model: BaseModel) -> dict[str, Any]:
    """`{"doc": <model dict>}` 래핑."""
    return {"doc": model.model_dump(mode="json")}


def _id_patch(id: UUID, patch: BaseModel) -> dict[str, Any]:
    """update 도구의 `{"id": ..., "patch": ...}` 래핑.

    patch 는 `exclude_unset=True` 로 명시된 필드만 보냄 (Pydantic Update 시멘틱).
    """
    return {
        "id": str(id),
        "patch": patch.model_dump(mode="json", exclude_unset=True),
    }


def _list_args(
    where: dict[str, Any] | None,
    limit: int,
    offset: int,
    order_by: str,
) -> dict[str, Any]:
    args: dict[str, Any] = {"limit": limit, "offset": offset, "order_by": order_by}
    if where is not None:
        args["where"] = where
    return args


def _where_args(where: dict[str, Any] | None) -> dict[str, Any]:
    return {} if where is None else {"where": where}


__all__ = ["DocStoreClient"]
