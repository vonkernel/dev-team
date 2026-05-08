"""DocStoreClient — Doc Store MCP 의 typed 클라이언트.

호출자는 Pydantic 모델 입출력만 다룸. wire-level 디테일 (도구명 / dict 래핑 /
JSON parse) 모두 본 클래스 안에 격리.

#75 재설계: chat tier (Session / Chat / Assignment) + A2A tier (A2AContext /
A2AMessage / A2ATask / A2ATaskStatusUpdate / A2ATaskArtifact) + 도메인 산출물
(Issue / WikiPage). 기존 AgentTask / AgentSession / AgentItem 폐기.
"""

from __future__ import annotations

from typing import Any, TypeVar
from uuid import UUID

from pydantic import BaseModel

from dev_team_shared.doc_store.schemas import (
    A2AContextCreate,
    A2AContextRead,
    A2AContextUpdate,
    A2AMessageCreate,
    A2AMessageRead,
    A2ATaskArtifactCreate,
    A2ATaskArtifactRead,
    A2ATaskCreate,
    A2ATaskRead,
    A2ATaskStatusUpdateCreate,
    A2ATaskStatusUpdateRead,
    A2ATaskUpdate,
    AssignmentCreate,
    AssignmentRead,
    AssignmentUpdate,
    ChatCreate,
    ChatRead,
    IssueCreate,
    IssueRead,
    IssueUpdate,
    SessionCreate,
    SessionRead,
    SessionUpdate,
    WikiPageCreate,
    WikiPageRead,
    WikiPageUpdate,
)
from dev_team_shared.doc_store.tool_names import (
    A2AContextTools,
    A2AMessageTools,
    A2ATaskArtifactTools,
    A2ATaskStatusUpdateTools,
    A2ATaskTools,
    AssignmentTools,
    ChatTools,
    IssueTools,
    SessionTools,
    WikiPageTools,
)
from dev_team_shared.mcp_client import StreamableMCPClient

T = TypeVar("T", bound=BaseModel)


class DocStoreClient:
    """Typed wrapper around `StreamableMCPClient` for Doc Store MCP 도구.

    각 collection × op 마다 1 메서드. 모든 입력은 Pydantic 모델, 모든 반환은
    Pydantic 모델 / scalar 또는 None. dict / 문자열은 본 클래스 외부로 새지 않음.
    """

    def __init__(self, mcp: StreamableMCPClient) -> None:
        self._mcp = mcp

    # ──────────────────────────────────────────────────────────────────────
    # Chat tier — sessions
    # ──────────────────────────────────────────────────────────────────────

    async def session_create(self, doc: SessionCreate) -> SessionRead:
        return await self._call(SessionTools.CREATE, _doc(doc), SessionRead)

    async def session_update(
        self, id: UUID, patch: SessionUpdate,
    ) -> SessionRead | None:
        return await self._call_optional(
            SessionTools.UPDATE, _id_patch(id, patch), SessionRead,
        )

    async def session_get(self, id: UUID) -> SessionRead | None:
        return await self._call_optional(
            SessionTools.GET, {"id": str(id)}, SessionRead,
        )

    async def session_list(
        self,
        *,
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "started_at DESC",
    ) -> list[SessionRead]:
        return await self._call_list(
            SessionTools.LIST, _list_args(where, limit, offset, order_by), SessionRead,
        )

    async def session_delete(self, id: UUID) -> bool:
        return await self._call_scalar(SessionTools.DELETE, {"id": str(id)})

    async def session_count(self, *, where: dict[str, Any] | None = None) -> int:
        return await self._call_scalar(SessionTools.COUNT, _where_args(where))

    # ──────────────────────────────────────────────────────────────────────
    # Chat tier — chats (immutable — no update)
    # ──────────────────────────────────────────────────────────────────────

    async def chat_create(self, doc: ChatCreate) -> ChatRead:
        return await self._call(ChatTools.CREATE, _doc(doc), ChatRead)

    async def chat_get(self, id: UUID) -> ChatRead | None:
        return await self._call_optional(
            ChatTools.GET, {"id": str(id)}, ChatRead,
        )

    async def chat_list(
        self,
        *,
        where: dict[str, Any] | None = None,
        limit: int = 200,
        offset: int = 0,
        order_by: str = "created_at",
    ) -> list[ChatRead]:
        return await self._call_list(
            ChatTools.LIST, _list_args(where, limit, offset, order_by), ChatRead,
        )

    async def chat_delete(self, id: UUID) -> bool:
        return await self._call_scalar(ChatTools.DELETE, {"id": str(id)})

    async def chat_count(self, *, where: dict[str, Any] | None = None) -> int:
        return await self._call_scalar(ChatTools.COUNT, _where_args(where))

    async def chat_list_by_session(self, session_id: UUID) -> list[ChatRead]:
        return await self._call_list(
            ChatTools.LIST_BY_SESSION,
            {"session_id": str(session_id)},
            ChatRead,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Chat tier — assignments
    # ──────────────────────────────────────────────────────────────────────

    async def assignment_create(self, doc: AssignmentCreate) -> AssignmentRead:
        return await self._call(AssignmentTools.CREATE, _doc(doc), AssignmentRead)

    async def assignment_update(
        self, id: UUID, patch: AssignmentUpdate,
    ) -> AssignmentRead | None:
        return await self._call_optional(
            AssignmentTools.UPDATE, _id_patch(id, patch), AssignmentRead,
        )

    async def assignment_get(self, id: UUID) -> AssignmentRead | None:
        return await self._call_optional(
            AssignmentTools.GET, {"id": str(id)}, AssignmentRead,
        )

    async def assignment_list(
        self,
        *,
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> list[AssignmentRead]:
        return await self._call_list(
            AssignmentTools.LIST,
            _list_args(where, limit, offset, order_by),
            AssignmentRead,
        )

    async def assignment_delete(self, id: UUID) -> bool:
        return await self._call_scalar(AssignmentTools.DELETE, {"id": str(id)})

    async def assignment_count(self, *, where: dict[str, Any] | None = None) -> int:
        return await self._call_scalar(AssignmentTools.COUNT, _where_args(where))

    async def assignment_list_by_session(
        self, root_session_id: UUID,
    ) -> list[AssignmentRead]:
        return await self._call_list(
            AssignmentTools.LIST_BY_SESSION,
            {"root_session_id": str(root_session_id)},
            AssignmentRead,
        )

    # ──────────────────────────────────────────────────────────────────────
    # A2A tier — a2a_contexts
    # ──────────────────────────────────────────────────────────────────────

    async def a2a_context_create(self, doc: A2AContextCreate) -> A2AContextRead:
        return await self._call(A2AContextTools.CREATE, _doc(doc), A2AContextRead)

    async def a2a_context_update(
        self, id: UUID, patch: A2AContextUpdate,
    ) -> A2AContextRead | None:
        return await self._call_optional(
            A2AContextTools.UPDATE, _id_patch(id, patch), A2AContextRead,
        )

    async def a2a_context_get(self, id: UUID) -> A2AContextRead | None:
        return await self._call_optional(
            A2AContextTools.GET, {"id": str(id)}, A2AContextRead,
        )

    async def a2a_context_list(
        self,
        *,
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "started_at DESC",
    ) -> list[A2AContextRead]:
        return await self._call_list(
            A2AContextTools.LIST,
            _list_args(where, limit, offset, order_by),
            A2AContextRead,
        )

    async def a2a_context_delete(self, id: UUID) -> bool:
        return await self._call_scalar(A2AContextTools.DELETE, {"id": str(id)})

    async def a2a_context_count(self, *, where: dict[str, Any] | None = None) -> int:
        return await self._call_scalar(A2AContextTools.COUNT, _where_args(where))

    async def a2a_context_find_by_context_id(
        self, context_id: str,
    ) -> A2AContextRead | None:
        return await self._call_optional(
            A2AContextTools.FIND_BY_CONTEXT_ID,
            {"context_id": context_id},
            A2AContextRead,
        )

    # ──────────────────────────────────────────────────────────────────────
    # A2A tier — a2a_messages (immutable — no update)
    # ──────────────────────────────────────────────────────────────────────

    async def a2a_message_create(self, doc: A2AMessageCreate) -> A2AMessageRead:
        return await self._call(A2AMessageTools.CREATE, _doc(doc), A2AMessageRead)

    async def a2a_message_get(self, id: UUID) -> A2AMessageRead | None:
        return await self._call_optional(
            A2AMessageTools.GET, {"id": str(id)}, A2AMessageRead,
        )

    async def a2a_message_list(
        self,
        *,
        where: dict[str, Any] | None = None,
        limit: int = 200,
        offset: int = 0,
        order_by: str = "created_at",
    ) -> list[A2AMessageRead]:
        return await self._call_list(
            A2AMessageTools.LIST,
            _list_args(where, limit, offset, order_by),
            A2AMessageRead,
        )

    async def a2a_message_delete(self, id: UUID) -> bool:
        return await self._call_scalar(A2AMessageTools.DELETE, {"id": str(id)})

    async def a2a_message_count(self, *, where: dict[str, Any] | None = None) -> int:
        return await self._call_scalar(A2AMessageTools.COUNT, _where_args(where))

    async def a2a_message_list_by_context(
        self, a2a_context_id: UUID,
    ) -> list[A2AMessageRead]:
        return await self._call_list(
            A2AMessageTools.LIST_BY_CONTEXT,
            {"a2a_context_id": str(a2a_context_id)},
            A2AMessageRead,
        )

    async def a2a_message_list_by_task(
        self, a2a_task_id: UUID,
    ) -> list[A2AMessageRead]:
        return await self._call_list(
            A2AMessageTools.LIST_BY_TASK,
            {"a2a_task_id": str(a2a_task_id)},
            A2AMessageRead,
        )

    # ──────────────────────────────────────────────────────────────────────
    # A2A tier — a2a_tasks
    # ──────────────────────────────────────────────────────────────────────

    async def a2a_task_create(self, doc: A2ATaskCreate) -> A2ATaskRead:
        return await self._call(A2ATaskTools.CREATE, _doc(doc), A2ATaskRead)

    async def a2a_task_update(
        self, id: UUID, patch: A2ATaskUpdate,
    ) -> A2ATaskRead | None:
        return await self._call_optional(
            A2ATaskTools.UPDATE, _id_patch(id, patch), A2ATaskRead,
        )

    async def a2a_task_get(self, id: UUID) -> A2ATaskRead | None:
        return await self._call_optional(
            A2ATaskTools.GET, {"id": str(id)}, A2ATaskRead,
        )

    async def a2a_task_list(
        self,
        *,
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "submitted_at DESC",
    ) -> list[A2ATaskRead]:
        return await self._call_list(
            A2ATaskTools.LIST,
            _list_args(where, limit, offset, order_by),
            A2ATaskRead,
        )

    async def a2a_task_delete(self, id: UUID) -> bool:
        return await self._call_scalar(A2ATaskTools.DELETE, {"id": str(id)})

    async def a2a_task_count(self, *, where: dict[str, Any] | None = None) -> int:
        return await self._call_scalar(A2ATaskTools.COUNT, _where_args(where))

    async def a2a_task_find_by_task_id(self, task_id: str) -> A2ATaskRead | None:
        return await self._call_optional(
            A2ATaskTools.FIND_BY_TASK_ID,
            {"task_id": task_id},
            A2ATaskRead,
        )

    # ──────────────────────────────────────────────────────────────────────
    # A2A tier — a2a_task_status_updates (immutable — no update)
    # ──────────────────────────────────────────────────────────────────────

    async def a2a_task_status_update_create(
        self, doc: A2ATaskStatusUpdateCreate,
    ) -> A2ATaskStatusUpdateRead:
        return await self._call(
            A2ATaskStatusUpdateTools.CREATE, _doc(doc), A2ATaskStatusUpdateRead,
        )

    async def a2a_task_status_update_get(
        self, id: UUID,
    ) -> A2ATaskStatusUpdateRead | None:
        return await self._call_optional(
            A2ATaskStatusUpdateTools.GET, {"id": str(id)}, A2ATaskStatusUpdateRead,
        )

    async def a2a_task_status_update_list(
        self,
        *,
        where: dict[str, Any] | None = None,
        limit: int = 200,
        offset: int = 0,
        order_by: str = "transitioned_at",
    ) -> list[A2ATaskStatusUpdateRead]:
        return await self._call_list(
            A2ATaskStatusUpdateTools.LIST,
            _list_args(where, limit, offset, order_by),
            A2ATaskStatusUpdateRead,
        )

    async def a2a_task_status_update_delete(self, id: UUID) -> bool:
        return await self._call_scalar(
            A2ATaskStatusUpdateTools.DELETE, {"id": str(id)},
        )

    async def a2a_task_status_update_count(
        self, *, where: dict[str, Any] | None = None,
    ) -> int:
        return await self._call_scalar(
            A2ATaskStatusUpdateTools.COUNT, _where_args(where),
        )

    async def a2a_task_status_update_list_by_task(
        self, a2a_task_id: UUID,
    ) -> list[A2ATaskStatusUpdateRead]:
        return await self._call_list(
            A2ATaskStatusUpdateTools.LIST_BY_TASK,
            {"a2a_task_id": str(a2a_task_id)},
            A2ATaskStatusUpdateRead,
        )

    # ──────────────────────────────────────────────────────────────────────
    # A2A tier — a2a_task_artifacts (immutable — no update)
    # ──────────────────────────────────────────────────────────────────────

    async def a2a_task_artifact_create(
        self, doc: A2ATaskArtifactCreate,
    ) -> A2ATaskArtifactRead:
        return await self._call(
            A2ATaskArtifactTools.CREATE, _doc(doc), A2ATaskArtifactRead,
        )

    async def a2a_task_artifact_get(self, id: UUID) -> A2ATaskArtifactRead | None:
        return await self._call_optional(
            A2ATaskArtifactTools.GET, {"id": str(id)}, A2ATaskArtifactRead,
        )

    async def a2a_task_artifact_list(
        self,
        *,
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> list[A2ATaskArtifactRead]:
        return await self._call_list(
            A2ATaskArtifactTools.LIST,
            _list_args(where, limit, offset, order_by),
            A2ATaskArtifactRead,
        )

    async def a2a_task_artifact_delete(self, id: UUID) -> bool:
        return await self._call_scalar(A2ATaskArtifactTools.DELETE, {"id": str(id)})

    async def a2a_task_artifact_count(
        self, *, where: dict[str, Any] | None = None,
    ) -> int:
        return await self._call_scalar(A2ATaskArtifactTools.COUNT, _where_args(where))

    async def a2a_task_artifact_list_by_task(
        self, a2a_task_id: UUID,
    ) -> list[A2ATaskArtifactRead]:
        return await self._call_list(
            A2ATaskArtifactTools.LIST_BY_TASK,
            {"a2a_task_id": str(a2a_task_id)},
            A2ATaskArtifactRead,
        )

    # ──────────────────────────────────────────────────────────────────────
    # 도메인 산출물 — issues
    # ──────────────────────────────────────────────────────────────────────

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
        return await self._call_optional(IssueTools.GET, {"id": str(id)}, IssueRead)

    async def issue_list(
        self,
        *,
        where: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> list[IssueRead]:
        return await self._call_list(
            IssueTools.LIST, _list_args(where, limit, offset, order_by), IssueRead,
        )

    async def issue_delete(self, id: UUID) -> bool:
        return await self._call_scalar(IssueTools.DELETE, {"id": str(id)})

    async def issue_count(self, *, where: dict[str, Any] | None = None) -> int:
        return await self._call_scalar(IssueTools.COUNT, _where_args(where))

    # ──────────────────────────────────────────────────────────────────────
    # 도메인 산출물 — wiki_pages
    # ──────────────────────────────────────────────────────────────────────

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

    # ──────────────────────────────────────────────────────────────────────
    # 내부 — wire 호출 + 직렬화/역직렬화
    # ──────────────────────────────────────────────────────────────────────

    async def _call(
        self, name: str, args: dict[str, Any], return_type: type[T],
    ) -> T:
        sc = await self._invoke(name, args)
        return return_type.model_validate(sc)

    async def _call_optional(
        self, name: str, args: dict[str, Any], return_type: type[T],
    ) -> T | None:
        sc = await self._invoke(name, args)
        inner = sc.get("result")
        if inner is None:
            return None
        return return_type.model_validate(inner)

    async def _call_list(
        self, name: str, args: dict[str, Any], item_type: type[T],
    ) -> list[T]:
        sc = await self._invoke(name, args)
        items = sc.get("result") or []
        return [item_type.model_validate(it) for it in items]

    async def _call_scalar(self, name: str, args: dict[str, Any]) -> Any:
        sc = await self._invoke(name, args)
        return sc.get("result")

    async def _invoke(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        result = await self._mcp.call_tool(name, args)
        return result.structuredContent or {}


# ──────────────────────────────────────────────────────────────────────────
# 내부 헬퍼 — args 조립을 한 곳에서
# ──────────────────────────────────────────────────────────────────────────


def _doc(model: BaseModel) -> dict[str, Any]:
    return {"doc": model.model_dump(mode="json")}


def _id_patch(id: UUID, patch: BaseModel) -> dict[str, Any]:
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
